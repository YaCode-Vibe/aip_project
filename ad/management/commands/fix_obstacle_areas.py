"""Corrige les valeurs du champ `area` des obstacles existants."""
from django.core.management.base import BaseCommand
from common.models import Obstacle


NORMALIZATION_MAP = {
    "APPROACH": "APPROACH",
    "APPROACH AND TAKE-OFF AREAS": "APPROACH",
    "APPROACH AND TAKE-OFF": "APPROACH",
    "TAKE-OFF": "APPROACH",
    "APP": "APPROACH",
    "APCH": "APPROACH",
    "CIRCLING": "CIRCLING",
    "CIRCLING AREA AND AT AERODROME": "CIRCLING",
    "CIRCLING AREA": "CIRCLING",
    "ENROUTE": "ENROUTE",
    "EN-ROUTE": "ENROUTE",
    "EN ROUTE": "ENROUTE",
}


class Command(BaseCommand):
    help = "Corrige les valeurs du champ 'area' des obstacles existants."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true",
                            help="Affiche les changements sans les appliquer")
        parser.add_argument("--icao", help="Limiter à un seul aérodrome")

    def handle(self, *args, **opt):
        qs = Obstacle.objects.all()
        if opt["icao"]:
            qs = qs.filter(aerodrome__icao_code=opt["icao"].upper())

        fixed, untouched = 0, 0
        for o in qs:
            raw = (o.area or "").strip().upper()
            normalized = NORMALIZATION_MAP.get(raw, "CIRCLING")
            if normalized != o.area:
                self.stdout.write(
                    f"  {o.aerodrome.icao_code} {o.obst_id or '?'} : "
                    f"{o.area!r} → {normalized!r}"
                )
                if not opt["dry_run"]:
                    o.area = normalized
                    o.save(update_fields=["area"])
                fixed += 1
            else:
                untouched += 1

        prefix = "[DRY-RUN] " if opt["dry_run"] else ""
        self.stdout.write(self.style.SUCCESS(
            f"{prefix}{fixed} obstacle(s) corrigé(s), {untouched} inchangé(s)."
        ))