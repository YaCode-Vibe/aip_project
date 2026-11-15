"""Sérialisation inverse de import_aerodrome() : Aerodrome → dict.

Le format produit est strictement compatible avec ad/services/importer.py
(round-trip garanti).

Toutes les sections AD 1.x et AD 2.x sont couvertes :
    AD 1.1, 1.2, 1.4, 1.5
    AD 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 2.9, 2.10, 2.11,
    AD 2.12, 2.13, 2.14, 2.15, 2.16, 2.17, 2.18, 2.19, 2.20–2.23, 2.24
"""
from ad.models import (AerodromeCertificate, AerodromeConditionOfUse,
                       AerodromeGroup, Apron, CheckLocation, DeclaredDistance,
                       HandlingService, HelicopterLandingArea,
                       MeteorologicalService, OperationalHours, OtherLighting,
                       PassengerFacility, RescueFirefighting, Runway,
                       RunwayLighting, SeasonalAvailability, SnowPlan,
                       SurfaceMovementGuidance, Taxiway, TextSection)
from common.models import Obstacle


# ===========================================================================
# Helpers
# ===========================================================================
def _flt(v):
    """Décimal → float (pour JSON)."""
    return float(v) if v is not None else None


def _dec(v):
    """Décimal → str (préserve la précision des coordonnées)."""
    return str(v) if v is not None else None


def _str(v):
    """Renvoie '' si None pour éviter les None là où on attend du texte."""
    return v if v is not None else ""


