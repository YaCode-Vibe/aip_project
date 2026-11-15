from django.core.management.base import BaseCommand
from common.models import Aerodrome

AERODROMES = [
    ("DAUA", "ADRAR/Touat-Cheikh Sidi Mohamed Belkebir", "Adrar"),
    ("DAAG", "ALGER/Houari Boumediene", "Alger"),
    ("DABB", "ANNABA/Rabah Bitat", "Annaba"),
    ("DABT", "BATNA/Mostepha Ben Boulaid", "Batna"),
    ("DAAE", "BEJAIA/Soummam-Abane Ramdane", "Bejaia"),
    ("DAOR", "BECHAR/Boudghene Ben Ali Lotfi", "Bechar"),
    ("DATM", "BORDJ BADJI MOKHTAR", "Bordj Badji Mokhtar"),
    ("DAAD", "BOU SAADA", "Bou Saada"),
    ("DAUB", "BISKRA/Mohamed Khider", "Biskra"),
    ("DAOI", "CHLEF", "Chlef"),
    ("DABC", "CONSTANTINE/Mohamed Boudiaf", "Constantine"),
    ("DAAJ", "DJANET/Tiska", "Djanet"),
    ("DAOY", "EL BAYADH", "El Bayadh"),
    ("DAUE", "EL GOLEA", "El Golea"),
    ("DAUO", "EL OUED/Guemar", "El Oued"),
    ("DAUG", "GHARDAIA/Noumerat-Moufdi Zakaria", "Ghardaia"),
    ("DAOV", "GHRISS", "Ghriss"),
    ("DAUH", "HASSI MESSAOUD/Oued Irara-Krim Belkacem", "Hassi Messaoud"),
    ("DAAP", "ILLIZI/Takhamalt", "Illizi"),
    ("DATG", "IN GUEZZAM", "In Guezzam"),
    ("DAUI", "IN SALAH", "In Salah"),
    ("DAAV", "JIJEL/Ferhat Abbas", "Jijel"),
    ("DAOO", "ORAN/Ahmed Ben Bella", "Oran"),
    ("DAUU", "OUARGLA", "Ouargla"),
    ("DAAS", "SETIF/8 MAI 45", "Setif"),
    ("DAAT", "TAMENGHASSET/Aguenar-Hadj Bey Akhamok", "Tamanrasset"),
    ("DABS", "TEBESSA/Cheikh Larbi Tebessi", "Tebessa"),
    ("DAOB", "TIARET/Abdelhafid Boussouf Bou Chekif", "Tiaret"),
    ("DAUT", "TIMIMOUN", "Timimoun"),
    ("DAOF", "TINDOUF", "Tindouf"),
    ("DAON", "TLEMCEN/Zenata-Messali El Hadj", "Tlemcen"),
    ("DAUK", "TOUGGOURT/Sidi Mahdi", "Touggourt"),
    ("DAUZ", "ZARZAITINE/In Amenas", "In Amenas"),
]


class Command(BaseCommand):
    help = "Seed the 33 Algerian aerodromes of AIP Part 3 (AD 2)."

    def handle(self, *args, **options):
        created = 0
        for icao, name, city in AERODROMES:
            _, was_created = Aerodrome.objects.get_or_create(
                icao_code=icao, defaults={"name": name, "city": city})
            created += int(was_created)
        self.stdout.write(self.style.SUCCESS(
            f"{created} aerodrome(s) created, {len(AERODROMES)} processed."))