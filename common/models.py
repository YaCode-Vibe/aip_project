"""Shared AIP entities – réutilisables par GEN, ENR et AD."""
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


# ===========================================================================
# Base
# ===========================================================================
class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class LatLonMixin(models.Model):
    """Coordonnées WGS-84 stockées en degrés décimaux (DD).
    Affichage DMS via propriétés ; migration PostGIS possible."""
    latitude = models.DecimalField(
        "Latitude (DD)", max_digits=9, decimal_places=6, null=True, blank=True,
        validators=[MinValueValidator(-90), MaxValueValidator(90)])
    longitude = models.DecimalField(
        "Longitude (DD)", max_digits=9, decimal_places=6, null=True, blank=True,
        validators=[MinValueValidator(-180), MaxValueValidator(180)])

    class Meta:
        abstract = True


# ===========================================================================
# AIRAC
# ===========================================================================
class AiracCycle(TimeStampedModel):
    code = models.CharField(max_length=12, unique=True)
    effective_date = models.DateField()
    publication_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=False)
    is_draft = models.BooleanField(
        default=False,
        help_text="Cycle en préparation, non encore publié.",
    )

    class Meta:
        ordering = ("-effective_date",)
        verbose_name = "AIRAC cycle"

    def __str__(self):
        return f"{self.code} ({self.effective_date})"


# ===========================================================================
# AERODROME
# ===========================================================================
class Aerodrome(TimeStampedModel, LatLonMixin):
    """AD 2.1 + AD 2.2."""

    class TrafficType(models.TextChoices):
        IFR = "IFR", "IFR"
        VFR = "VFR", "VFR"
        IFR_VFR = "IFR/VFR", "IFR/VFR"

    class AerodromeType(models.TextChoices):
        CIVIL = "CIVIL", "Civil"
        MIL = "MIL", "Military"
        CIVIL_MIL = "CIVIL/MIL", "Civil/Military"

    # --- AD 2.1
    icao_code = models.CharField("ICAO indicator", max_length=4, unique=True, db_index=True)
    name = models.CharField(max_length=160)
    city = models.CharField(max_length=80, blank=True)

    # --- AD 2.2
    arp_site = models.CharField("ARP site at AD", max_length=200, blank=True,
                                help_text="e.g. 'Intersection of the RWYs.'")
    distance_from_city = models.CharField(max_length=160, blank=True,
                                          help_text="e.g. '4.6 NM East from In Amenas'")
    elevation_m = models.DecimalField("Elevation (M)", max_digits=7, decimal_places=2,
                                      null=True, blank=True)
    reference_temperature_c = models.DecimalField("Reference temperature (°C)",
                                                  max_digits=4, decimal_places=1,
                                                  null=True, blank=True)
    geoid_undulation = models.CharField(max_length=40, blank=True, default="NIL")
    magnetic_variation_deg = models.DecimalField(max_digits=4, decimal_places=2,
                                                 null=True, blank=True)
    magnetic_variation_year = models.PositiveSmallIntegerField(null=True, blank=True)
    annual_change_deg = models.DecimalField(max_digits=4, decimal_places=2,
                                            null=True, blank=True)

    # --- AD 2.2.6 – Administration
    address = models.TextField(blank=True, help_text="Adresse postale complète")
    telefax = models.CharField(max_length=60, blank=True, help_text="Numéro de fax")
    telex = models.CharField(max_length=60, blank=True, help_text="Numéro de telex")

    # --- AD 2.2 items 7 & 8
    traffic_type = models.CharField(max_length=8, choices=TrafficType.choices,
                                    default=TrafficType.IFR_VFR)
    aerodrome_type = models.CharField(max_length=12, choices=AerodromeType.choices,
                                      default=AerodromeType.CIVIL_MIL)
    remarks = models.TextField(blank=True)

    # --- Statut / AIRAC
    is_operational = models.BooleanField(default=True)
    airac_cycle = models.ForeignKey(AiracCycle, null=True, blank=True,
                                    on_delete=models.SET_NULL, related_name="aerodromes")
    last_airac_cycle = models.ForeignKey(
        AiracCycle, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="published_for",
        help_text="Cycle AIRAC de la version courante (N).")
    previous_airac_cycle = models.ForeignKey(
        AiracCycle, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="superseded_for",
        help_text="Cycle AIRAC de la version précédente publiée (N-1).")
    previous_snapshot = models.JSONField(
        null=True, blank=True,
        help_text="Instantané JSON de la version N-1 (utilisé pour le diff).")

    class Meta:
        ordering = ("icao_code",)
        verbose_name = "Aerodrome"
        indexes = [models.Index(fields=["icao_code"]),
                   models.Index(fields=["name"])]

    def __str__(self):
        return f"{self.icao_code} – {self.name}"

    # ------------------------------------------------------------ propriétés
    @property
    def ad_2_1_label(self):
        return f"{self.icao_code} – {self.name}"

    @property
    def arp_decimal(self):
        if self.latitude is None or self.longitude is None:
            return "NIL"
        return f"{self.latitude} / {self.longitude}"

    @property
    def latitude_dms(self):
        from common.utils import dd_to_dms
        return dd_to_dms(self.latitude, is_lat=True)

    @property
    def longitude_dms(self):
        from common.utils import dd_to_dms
        return dd_to_dms(self.longitude, is_lat=False)

    @property
    def coordinates_dms(self):
        from common.utils import dd_pair_to_dms_string
        return dd_pair_to_dms_string(self.latitude, self.longitude)

    @property
    def coverage_report(self):
        from ad.services.serializer import coverage
        rows = coverage(self)
        filled = sum(1 for _, _, ok in rows if ok)
        total = len(rows)
        return {
            "rows": rows,
            "filled": filled,
            "total": total,
            "pct": int(filled * 100 / total) if total else 0,
        }