# ===========================================================================
# Sérialisation principale
# ===========================================================================
def aerodrome_to_dict(ad):
    """Retourne un dict identique à un élément de AERODROMES (aip_algeria.py)."""

    # ----------------------------------------------------------------- AD 1.4
    groups = list(ad.groups.values_list("code", flat=True)) if hasattr(ad, "groups") else []

    # ----------------------------------------------------------------- AD 2.1 / 2.2
    data = {
        "icao": ad.icao_code,
        "name": ad.name,
        "city": _str(ad.city),
        "arp_lat": _dec(ad.latitude),
        "arp_lon": _dec(ad.longitude),
        "arp_site": _str(ad.arp_site),
        "dist_city": _str(ad.distance_from_city),
        "elev": _flt(ad.elevation_m),
        "ref_temp": _flt(ad.reference_temperature_c),
        "geoid": ad.geoid_undulation or "NIL",
        "mag_var": _flt(ad.magnetic_variation_deg),
        "mag_var_year": ad.magnetic_variation_year,
        "annual_change": _flt(ad.annual_change_deg),
        # NOUVEAU AD 2.2.6 – Administration
        "address": _str(ad.address),
        "telefax": _str(ad.telefax),
        "telex": _str(ad.telex),
        "traffic": ad.traffic_type,
        "type": ad.aerodrome_type,
        "remarks": _str(ad.remarks),

        # AD 1.4 – Groupes (liste de codes)
        "groups": groups,

        # AD 2.2 – Liste des contacts structurés
        "contacts": [(c.role, c.value) for c in ad.contacts.all()],

        # AD 2.3 – Operational hours
        "hours": [(h.service, h.hours_text) for h in ad.operational_hours.all()],

        # AD 2.5 – Passenger facilities
        "passenger": [
            {"kind": p.kind, "description": _str(p.description), "remarks": _str(p.remarks)}
            for p in ad.passenger_facilities.all()
        ],

        # AD 2.8 – Aprons
        "aprons": [
            {
                "designator": _str(a.designator),
                "surface": _str(a.surface),
                "strength": _str(a.strength),
                "dimensions": _str(a.dimensions),
                "remarks": _str(a.remarks),
            }
            for a in ad.aprons.all()
        ],

        # AD 2.8 – Taxiways
        "taxiways": [
            {
                "designator": _str(t.designator),
                "width_m": _flt(t.width_m),
                "surface": _str(t.surface),
                "strength": _str(t.strength),
                "shoulders_m": _flt(t.shoulders_m),
                "remarks": _str(t.remarks),
            }
            for t in ad.taxiways.all()
        ],

        # AD 2.8 – Check locations
        "check_locations": [
            {"kind": ck.kind, "location": _str(ck.location),
             "elevation": _str(ck.elevation), "remarks": _str(ck.remarks)}
            for ck in ad.check_locations.all()
        ],

        # AD 2.10 – Obstacles
        "obstacles": [
            {
                "id": _str(o.obst_id),
                "area": o.area,
                "type": _str(o.obstacle_type),
                "lat": _dec(o.latitude),
                "lon": _dec(o.longitude),
                "position_text": _str(o.position_text),
                "elev": _flt(o.elevation_m),
                "hgt": _flt(o.height_m),
                "marking": _str(o.markings),
                "lighting": _str(o.lighting),
                "remarks": _str(o.remarks),
            }
            for o in ad.obstacles.all()
        ],

        # AD 2.18 – Communication facilities
        "comms": [
            {"service": c.service, "call_sign": _str(c.call_sign),
             "frequency": _str(c.frequency),
             "hours": _str(c.hours_of_operation),
             "remarks": _str(c.remarks)}
            for c in ad.comms.all()
        ],

        # AD 2.19 – Radio navigation and landing aids
        "navaids": [
            {
                "aid_type": n.aid_type,
                "designator": _str(n.designator),
                "frequency": _str(n.frequency),
                "hours": _str(n.hours_of_operation),
                "latitude": _dec(n.latitude),
                "longitude": _dec(n.longitude),
                "elevation_m": _flt(n.elevation_m),
                "mag_var": _str(n.magnetic_variation),
                "remarks": _str(n.remarks),
            }
            for n in ad.navaids.all()
        ],

        # AD 2.20–2.23 – Textes libres
        "texts": {t.section: t.content for t in ad.text_sections.all()},

        # AD 2.24 – Charts
        "charts": [
            {
                "chart_type": c.chart_type,
                "title": _str(c.title),
                "reference": _str(c.reference),
                "file": c.file.url if c.file else None,
                "effective_date": c.effective_date.isoformat() if c.effective_date else None,
                "remarks": _str(c.remarks),
            }
            for c in ad.charts.all()
        ],

        # Listes vides à remplir plus bas
        "runways": [],
    }

    # ----------------------------------------------------------------- AD 2.4
    if hasattr(ad, "handling"):
        h = ad.handling
        data["handling"] = {
            "cargo": _str(h.cargo_facilities),
            "fuel": _str(h.fuel_types),
            "fueling": _str(h.fueling_facilities),
            "deicing": _str(h.deicing_facilities),
            "hangar": _str(h.hangar_space),
            "repair": _str(h.repair_facilities),
            "remarks": _str(h.remarks),
        }

    # ----------------------------------------------------------------- AD 2.6
    if hasattr(ad, "rffs"):
        r = ad.rffs
        data["rffs"] = {
            "category": _str(r.category),
            "equipment": _str(r.rescue_equipment),
            "removal": _str(r.removal_capability),
            "remarks": _str(r.remarks),
        }

    # ----------------------------------------------------------------- AD 2.7
    if hasattr(ad, "seasonal_availability"):
        s = ad.seasonal_availability
        data["seasonal"] = {
            "equipment": _str(s.clearing_equipment),
            "priorities": _str(s.clearance_priorities),
            "remarks": _str(s.remarks),
        }

    # ----------------------------------------------------------------- AD 2.9
    if hasattr(ad, "smgcs"):
        s = ad.smgcs
        data["smgcs"] = {
            "id_signs": _str(s.stand_id_signs),
            "twy_guidelines": _str(s.twy_guidelines),
            "parking": _str(s.parking_guidance),
            "rwy_markings": _str(s.rwy_markings),
            "twy_markings": _str(s.twy_markings),
            "rwy_lights": _str(s.rwy_lights),
            "twy_lights": _str(s.twy_lights),
            "stop_bars": _str(s.stop_bars),
            "remarks": _str(s.remarks),
        }

    # ----------------------------------------------------------------- AD 2.11
    if hasattr(ad, "met_service"):
        m = ad.met_service
        data["met"] = {
            "office": _str(m.associated_met_office),
            "hours": _str(m.hours_of_service),
            "outside_hours": _str(m.met_office_outside_hours),
            "taf_office": _str(m.taf_office),
            "validity": _str(m.validity_periods),
            "trend": _str(m.trend_forecast),
            "briefing": _str(m.briefing_provided),
            "documentation": _str(m.flight_documentation),
            "charts": _str(m.charts_available),
            "equipment": _str(m.supplementary_equipment),
            "ats_units": _str(m.ats_units_provided),
            "remarks": _str(m.remarks),
        }

    # ----------------------------------------------------------------- AD 2.15
    if hasattr(ad, "other_lighting"):
        ol = ad.other_lighting
        data["other_lighting"] = {
            "abn_location": _str(ol.abn_location),
            "abn_characteristics": _str(ol.abn_characteristics),
            "abn_hours": _str(ol.abn_hours),
            "ldi": _str(ol.ldi),
            "anemometer": _str(ol.anemometer),
            "twy_edge_lights": _str(ol.twy_edge_lights),
            "twy_centre_line_lights": _str(ol.twy_centre_line_lights),
            "secondary_power": _str(ol.secondary_power),
            "switch_over": _str(ol.switch_over_time),
            "remarks": _str(ol.remarks),
        }

    # ----------------------------------------------------------------- AD 2.16
    if hasattr(ad, "helipad"):
        hp = ad.helipad
        data["helipad"] = {
            "tloF_coordinates": _str(hp.tloF_coordinates),
            "geoid": _str(hp.geoid_undulation),
            "tloF_elevation": _str(hp.tloF_elevation),
            "dimensions": _str(hp.area_dimensions),
            "surface": _str(hp.surface),
            "strength": _str(hp.strength),
            "marking": _str(hp.marking),
            "true_bearings": _str(hp.true_bearings),
            "declared_distance": _str(hp.declared_distance),
            "app_fato_lighting": _str(hp.app_fato_lighting),
            "remarks": _str(hp.remarks),
        }

    # ----------------------------------------------------------------- AD 2.17
    asp = ad.airspaces.first()
    if asp:
        data["airspace"] = {
            "kind": asp.kind,
            "designation": _str(asp.designation),
            "lateral": _str(asp.lateral_limits),
            "upper": _str(asp.vertical_limits_upper),
            "lower": _str(asp.vertical_limits_lower),
            "class": _str(asp.airspace_class),
            "unit": _str(asp.ats_unit_call_sign),
            "lang": _str(asp.languages),
            "trans_alt": _str(asp.transition_altitude),
            "remarks": _str(asp.remarks),
        }

    # ----------------------------------------------------------------- AD 1.1
    if hasattr(ad, "condition_of_use"):
        c = ad.condition_of_use
        data["condition_of_use"] = {
            "availability": _str(c.availability),
            "conditions": _str(c.conditions_of_use),
            "remarks": _str(c.remarks),
        }

    # ----------------------------------------------------------------- AD 1.2
    if hasattr(ad, "snow_plan"):
        sp = ad.snow_plan
        data["snow_plan"] = {
            "equipment": _str(sp.clearing_equipment),
            "priorities": _str(sp.clearance_priorities),
            "remarks": _str(sp.remarks),
        }

    # ----------------------------------------------------------------- AD 1.5
    if hasattr(ad, "certificate"):
        cert = ad.certificate
        data["certificate"] = {
            "number": _str(cert.certificate_number),
            "status": cert.status,
            "issue_date": cert.issue_date.isoformat() if cert.issue_date else None,
            "expiry_date": cert.expiry_date.isoformat() if cert.expiry_date else None,
            "scope": _str(cert.scope),
            "remarks": _str(cert.remarks),
        }

    # ----------------------------------------------------------------- AD 2.12 + 2.13 + 2.14 (pistes)
    for rwy in ad.runways.all():
        r = {
            "designator": rwy.designator,
            "paired_designator": _str(rwy.paired_designator),
            "true_bearing": _flt(rwy.true_bearing),
            "length_m": _flt(rwy.length_m),
            "width_m": _flt(rwy.width_m),
            "strength": _str(rwy.strength),
            "surface": _str(rwy.surface),
            "thr_latitude": _dec(rwy.thr_latitude),
            "thr_longitude": _dec(rwy.thr_longitude),
            "thr_elevation_m": _flt(rwy.thr_elevation_m),
            "end_latitude": _dec(rwy.end_latitude),
            "end_longitude": _dec(rwy.end_longitude),
            "end_elevation_m": _flt(rwy.end_elevation_m),
            "thr_geoid_undulation": _str(rwy.thr_geoid_undulation),
            "tdz_elevation_m": _flt(rwy.tdz_elevation_m),
            "slope": _str(rwy.slope),
            "swy_dimensions": _str(rwy.swy_dimensions),
            "cwy_dimensions": _str(rwy.cwy_dimensions),
            "strip_dimensions": _str(rwy.strip_dimensions),
            "resa": _str(rwy.resa),
            "ofz": _str(rwy.ofz),
            "remarks": _str(rwy.remarks),
        }

        # AD 2.13
        if hasattr(rwy, "declared_distance"):
            dd = rwy.declared_distance
            r["dd"] = {
                "tora": dd.tora,
                "toda": dd.toda,
                "asda": dd.asda,
                "lda": dd.lda,
                "remarks": _str(dd.remarks),
            }

        # AD 2.14
        if hasattr(rwy, "lighting"):
            lt = rwy.lighting
            r["lighting"] = {
                "apch_type": _str(lt.apch_lgt_type),
                "apch_len": _str(lt.apch_lgt_length),
                "apch_intensity": _str(lt.apch_lgt_intensity),
                "thr_color": _str(lt.thr_lgt_color),
                "wbar": _str(lt.wbar),
                "vasis_type": _str(lt.vasis_type),
                "vasis_meht": _str(lt.vasis_meht),
                "papi": _str(lt.papi_angle),
                "tdz": _str(lt.tdz_lgt_length),
                "rcl": _str(lt.rcl_lgt),
                "edge": _str(lt.rwy_edge_lgt),
                "end": _str(lt.rwy_end_lgt),
                "swy": _str(lt.swy_lgt),
                "remarks": _str(lt.remarks),
            }

        data["runways"].append(r)

    return data


# ===========================================================================
# Complétude (barre de progression)
# ===========================================================================
def coverage(ad):
    """Indique pour chaque section si elle contient des données.

    Returns:
        list[tuple(label, count, is_filled)] — utilisé par
        Aerodrome.coverage_report pour calculer le pourcentage.
    """
    from ad.registry import CHILD_COLLECTIONS, SINGLETON_SECTIONS

    report = []

    # Collections enfants (contacts, hours, runways, obstacles…)
    for slug, (model, label) in CHILD_COLLECTIONS.items():
        if hasattr(ad, slug):
            count = getattr(ad, slug).count()
            report.append((label, count, count > 0))
        else:
            report.append((label, 0, False))

    # Sections 1:1 (rffs, handling, met, smgcs, helipad…)
    for slug, (attr, label) in SINGLETON_SECTIONS.items():
        has = hasattr(ad, attr) and getattr(ad, attr) is not None
        report.append((label, 1 if has else 0, has))

    return report