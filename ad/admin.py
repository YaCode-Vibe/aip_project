from django.contrib import admin
from common.models import (Aerodrome, Airspace, Chart, CommunicationFacility,
                           ContactPoint, Navaid, Obstacle)
from .models import *  # noqa

admin.site.site_header = "AIP Algeria – Administration"
admin.site.site_title = "AIP Algeria"
admin.site.index_title = "Aeronautical Information Publication"


# ---------------------------------------------------------------- inlines
class ContactPointInline(admin.TabularInline):
    model = ContactPoint
    extra = 0


class OperationalHoursInline(admin.TabularInline):
    model = OperationalHours
    extra = 0


class PassengerFacilityInline(admin.TabularInline):
    model = PassengerFacility
    extra = 0


class ApronInline(admin.TabularInline):
    model = Apron
    extra = 0


class TaxiwayInline(admin.TabularInline):
    model = Taxiway
    extra = 0


class ObstacleInline(admin.TabularInline):
    model = Obstacle
    extra = 0
    fk_name = "aerodrome"


class RunwayInline(admin.TabularInline):
    model = Runway
    extra = 0


class AirspaceInline(admin.TabularInline):
    model = Airspace
    extra = 0
    fk_name = "aerodrome"


class CommsInline(admin.TabularInline):
    model = CommunicationFacility
    extra = 0
    fk_name = "aerodrome"


class NavaidInline(admin.TabularInline):
    model = Navaid
    extra = 0
    fk_name = "aerodrome"


class TextSectionInline(admin.TabularInline):
    model = TextSection
    extra = 0


class ChartInline(admin.TabularInline):
    model = Chart
    extra = 0
    fk_name = "aerodrome"


# --------------------------------------------------------------- admin class
@admin.register(Aerodrome)
class AerodromeAdmin(admin.ModelAdmin):
    list_display = ("icao_code", "name", "city", "aerodrome_type",
                    "traffic_type", "elevation_m", "is_operational")
    search_fields = ("icao_code", "name", "city")
    list_filter = ("aerodrome_type", "traffic_type", "is_operational")
    inlines = [
        ContactPointInline, OperationalHoursInline, PassengerFacilityInline,
        ApronInline, TaxiwayInline, ObstacleInline, RunwayInline,
        AirspaceInline, CommsInline, NavaidInline, TextSectionInline, ChartInline,
    ]
    fieldsets = (
        ("AD 2.1 – Identification", {
            "fields": ("icao_code", "name", "city", "aerodrome_type", "traffic_type")}),
        ("AD 2.2 – Geographical & administrative data", {
            "fields": ("latitude", "longitude", "arp_site", "distance_from_city",
                       "elevation_m", "reference_temperature_c", "geoid_undulation",
                       "magnetic_variation_deg", "magnetic_variation_year",
                       "annual_change_deg", "remarks")}),
        ("Status", {"fields": ("is_operational", "airac_cycle")}),
    )


@admin.register(Runway)
class RunwayAdmin(admin.ModelAdmin):
    list_display = ("aerodrome", "designator", "length_m", "width_m", "surface")
    list_filter = ("aerodrome",)
    search_fields = ("designator", "aerodrome__icao_code")


@admin.register(DeclaredDistance)
class DeclaredDistanceAdmin(admin.ModelAdmin):
    list_display = ("runway", "tora", "toda", "asda", "lda")


@admin.register(RunwayLighting)
class RunwayLightingAdmin(admin.ModelAdmin):
    list_display = ("runway", "apch_lgt_type", "papi_angle", "rwy_edge_lgt")


for model in (OperationalHours, HandlingService, PassengerFacility,
              RescueFirefighting, SeasonalAvailability, Apron, Taxiway,
              CheckLocation, SurfaceMovementGuidance, MeteorologicalService,
              OtherLighting, HelicopterLandingArea, TextSection,
              AerodromeConditionOfUse, SnowPlan, AerodromeGroup,
              AerodromeCertificate):
    admin.site.register(model)


@admin.register(Airspace)
class AirspaceAdmin(admin.ModelAdmin):
    list_display = ("kind", "designation", "aerodrome", "airspace_class")
    list_filter = ("kind", "airspace_class")
    search_fields = ("designation",)


@admin.register(Navaid)
class NavaidAdmin(admin.ModelAdmin):
    list_display = ("aid_type", "designator", "frequency", "aerodrome")
    list_filter = ("aid_type",)


@admin.register(Obstacle)
class ObstacleAdmin(admin.ModelAdmin):
    list_display = ("obst_id", "obstacle_type", "area", "aerodrome", "height_m")
    list_filter = ("area", "aerodrome")
    search_fields = ("obst_id", "obstacle_type")


@admin.register(Chart)
class ChartAdmin(admin.ModelAdmin):
    list_display = ("chart_type", "reference", "title", "aerodrome")
    list_filter = ("chart_type",)