# ===========================================================================
# CONTACT POINT (AD 2.2 item 6)
# ===========================================================================
class ContactPoint(TimeStampedModel):
    class Role(models.TextChoices):
        ADMIN = "ADMIN", "AD Administration"
        TWR = "TWR", "Tower (TWR)"
        APP = "APP", "Approach (APP)"
        ARO = "ARO", "ATS Reporting Office (ARO)"
        MBO = "MBO", "Meteorological Briefing Office (MBO)"
        STD = "STD", "STD"
        AFS = "AFS", "AFS"
        TELEX = "TELEX", "Telex"
        FAX = "FAX", "Telefax"
        EMAIL = "EMAIL", "Email"

    aerodrome = models.ForeignKey(Aerodrome, on_delete=models.CASCADE,
                                  related_name="contacts")
    role = models.CharField(max_length=10, choices=Role.choices)
    value = models.CharField(max_length=200)

    class Meta:
        ordering = ("role",)
        unique_together = ("aerodrome", "role", "value")

    def __str__(self):
        return f"{self.get_role_display()}: {self.value}"


# ===========================================================================
# COMMUNICATION FACILITY (AD 2.18 / ENR 4.2)
# ===========================================================================
class CommunicationFacility(TimeStampedModel):
    class Service(models.TextChoices):
        TWR = "TWR", "TWR"
        APP = "APP", "APP"
        ACC = "ACC", "ACC"
        GND = "GND", "Ground"
        ATIS = "ATIS", "ATIS"
        VDF = "VDF", "VDF"
        FIS = "FIS", "FIS"
        SOL = "SOL", "Surface Movement Control"
        OTHER = "OTHER", "Other"

    aerodrome = models.ForeignKey(Aerodrome, null=True, blank=True,
                                  on_delete=models.CASCADE, related_name="comms")
    service = models.CharField(max_length=8, choices=Service.choices)
    call_sign = models.CharField(max_length=80)
    frequency = models.CharField(max_length=60,
                                 help_text="e.g. '119.7 MHz – 118.7 MHz (a)'")
    hours_of_operation = models.CharField(max_length=80, blank=True)
    remarks = models.TextField(blank=True)

    class Meta:
        ordering = ("service", "call_sign")
        verbose_name = "Communication facility"

    def __str__(self):
        return f"{self.get_service_display()} {self.call_sign} – {self.frequency}"


# ===========================================================================
# NAVAID (AD 2.19 / ENR 4.1)
# ===========================================================================
class Navaid(TimeStampedModel, LatLonMixin):
    class AidType(models.TextChoices):
        NDB = "NDB", "NDB"
        VOR = "VOR", "VOR"
        DVOR = "DVOR", "DVOR"
        DME = "DME", "DME"
        VOR_DME = "VOR/DME", "VOR/DME"
        DVOR_DME = "DVOR/DME", "DVOR/DME"
        LOC = "LOC", "LOC"
        GP = "GP", "Glide path"
        ILS = "ILS", "ILS"
        TACAN = "TACAN", "TACAN"
        OTHER = "OTHER", "Other"

    aerodrome = models.ForeignKey(Aerodrome, null=True, blank=True,
                                  on_delete=models.CASCADE, related_name="navaids")
    aid_type = models.CharField(max_length=12, choices=AidType.choices)
    designator = models.CharField("ID", max_length=10)
    frequency = models.CharField(max_length=60,
                                 help_text="e.g. '112.9 MHz CH 76 X'")
    hours_of_operation = models.CharField(max_length=40, blank=True)
    elevation_m = models.DecimalField(max_digits=7, decimal_places=2,
                                      null=True, blank=True)
    magnetic_variation = models.CharField(max_length=40, blank=True)
    remarks = models.TextField(blank=True)

    class Meta:
        ordering = ("aid_type", "designator")
        verbose_name = "Radio navigation aid"

    def __str__(self):
        return f"{self.get_aid_type_display()} {self.designator}"

    @property
    def coordinates_dms(self):
        from common.utils import dd_pair_to_dms_string
        return dd_pair_to_dms_string(self.latitude, self.longitude)


