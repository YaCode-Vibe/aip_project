"""ICAO Doc 10066 – Part 3 (AD) : sections AD 1.x et AD 2.x."""
from django.db import models

from common.models import (Aerodrome, Airspace, Chart, CommunicationFacility,
                           LatLonMixin, Navaid, Obstacle, TimeStampedModel)


# ===========================================================================
# AD 1 – AERODROMES/HELIPORTS — INTRODUCTION
# ===========================================================================
class AerodromeConditionOfUse(TimeStampedModel):
    """AD 1.1 Aerodrome/heliport availability and conditions of use."""
    aerodrome = models.OneToOneField(
        Aerodrome, on_delete=models.CASCADE, related_name="condition_of_use")
    availability = models.TextField(blank=True)
    conditions_of_use = models.TextField(blank=True)
    remarks = models.TextField(blank=True)

    class Meta:
        verbose_name = "AD 1.1 – Condition of use"

    def __str__(self):
        return f"AD 1.1 – {self.aerodrome.icao_code}"


class RescueFirefighting(TimeStampedModel):
    """AD 1.2 / AD 2.6 – Rescue and firefighting services."""
    aerodrome = models.OneToOneField(
        Aerodrome, on_delete=models.CASCADE, related_name="rffs")
    category = models.CharField("AD category", max_length=10, blank=True)
    rescue_equipment = models.TextField(blank=True)
    removal_capability = models.TextField(
        "Capability for removal of disabled aircraft", blank=True)
    remarks = models.TextField(blank=True)

    class Meta:
        verbose_name = "AD 2.6 – Rescue and firefighting services"

    def __str__(self):
        return f"RFFS {self.aerodrome.icao_code} CAT {self.category}"


class SnowPlan(TimeStampedModel):
    """AD 1.2 – Snow plan."""
    aerodrome = models.OneToOneField(
        Aerodrome, on_delete=models.CASCADE, related_name="snow_plan")
    clearing_equipment = models.TextField(blank=True)
    clearance_priorities = models.TextField(blank=True)
    remarks = models.TextField(blank=True)

    class Meta:
        verbose_name = "AD 1.2 – Snow plan"

    def __str__(self):
        return f"Snow plan – {self.aerodrome.icao_code}"


class AerodromeGroup(TimeStampedModel):
    """AD 1.4 – Grouping of aerodromes/heliports.    ⬅ RESTAURÉ"""
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    aerodromes = models.ManyToManyField(Aerodrome, blank=True,
                                        related_name="groups")

    class Meta:
        verbose_name = "AD 1.4 – Aerodrome group"

    def __str__(self):
        return f"{self.code} – {self.name}"


class AerodromeCertificate(TimeStampedModel):
    """AD 1.5 – Status of certification of aerodromes."""
    class Status(models.TextChoices):
        CERTIFIED = "CERTIFIED", "Certified"
        NOT_CERTIFIED = "NOT_CERTIFIED", "Not certified"
        PENDING = "PENDING", "Pending"

    aerodrome = models.OneToOneField(
        Aerodrome, on_delete=models.CASCADE, related_name="certificate")
    certificate_number = models.CharField(max_length=60, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices,
                              default=Status.NOT_CERTIFIED)
    issue_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    scope = models.TextField(blank=True)
    remarks = models.TextField(blank=True)

    class Meta:
        verbose_name = "AD 1.5 – Certification"

    def __str__(self):
        return f"{self.aerodrome.icao_code} – {self.get_status_display()}"


