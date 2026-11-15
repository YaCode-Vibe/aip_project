"""Publie une nouvelle version AIRAC : fige N-1 et incrémente N."""
from django.core.management.base import BaseCommand
from django.utils.dateparse import parse_date

from common.models import Aerodrome, AiracCycle
from ad.services.serializer import aerodrome_to_dict


class Command(BaseCommand):
    help = "Fige la version courante (N-1) et publie un nouveau cycle AIRAC (N)."

    def add_arguments(self, parser):
        parser.add_argument("--airac", required=True,
                            help="Code du nouveau cycle, ex. 03/26")
        parser.add_argument("--publication-date", required=True,
                            help="Date de publication (YYYY-MM-DD)")
        parser.add_argument("--effective-date", default=None,
                            help="Date d'effet (défaut : +28 jours)")
        parser.add_argument("--icao", default=None,
                            help="Ne publier qu'un seul aérodrome")

    def handle(self, *args, **opt):
        pub = parse_date(opt["publication_date"])
        eff = parse_date(opt["effective_date"]) if opt["effective_date"] else None

        cycle, _ = AiracCycle.objects.update_or_create(
            code=opt["airac"],
            defaults={"publication_date": pub, "effective_date": eff or pub,
                      "is_active": True},
        )
        # Désactiver les autres
        AiracCycle.objects.exclude(pk=cycle.pk).update(is_active=False)

        qs = Aerodrome.objects.all()
        if opt["icao"]:
            qs = qs.filter(icao_code=opt["icao"].upper())

        count = 0
        for ad in qs:
            # 1) figer l'état courant → previous_snapshot (N-1)
            ad.previous_snapshot = aerodrome_to_dict(ad)
            # 2) basculer les cycles : N-1 <- N
            ad.previous_airac_cycle = ad.last_airac_cycle
            # 3) assigner le nouveau cycle
            ad.last_airac_cycle = cycle
            ad.save(update_fields=[
                "previous_snapshot", "previous_airac_cycle", "last_airac_cycle",
            ])
            count += 1

        self.stdout.write(self.style.SUCCESS(
            f"AIRAC {cycle.code} publié pour {count} aérodrome(s) "
            f"(publication {pub})."
        ))