# ===========================================================================
# AIRSPACE (AD 2.17 / ENR 2.1)
# ===========================================================================
class Airspace(TimeStampedModel):
    class Kind(models.TextChoices):
        CTR = "CTR", "CTR"
        CTA = "CTA", "CTA"
        TMA = "TMA", "TMA"
        FIR = "FIR", "FIR"
        UIR = "UIR", "UIR"
        TSA = "TSA", "TSA"
        P = "P", "Prohibited"
        R = "R", "Restricted"
        D = "D", "Danger"
        OTHER = "OTHER", "Other"

    aerodrome = models.ForeignKey(Aerodrome, null=True, blank=True,
                                  on_delete=models.CASCADE, related_name="airspaces")
    kind = models.CharField(max_length=6, choices=Kind.choices, default=Kind.CTR)
    designation = models.CharField(max_length=120)
    lateral_limits = models.TextField(blank=True)
    vertical_limits_upper = models.CharField(max_length=60, blank=True)
    vertical_limits_lower = models.CharField(max_length=60, blank=True)
    airspace_class = models.CharField(max_length=10, blank=True)
    ats_unit_call_sign = models.CharField(max_length=80, blank=True)
    languages = models.CharField(max_length=40, blank=True)
    transition_altitude = models.CharField(max_length=40, blank=True)
    remarks = models.TextField(blank=True)

    class Meta:
        ordering = ("kind", "designation")
        verbose_name = "ATS airspace"

    def __str__(self):
        return f"{self.kind} {self.designation}"


# ===========================================================================
# OBSTACLE (AD 2.10 / ENR 5.4)
# ===========================================================================
class Obstacle(TimeStampedModel, LatLonMixin):
    class Area(models.TextChoices):
        APPROACH = "APPROACH", "Approach and take-off areas"
        CIRCLING = "CIRCLING", "Circling area and at aerodrome"
        ENROUTE = "ENROUTE", "En-route"

    aerodrome = models.ForeignKey(Aerodrome, null=True, blank=True,
                                  on_delete=models.CASCADE, related_name="obstacles")
    obst_id = models.CharField("OBST ID", max_length=24, blank=True)
    area = models.CharField(max_length=10, choices=Area.choices, default=Area.CIRCLING)
    obstacle_type = models.CharField(max_length=80)
    position_text = models.CharField(
        max_length=160, blank=True,
        help_text="Utilisé quand l'AIP donne une description au lieu de coordonnées "
                  "(ex. 'QDR 104°/2400 M from THR10')")
    elevation_m = models.DecimalField(max_digits=8, decimal_places=2,
                                      null=True, blank=True)
    height_m = models.DecimalField(max_digits=8, decimal_places=2,
                                   null=True, blank=True)
    markings = models.CharField(max_length=120, blank=True)
    lighting = models.CharField(max_length=40, blank=True)
    remarks = models.TextField(blank=True)

    class Meta:
        ordering = ("area", "obst_id")
        verbose_name = "Obstacle"

    def __str__(self):
        return f"{self.obst_id or self.obstacle_type}"

    @property
    def coordinates_dms(self):
        from common.utils import dd_pair_to_dms_string
        return dd_pair_to_dms_string(self.latitude, self.longitude)

    # common/models.py — dans class Obstacle
    def clean(self):
        from django.core.exceptions import ValidationError
        valid = {c[0] for c in self.Area.choices}
        if self.area not in valid:
            raise ValidationError({
                "area": f"Valeur invalide. Doit être parmi : {', '.join(valid)}"
            })

# ===========================================================================
# CHART (AD 2.24 / GEN 3.x)
# ===========================================================================
class Chart(TimeStampedModel):
    class ChartType(models.TextChoices):
        AD = "AD", "Aerodrome chart (ICAO)"
        AOC = "AOC", "Aerodrome obstacle chart"
        APDC = "APDC", "Aircraft parking/docking chart"
        SID = "SID", "Standard departure chart"
        STAR = "STAR", "Standard arrival chart"
        IAC = "IAC", "Instrument approach chart"
        VAC = "VAC", "Visual approach chart"
        ATCSMAC = "ATCSMAC", "ATC surveillance minimum altitude chart"
        OTHER = "OTHER", "Other"

    aerodrome = models.ForeignKey(Aerodrome, null=True, blank=True,
                                  on_delete=models.CASCADE, related_name="charts")
    chart_type = models.CharField(max_length=10, choices=ChartType.choices)
    title = models.CharField(max_length=200)
    reference = models.CharField(max_length=60, blank=True,
                                 help_text="e.g. 'AD 2 DAUZ-AD'")
    file = models.FileField(upload_to="charts/", null=True, blank=True)
    effective_date = models.DateField(null=True, blank=True)
    remarks = models.TextField(blank=True)

    class Meta:
        ordering = ("chart_type", "reference")
        verbose_name = "Chart"

    def __str__(self):
        return f"{self.get_chart_type_display()} – {self.reference or self.title}"