# ===========================================================================
# AD 2 – AERODROMES
# ===========================================================================
class OperationalHours(TimeStampedModel):
    """AD 2.3 Operational hours."""
    class Service(models.TextChoices):
        AD_ADMIN = "AD_ADMIN", "AD administration"
        CUSTOMS = "CUSTOMS", "Customs and immigration"
        HEALTH = "HEALTH", "Health and sanitation"
        AIS = "AIS", "AIS briefing office"
        ARO = "ARO", "ATS reporting office (ARO)"
        MET = "MET", "MET briefing office"
        ATS = "ATS", "ATS"
        FUELING = "FUELING", "Fueling"
        HANDLING = "HANDLING", "Handling"
        SECURITY = "SECURITY", "Security"
        DEICING = "DEICING", "De-icing"

    aerodrome = models.ForeignKey(
        Aerodrome, on_delete=models.CASCADE, related_name="operational_hours")
    service = models.CharField(max_length=12, choices=Service.choices)
    hours_text = models.CharField(
        max_length=120, blank=True,
        help_text="e.g. '0700/1500 (SUN/THU)' ou 'H24'")
    is_h24 = models.BooleanField(default=False)
    remarks = models.TextField(blank=True)

    class Meta:
        ordering = ("service",)
        unique_together = ("aerodrome", "service")
        verbose_name = "AD 2.3 – Operational hours"

    def __str__(self):
        return f"{self.aerodrome.icao_code} – {self.get_service_display()}"


class HandlingService(TimeStampedModel):
    """AD 2.4 Handling services and facilities."""
    aerodrome = models.OneToOneField(
        Aerodrome, on_delete=models.CASCADE, related_name="handling")
    cargo_facilities = models.TextField(blank=True)
    fuel_types = models.TextField("Fuel and oil types", blank=True)
    fueling_facilities = models.TextField(
        "Fuelling facilities and capacity", blank=True)
    deicing_facilities = models.TextField(blank=True)
    hangar_space = models.TextField(blank=True)
    repair_facilities = models.TextField(blank=True)
    remarks = models.TextField(blank=True)

    class Meta:
        verbose_name = "AD 2.4 – Handling services"

    def __str__(self):
        return f"AD 2.4 – {self.aerodrome.icao_code}"


class PassengerFacility(TimeStampedModel):
    """AD 2.5 Passenger facilities."""
    class Kind(models.TextChoices):
        HOTELS = "HOTELS", "Hotels"
        RESTAURANTS = "RESTAURANTS", "Restaurants"
        TRANSPORT = "TRANSPORT", "Transportation facilities"
        MEDICAL = "MEDICAL", "Medical facilities"
        BANK_POST = "BANK_POST", "Bank and post office"
        TOURIST = "TOURIST", "Tourist office"
        OTHER = "OTHER", "Other"

    aerodrome = models.ForeignKey(
        Aerodrome, on_delete=models.CASCADE,
        related_name="passenger_facilities")
    kind = models.CharField(max_length=12, choices=Kind.choices)
    description = models.CharField(max_length=160, blank=True)
    remarks = models.TextField(blank=True)

    class Meta:
        ordering = ("kind",)
        verbose_name = "AD 2.5 – Passenger facility"

    def __str__(self):
        return f"{self.get_kind_display()}"


class SeasonalAvailability(TimeStampedModel):
    """AD 2.7 Seasonal availability – clearing."""
    aerodrome = models.OneToOneField(
        Aerodrome, on_delete=models.CASCADE,
        related_name="seasonal_availability")
    clearing_equipment = models.TextField(blank=True)
    clearance_priorities = models.TextField(blank=True)
    remarks = models.TextField(blank=True)

    class Meta:
        verbose_name = "AD 2.7 – Seasonal availability"

    def __str__(self):
        return f"AD 2.7 – {self.aerodrome.icao_code}"


class Apron(TimeStampedModel):
    """AD 2.8 – Aprons."""
    aerodrome = models.ForeignKey(
        Aerodrome, on_delete=models.CASCADE, related_name="aprons")
    designator = models.CharField(max_length=20, blank=True)
    surface = models.CharField(max_length=60, blank=True)
    strength = models.CharField("Strength (PCR)", max_length=60, blank=True)
    dimensions = models.CharField(max_length=60, blank=True)
    remarks = models.TextField(blank=True)

    class Meta:
        ordering = ("designator",)
        verbose_name = "AD 2.8 – Apron"

    def __str__(self):
        return f"Apron {self.designator or '-'}"


