from django.core.management.base import BaseCommand
from ad.data.aip_algeria import AERODROMES
from ad.services.importer import import_aerodrome


class Command(BaseCommand):
    help = "Importe / met à jour les 33 aérodromes AIP Algérie dans la BDD."

    def add_arguments(self, parser):
        parser.add_argument("--icao", help="Importer un seul aérodrome par code ICAO")

    def handle(self, *args, **options):
        target = options.get("icao")
        aerodromes = AERODROMES
        if target:
            aerodromes = [a for a in AERODROMES if a["icao"] == target.upper()]
            if not aerodromes:
                self.stderr.write(self.style.ERROR(f"ICAO {target} non trouvé"))
                return

        ok, fail = 0, 0
        for data in aerodromes:
            try:
                ad = import_aerodrome(data)
                ok += 1
                self.stdout.write(self.style.SUCCESS(
                    f"[OK] {ad.icao_code} – {ad.name}"
                    f"  ({ad.runways.count()} piste(s), {ad.comms.count()} fréq., "
                    f"{ad.navaids.count()} aide(s) radio)"
                ))
            except Exception as e:
                fail += 1
                self.stderr.write(self.style.ERROR(
                    f"[KO] {data.get('icao')}: {e}"
                ))
        self.stdout.write(self.style.SUCCESS(
            f"\nImport terminé : {ok} OK, {fail} échec(s)."
        ))