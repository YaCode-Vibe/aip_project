"""Services de gestion des cycles AIRAC (publication conforme OACI)."""
from django.db import transaction

from common.models import Aerodrome, AiracCycle
from ad.services.pdf_generator import _compute_diff
from ad.services.serializer import aerodrome_to_dict


# ---------------------------------------------------------------- queries
def get_draft_cycle():
    """Retourne l'unique cycle brouillon (ou None)."""
    return AiracCycle.objects.filter(is_draft=True).first()


def get_active_cycle():
    """Retourne le dernier cycle publié."""
    return (AiracCycle.objects.filter(is_active=True)
            .order_by("-publication_date").first())


# ---------------------------------------------------------------- diff
def compute_aerodrome_diff(ad):
    """Diff entre l'état actuel en base et le snapshot publié."""
    current = aerodrome_to_dict(ad)
    return _compute_diff(current, ad.previous_snapshot or {})


def preview_all_changes():
    """Liste les aérodromes avec des modifications non publiées.

    Retourne une liste de dicts :
        {"aerodrome": <Aerodrome>, "changed_sections": [str], "is_new": bool}
    """
    results = []
    for ad in Aerodrome.objects.all().order_by("icao_code"):
        current = aerodrome_to_dict(ad)

        # Première publication : pas de snapshot mais nom renseigné
        if ad.previous_snapshot is None:
            if (current.get("name") or "").strip():
                results.append({
                    "aerodrome": ad,
                    "changed_sections": ["Nouvelle publication"],
                    "is_new": True,
                })
            continue

        diff = _compute_diff(current, ad.previous_snapshot)
        if diff.get("_any"):
            changed = [
                k for k, v in diff.items()
                if isinstance(v, dict) and v.get("changed")
            ]
            results.append({
                "aerodrome": ad,
                "changed_sections": changed,
                "is_new": False,
            })
    return results


# ---------------------------------------------------------------- publish
@transaction.atomic
def publish_draft_cycle():
    """Publie le cycle brouillon.

    Pour chaque aérodrome modifié (ou nouveau) :
      - previous_airac_cycle ← last_airac_cycle
      - previous_snapshot    ← état actuel
      - last_airac_cycle     ← draft
    Les aérodromes inchangés conservent leur cycle d'origine.

    Retourne (draft_cycle, nb_mis_à_jour).
    """
    draft = get_draft_cycle()
    if not draft:
        raise ValueError("Aucun cycle brouillon à publier.")

    # Désactiver l'ancien actif
    AiracCycle.objects.filter(is_active=True).update(is_active=False)

    updated = 0
    for ad in Aerodrome.objects.all():
        current = aerodrome_to_dict(ad)
        is_new = ad.previous_snapshot is None and (current.get("name") or "").strip()

        if is_new:
            changed = True
        else:
            diff = _compute_diff(current, ad.previous_snapshot or {})
            changed = diff.get("_any", False)

        if changed:
            ad.previous_airac_cycle = ad.last_airac_cycle
            ad.previous_snapshot = current
            ad.last_airac_cycle = draft
            ad.save(update_fields=[
                "previous_snapshot", "previous_airac_cycle", "last_airac_cycle",
            ])
            updated += 1

    draft.is_draft = False
    draft.is_active = True
    draft.save(update_fields=["is_draft", "is_active"])
    return draft, updated