class Taxiway(TimeStampedModel):
    """AD 2.8 – Taxiways."""
    aerodrome = models.ForeignKey(
        Aerodrome, on_delete=models.CASCADE, related_name="taxiways")
    designator = models.CharField(max_length=40)
    width_m = models.DecimalField(max_digits=5, decimal_places=1,
                                  null=True, blank=True)
    surface = models.CharField(max_length=60, blank=True)
    strength = models.CharField("Strength (PCR)", max_length=60, blank=True)
    shoulders_m = models.DecimalField(max_digits=5, decimal_places=1,
                                      null=True, blank=True)
    remarks = models.TextField(blank=True)

    class Meta:
        ordering = ("designator",)
        verbose_name = "AD 2.8 – Taxiway"

    def __str__(self):
        return f"TWY {self.designator}"


class CheckLocation(TimeStampedModel):
    """AD 2.8 – Altimeter / VOR / INS check locations."""
    class Kind(models.TextChoices):
        ALTIMETER = "ALTIMETER", "Altimeter checkpoint"
        VOR = "VOR", "VOR checkpoint"
        INS = "INS", "INS checkpoint"

    aerodrome = models.ForeignKey(
        Aerodrome, on_delete=models.CASCADE,
        related_name="check_locations")
    kind = models.CharField(max_length=10, choices=Kind.choices)
    location = models.CharField(max_length=120, blank=True)
    elevation = models.CharField(max_length=40, blank=True)
    remarks = models.TextField(blank=True)

    class Meta:
        verbose_name = "AD 2.8 – Check location"

    def __str__(self):
        return f"{self.get_kind_display()} – {self.location}"


class SurfaceMovementGuidance(TimeStampedModel):
    """AD 2.9 Surface movement guidance and control system and markings."""
    aerodrome = models.OneToOneField(
        Aerodrome, on_delete=models.CASCADE, related_name="smgcs")
    stand_id_signs = models.TextField(blank=True)
    twy_guidelines = models.TextField(blank=True)
    parking_guidance = models.TextField(blank=True)
    rwy_markings = models.TextField(blank=True)
    twy_markings = models.TextField(blank=True)
    rwy_lights = models.TextField(blank=True)
    twy_lights = models.TextField(blank=True)
    stop_bars = models.TextField(blank=True)
    remarks = models.TextField(blank=True)

    class Meta:
        verbose_name = "AD 2.9 – SMGCS & markings"

    def __str__(self):
        return f"AD 2.9 – {self.aerodrome.icao_code}"


class MeteorologicalService(TimeStampedModel):
    """AD 2.11 Meteorological information provided."""
    aerodrome = models.OneToOneField(
        Aerodrome, on_delete=models.CASCADE,
        related_name="met_service")
    associated_met_office = models.CharField(max_length=120, blank=True)
    hours_of_service = models.CharField(max_length=60, blank=True)
    met_office_outside_hours = models.CharField(max_length=120, blank=True)
    taf_office = models.CharField(max_length=160, blank=True)
    validity_periods = models.CharField(max_length=120, blank=True)
    trend_forecast = models.CharField(max_length=160, blank=True)
    briefing_provided = models.TextField(blank=True)
    flight_documentation = models.TextField(blank=True)
    charts_available = models.TextField(blank=True)
    supplementary_equipment = models.TextField(blank=True)
    ats_units_provided = models.CharField(max_length=80, blank=True)
    remarks = models.TextField(blank=True)

    class Meta:
        verbose_name = "AD 2.11 – Meteorological information"

    def __str__(self):
        return f"AD 2.11 – {self.aerodrome.icao_code}"


