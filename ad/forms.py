"""Formulaires AIP – Partie 3 (AD)."""
from django import forms
from django.utils.dateparse import parse_date

from common.fields import DMSField
from common.models import (Aerodrome, Airspace, Chart, CommunicationFacility,
                           ContactPoint, Navaid, Obstacle, AiracCycle)
from common.airac_calendar import AIRAC_CALENDAR

from .models import (Apron, DeclaredDistance, OperationalHours,
                     PassengerFacility, Runway, RunwayLighting, Taxiway,
                     TextSection)


# ===========================================================================
# AERODROME (AD 2.1 / 2.2) — coordonnées en DMS
# ===========================================================================
class AerodromeForm(forms.ModelForm):
    latitude = DMSField(is_lat=True, label="Latitude (DMS)")
    longitude = DMSField(is_lat=False, label="Longitude (DMS)")

    class Meta:
        model = Aerodrome
        exclude = ("created_at", "updated_at")
        widgets = {"remarks": forms.Textarea(attrs={"rows": 2})}


# ===========================================================================
# RUNWAY (AD 2.12) — THR et RWY end en DMS
# ===========================================================================
class RunwayForm(forms.ModelForm):
    thr_latitude = DMSField(is_lat=True, label="THR latitude")
    thr_longitude = DMSField(is_lat=False, label="THR longitude")
    end_latitude = DMSField(is_lat=True, label="RWY end latitude")
    end_longitude = DMSField(is_lat=False, label="RWY end longitude")

    class Meta:
        model = Runway
        exclude = ("aerodrome",)


# ===========================================================================
# NAVAID (AD 2.19) — coordonnées en DMS
# ===========================================================================
class NavaidForm(forms.ModelForm):
    latitude = DMSField(is_lat=True, label="Latitude (DMS)")
    longitude = DMSField(is_lat=False, label="Longitude (DMS)")

    class Meta:
        model = Navaid
        exclude = ("aerodrome",)


# ===========================================================================
# OBSTACLE (AD 2.10) — coordonnées en DMS
# ===========================================================================
class ObstacleForm(forms.ModelForm):
    latitude = DMSField(is_lat=True, label="Latitude (DMS)")
    longitude = DMSField(is_lat=False, label="Longitude (DMS)")

    class Meta:
        model = Obstacle
        exclude = ("aerodrome",)


# ===========================================================================
# Autres formulaires (inchangés)
# ===========================================================================
class ContactPointForm(forms.ModelForm):
    class Meta:
        model = ContactPoint
        exclude = ("aerodrome",)


class OperationalHoursForm(forms.ModelForm):
    class Meta:
        model = OperationalHours
        exclude = ("aerodrome",)


class PassengerFacilityForm(forms.ModelForm):
    class Meta:
        model = PassengerFacility
        exclude = ("aerodrome",)


class ApronForm(forms.ModelForm):
    class Meta:
        model = Apron
        exclude = ("aerodrome",)


class TaxiwayForm(forms.ModelForm):
    class Meta:
        model = Taxiway
        exclude = ("aerodrome",)


class CommunicationFacilityForm(forms.ModelForm):
    class Meta:
        model = CommunicationFacility
        exclude = ("aerodrome",)


class AirspaceForm(forms.ModelForm):
    class Meta:
        model = Airspace
        exclude = ("aerodrome",)


class ChartForm(forms.ModelForm):
    class Meta:
        model = Chart
        exclude = ("aerodrome",)


class TextSectionForm(forms.ModelForm):
    class Meta:
        model = TextSection
        exclude = ("aerodrome",)
        widgets = {"content": forms.Textarea(attrs={"rows": 5})}


# ===========================================================================
# Import JSON
# ===========================================================================
class ImportForm(forms.Form):
    json_file = forms.FileField(
        required=False,
        widget=forms.ClearableFileInput(attrs={"accept": ".json",
                                               "class": "form-control"}),
    )
    json_data = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            "rows": 15, "class": "form-control font-monospace",
            "placeholder": '{"icao": "DAUZ", "name": "...", "runways": [...]}',
        }),
    )

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("json_file") and not cleaned.get("json_data", "").strip():
            raise forms.ValidationError("Fournissez soit un fichier, soit du JSON.")
        return cleaned


# ===========================================================================
# AD 2.13 – Declared distances
# ===========================================================================
class DeclaredDistanceForm(forms.ModelForm):
    class Meta:
        model = DeclaredDistance
        exclude = ("runway",)
        widgets = {
            "tora": forms.NumberInput(attrs={"class": "form-control", "min": 0}),
            "toda": forms.NumberInput(attrs={"class": "form-control", "min": 0}),
            "asda": forms.NumberInput(attrs={"class": "form-control", "min": 0}),
            "lda": forms.NumberInput(attrs={"class": "form-control", "min": 0}),
            "remarks": forms.Textarea(attrs={"rows": 2, "class": "form-control"}),
        }

    def clean(self):
        c = super().clean()
        tora, toda, asda, lda = c.get("tora"), c.get("toda"), c.get("asda"), c.get("lda")
        if tora and toda and toda < tora:
            self.add_error("toda", "TODA doit être ≥ TORA (règle ICAO).")
        if toda and asda and asda < toda:
            self.add_error("asda", "ASDA doit être ≥ TODA (règle ICAO).")
        if tora and lda and lda > tora:
            self.add_error("lda", "LDA doit être ≤ TORA (règle ICAO).")
        return c