class Runway(TimeStampedModel, LatLonMixin):
    """AD 2.12 Runway physical characteristics (one row per runway end/designator)."""
    aerodrome = models.ForeignKey(
        Aerodrome, on_delete=models.CASCADE, related_name="runways")
    designator = models.CharField(
        max_length=6, help_text="e.g. '05', '23', '08L'")
    paired_designator = models.CharField(
        max_length=6, blank=True,
        help_text="Opposite end, e.g. '23' when designator is '05'")
    true_bearing = models.DecimalField(max_digits=5, decimal_places=1,
                                       null=True, blank=True)
    length_m = models.DecimalField(max_digits=7, decimal_places=1,
                                   null=True, blank=True)
    width_m = models.DecimalField(max_digits=6, decimal_places=1,
                                  null=True, blank=True)
    strength = models.CharField("Strength (PCR)", max_length=60, blank=True)
    surface = models.CharField(max_length=80, blank=True)

    # THR
    thr_latitude = models.DecimalField(max_digits=9, decimal_places=6,
                                       null=True, blank=True)
    thr_longitude = models.DecimalField(max_digits=9, decimal_places=6,
                                        null=True, blank=True)
    thr_elevation_m = models.DecimalField(max_digits=7, decimal_places=2,
                                          null=True, blank=True)
    # RWY end
    end_latitude = models.DecimalField(max_digits=9, decimal_places=6,
                                       null=True, blank=True)
    end_longitude = models.DecimalField(max_digits=9, decimal_places=6,
                                        null=True, blank=True)
    end_elevation_m = models.DecimalField(max_digits=7, decimal_places=2,
                                          null=True, blank=True)
    # Autres
    thr_geoid_undulation = models.CharField(max_length=40, blank=True,
                                            default="NIL")
    tdz_elevation_m = models.DecimalField(max_digits=7, decimal_places=2,
                                          null=True, blank=True)
    slope = models.CharField(max_length=40, blank=True)
    swy_dimensions = models.CharField("SWY dimensions (M)", max_length=60,
                                      blank=True)
    cwy_dimensions = models.CharField("CWY dimensions (M)", max_length=60,
                                      blank=True)
    strip_dimensions = models.CharField("Strip dimensions (M)", max_length=60,
                                        blank=True)
    resa = models.CharField("RESA (M)", max_length=60, blank=True)
    ofz = models.CharField("OFZ", max_length=60, blank=True)
    remarks = models.TextField(blank=True)

    class Meta:
        ordering = ("designator",)
        unique_together = ("aerodrome", "designator")
        verbose_name = "AD 2.12 – Runway"

    def __str__(self):
        return f"RWY {self.designator} – {self.aerodrome.icao_code}"

    # ---------- propriétés DMS ----------  ⬅ RESTAURÉES
    @property
    def thr_coordinates_dms(self):
        from common.utils import dd_pair_to_dms_string
        return dd_pair_to_dms_string(self.thr_latitude, self.thr_longitude)

    @property
    def end_coordinates_dms(self):
        from common.utils import dd_pair_to_dms_string
        return dd_pair_to_dms_string(self.end_latitude, self.end_longitude)


class DeclaredDistance(TimeStampedModel):
    """AD 2.13 Declared distances."""
    runway = models.OneToOneField(
        Runway, on_delete=models.CASCADE,
        related_name="declared_distance")
    tora = models.PositiveIntegerField("TORA (m)", null=True, blank=True)
    toda = models.PositiveIntegerField("TODA (m)", null=True, blank=True)
    asda = models.PositiveIntegerField("ASDA (m)", null=True, blank=True)
    lda = models.PositiveIntegerField("LDA (m)", null=True, blank=True)
    remarks = models.TextField(blank=True)

    class Meta:
        verbose_name = "AD 2.13 – Declared distances"

    def __str__(self):
        return f"DD RWY {self.runway.designator}"