# ===========================================================================
# AD 2.14 – Approach and runway lighting
# ===========================================================================
class RunwayLightingForm(forms.ModelForm):
    class Meta:
        model = RunwayLighting
        exclude = ("runway",)
        widgets = {f: forms.TextInput(attrs={"class": "form-control"})
                   for f in ("apch_lgt_type", "apch_lgt_length",
                             "apch_lgt_intensity", "thr_lgt_color", "wbar",
                             "vasis_type", "vasis_meht", "papi_angle",
                             "tdz_lgt_length", "rcl_lgt", "rwy_edge_lgt",
                             "rwy_end_lgt", "swy_lgt")}
        widgets["remarks"] = forms.Textarea(attrs={"rows": 2, "class": "form-control"})


# ===========================================================================
# AIRAC – Cycle form
# ===========================================================================
def _format_airac_label(pub_iso, eff_iso):
    """Affiche les deux dates en clair. Ex :
       'Publication 11 DEC 2025  →  Effet 22 JAN 2026'
    """
    p = parse_date(pub_iso)
    e = parse_date(eff_iso)
    if not p or not e:
        return f"{pub_iso} → {eff_iso}"
    return (
        f"Publication {p.strftime('%d %b %Y').upper()}"
        f"  →  Effet {e.strftime('%d %b %Y').upper()}"
    )


class AiracCycleForm(forms.ModelForm):
    """Création / édition d'un cycle AIRAC.

    - `code`   : saisie LIBRE (TextInput). Le formulaire ne le modifie JAMAIS.
    - `preset` : aide à la saisie — remplit UNIQUEMENT les deux dates.
                 Clé = date d'effet (non ambiguë, non affichée brute).
    - `publication_date` / `effective_date` : toujours éditables manuellement.
    """

    preset = forms.ChoiceField(
        label="Cycle AIRAC prédéfini (aide à la saisie)",
        required=False,
        choices=[],
        widget=forms.Select(attrs={"class": "form-select", "id": "id_preset"}),
        help_text="Sélectionnez un cycle officiel pour pré-remplir les deux "
                  "dates. Le code du cycle reste libre et n'est jamais modifié.",
    )

    class Meta:
        model = AiracCycle
        fields = ["code", "publication_date", "effective_date"]
        widgets = {
            "code": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Saisir librement. Ex. 04/26, AIRAC-2026-04, TEST-01…",
            }),
            "publication_date": forms.DateInput(attrs={
                "class": "form-control", "type": "date",
                "id": "id_publication_date",
            }),
            "effective_date": forms.DateInput(attrs={
                "class": "form-control", "type": "date",
                "id": "id_effective_date",
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Choix : libellé = "Publication … → Effet …" (aucun code visible)
        choices = [("", "— Sélectionner un cycle prédéfini —")]
        for key, (pub, eff) in AIRAC_CALENDAR.items():
            choices.append((key, _format_airac_label(pub, eff)))
        self.fields["preset"].choices = choices

        # En édition : pré-sélectionner si la date d'effet existe dans le calendrier
        if self.instance and self.instance.pk and self.instance.effective_date:
            eff_iso = self.instance.effective_date.strftime("%Y-%m-%d")
            if eff_iso in AIRAC_CALENDAR:
                self.fields["preset"].initial = eff_iso

    def clean(self):
        cleaned = super().clean()

        # Auto-remplissage UNIQUEMENT des deux dates si le preset est choisi
        # et qu'elles sont vides. Le code n'est jamais touché.
        preset = cleaned.get("preset")
        if preset and preset in AIRAC_CALENDAR:
            pub_iso, eff_iso = AIRAC_CALENDAR[preset]
            if not cleaned.get("publication_date"):
                cleaned["publication_date"] = parse_date(pub_iso)
            if not cleaned.get("effective_date"):
                cleaned["effective_date"] = parse_date(eff_iso)

        pub = cleaned.get("publication_date")
        eff = cleaned.get("effective_date")

        # Cohérence AIRAC (effet >= publication)
        if pub and eff and eff < pub:
            raise forms.ValidationError(
                "La date d'effet doit être ≥ à la date de publication (AIRAC)."
            )

        # Unicité du code
        code = cleaned.get("code")
        if code:
            qs = AiracCycle.objects.filter(code=code)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                self.add_error("code", "Ce code de cycle existe déjà.")

        return cleaned


# ===========================================================================
# AIRAC – Publish form
# ===========================================================================
class AiracPublishForm(forms.Form):
    """Confirmation de publication du cycle brouillon."""
    confirm = forms.BooleanField(
        label="Je confirme la publication du cycle brouillon",
        required=True,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )


# ===========================================================================
# Registre : Modèle → ModelForm explicite (avec conversion DMS)
# ===========================================================================
FORM_CLASSES = {
    Aerodrome: AerodromeForm,
    Runway: RunwayForm,
    Navaid: NavaidForm,
    Obstacle: ObstacleForm,
}