class RunwayLighting(TimeStampedModel):
    """AD 2.14 Approach and runway lighting."""
    runway = models.OneToOneField(
        Runway, on_delete=models.CASCADE, related_name="lighting")
    apch_lgt_type = models.CharField(max_length=80, blank=True)
    apch_lgt_length = models.CharField(max_length=40, blank=True)
    apch_lgt_intensity = models.CharField(max_length=40, blank=True)
    thr_lgt_color = models.CharField(max_length=40, blank=True)
    wbar = models.CharField(max_length=40, blank=True)
    vasis_type = models.CharField(max_length=60, blank=True)
    vasis_meht = models.CharField(max_length=40, blank=True)
    papi_angle = models.CharField(max_length=40, blank=True)
    tdz_lgt_length = models.CharField(max_length=60, blank=True)
    rcl_lgt = models.CharField(max_length=160, blank=True)
    rwy_edge_lgt = models.CharField(max_length=160, blank=True)
    rwy_end_lgt = models.CharField(max_length=80, blank=True)
    swy_lgt = models.CharField(max_length=80, blank=True)
    remarks = models.TextField(blank=True)

    class Meta:
        verbose_name = "AD 2.14 – Approach and runway lighting"

    def __str__(self):
        return f"Lighting RWY {self.runway.designator}"


class OtherLighting(TimeStampedModel):
    """AD 2.15 Other lighting and secondary power supply."""
    aerodrome = models.OneToOneField(
        Aerodrome, on_delete=models.CASCADE,
        related_name="other_lighting")
    abn_location = models.CharField(max_length=120, blank=True)
    abn_characteristics = models.CharField(max_length=120, blank=True)
    abn_hours = models.CharField(max_length=80, blank=True)
    ldi = models.CharField("LDI location and lighting", max_length=160,
                            blank=True)
    anemometer = models.CharField(max_length=160, blank=True)
    twy_edge_lights = models.CharField(max_length=80, blank=True)
    twy_centre_line_lights = models.CharField(max_length=80, blank=True)
    secondary_power = models.CharField(max_length=160, blank=True)
    switch_over_time = models.CharField(max_length=60, blank=True)
    remarks = models.TextField(blank=True)

    class Meta:
        verbose_name = "AD 2.15 – Other lighting"

    def __str__(self):
        return f"AD 2.15 – {self.aerodrome.icao_code}"


class HelicopterLandingArea(TimeStampedModel):
    """AD 2.16 Helicopter landing area."""
    aerodrome = models.OneToOneField(
        Aerodrome, on_delete=models.CASCADE, related_name="helipad")
    tloF_coordinates = models.CharField(
        "TLOF / THR FATO coordinates", max_length=120, blank=True)
    geoid_undulation = models.CharField(max_length=40, blank=True)
    tloF_elevation = models.CharField(
        "TLOF / FATO elevation", max_length=40, blank=True)
    area_dimensions = models.CharField(max_length=120, blank=True)
    surface = models.CharField(max_length=60, blank=True)
    strength = models.CharField(max_length=60, blank=True)
    marking = models.CharField(max_length=60, blank=True)
    true_bearings = models.CharField(max_length=60, blank=True)
    declared_distance = models.CharField(max_length=60, blank=True)
    app_fato_lighting = models.CharField(max_length=120, blank=True)
    remarks = models.TextField(blank=True)

    class Meta:
        verbose_name = "AD 2.16 – Helicopter landing area"

    def __str__(self):
        return f"AD 2.16 – {self.aerodrome.icao_code}"


class TextSection(TimeStampedModel):
    """Free-text paragraphs: AD 2.20, 2.21, 2.22, 2.23 (et futurs)."""
    class Section(models.TextChoices):
        LOCAL_REGULATIONS = "2.20", "AD 2.20 – Local aerodrome regulations"
        NOISE_ABATEMENT = "2.21", "AD 2.21 – Noise abatement procedures"
        FLIGHT_PROCEDURES = "2.22", "AD 2.22 – Flight procedures"
        ADDITIONAL_INFO = "2.23", "AD 2.23 – Additional information"
        OTHER = "OTHER", "Other"

    aerodrome = models.ForeignKey(
        Aerodrome, on_delete=models.CASCADE,
        related_name="text_sections")
    section = models.CharField(max_length=6, choices=Section.choices)
    content = models.TextField(blank=True, default="NIL")
    remarks = models.TextField(blank=True)

    class Meta:
        ordering = ("section",)
        unique_together = ("aerodrome", "section")
        verbose_name = "AD 2.20–2.23 – Text section"

    def __str__(self):
        return f"{self.get_section_display()} – {self.aerodrome.icao_code}"