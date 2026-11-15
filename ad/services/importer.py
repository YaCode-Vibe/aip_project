"""Import JSON vers modèles Django — round-trip 100 % avec aerodrome_to_dict().

Défensif contre les structures JSON malformées :
- sections attendues en dict mais fournies en liste → unwrap ou skip
- listes contenant des non-dicts → skip l'élément
- champs null/vides → valeurs par défaut
"""
from datetime import datetime

from django.db import transaction

from ad.models import (AerodromeCertificate, AerodromeConditionOfUse,
                       AerodromeGroup, Apron, CheckLocation, DeclaredDistance,
                       HandlingService, HelicopterLandingArea,
                       MeteorologicalService, OperationalHours, OtherLighting,
                       PassengerFacility, RescueFirefighting, Runway,
                       RunwayLighting, SeasonalAvailability, SnowPlan,
                       SurfaceMovementGuidance, Taxiway, TextSection)
from common.models import (Aerodrome, Airspace, Chart, CommunicationFacility,
                           ContactPoint, Navaid, Obstacle)


# ===========================================================================
# Helpers
# ===========================================================================
def _parse_date(s):
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _is_h24(text):
    if not text:
        return False
    up = str(text).upper().replace(" ", "")
    return "H24" in up or "H/24" in up


def _extract_icao(data):
    """Extrait le code ICAO (tolère plusieurs noms de clé)."""
    for key in ("icao", "icao_code", "icaoCode", "ICAO", "ICAO_CODE"):
        if key in data and data[key]:
            return str(data[key]).upper().strip()
    raise ValueError(
        "Clé 'icao' manquante. "
        f"Clés présentes : {sorted(data.keys())}"
    )


def _as_dict(obj):
    """Retourne un dict si possible, sinon None.

    - {}         → {}
    - []         → None (vide)
    - [{...}]    → {...} (unwrap liste à 1 élément)
    - [{...},{}] → {...} (prend le 1er, ignore le reste)
    - "chaine"   → None
    - null/None  → None
    """
    if isinstance(obj, dict):
        return obj
    if isinstance(obj, list):
        for item in obj:
            if isinstance(item, dict):
                return item
        return None
    return None


def _as_list(obj):
    """Retourne une liste de dicts (ignore les non-dicts)."""
    if not isinstance(obj, list):
        return []
    return [x for x in obj if isinstance(x, dict)]


def _safe_str(v, default=""):
    """Convertit en str, gère None."""
    return str(v) if v is not None else default
def _normalize_area(value):
    """Normalise le champ area vers les valeurs enum du modèle Obstacle.

    Tolère : case, espaces, label complet, abréviations.
    Retourne 'APPROACH', 'CIRCLING' ou 'ENROUTE'.
    """
    if not value:
        return "CIRCLING"

    up = str(value).upper().strip()

    # Approche / take-off
    if up in ("APPROACH", "APPROACH AND TAKE-OFF AREAS", "TAKE-OFF",
              "APPROACH AND TAKE-OFF", "APP", "APCH"):
        return "APPROACH"

    # En-route
    if up in ("ENROUTE", "EN-ROUTE", "EN ROUTE"):
        return "ENROUTE"

    # Tout le reste → circling (défaut)
    return "CIRCLING"

# ===========================================================================
# Import principal
# ===========================================================================
@transaction.atomic
def import_aerodrome(data):
    if not isinstance(data, dict):
        raise ValueError(f"Objet aérodrome invalide (attendu dict, reçu {type(data).__name__})")

    icao = _extract_icao(data)

    # ================================================================= AD 2.1 / 2.2
    ad, _ = Aerodrome.objects.update_or_create(
        icao_code=icao,
        defaults={
            "name": _safe_str(data.get("name")),
            "city": _safe_str(data.get("city")),
            "latitude": data.get("arp_lat"),
            "longitude": data.get("arp_lon"),
            "arp_site": _safe_str(data.get("arp_site")),
            "distance_from_city": _safe_str(data.get("dist_city")),
            "elevation_m": data.get("elev"),
            "reference_temperature_c": data.get("ref_temp"),
            "geoid_undulation": _safe_str(data.get("geoid")) or "NIL",
            "magnetic_variation_deg": data.get("mag_var"),
            "magnetic_variation_year": data.get("mag_var_year"),
            "annual_change_deg": data.get("annual_change"),
            "address": _safe_str(data.get("address")),
            "telefax": _safe_str(data.get("telefax")),
            "telex": _safe_str(data.get("telex")),
            "traffic_type": data.get("traffic", "IFR/VFR"),
            "aerodrome_type": data.get("type", "CIVIL"),
            "remarks": _safe_str(data.get("remarks")),
        },
    )

    # ================================================================= AD 1.4 – Groupes
    groups_data = data.get("groups") or []
    if isinstance(groups_data, list):
        group_objs = []
        for gcode in groups_data:
            if not gcode:
                continue
            grp, _ = AerodromeGroup.objects.get_or_create(
                code=str(gcode), defaults={"name": str(gcode)})
            group_objs.append(grp)
        ad.groups.set(group_objs)
    else:
        ad.groups.clear()

    # ================================================================= AD 2.2 – Contacts
    ContactPoint.objects.filter(aerodrome=ad).delete()
    for item in (data.get("contacts") or []):
        # Format tuple/list [role, value] ou dict {role, value}
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            role, value = item[0], item[1]
        elif isinstance(item, dict):
            role, value = item.get("role"), item.get("value")
        else:
            continue
        if not role or value is None:
            continue
        ContactPoint.objects.create(aerodrome=ad, role=role, value=str(value))

    # ================================================================= AD 2.3 – Hours
    OperationalHours.objects.filter(aerodrome=ad).delete()
    for item in (data.get("hours") or []):
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            service, hours = item[0], item[1]
        elif isinstance(item, dict):
            service, hours = item.get("service"), item.get("hours_text")
        else:
            continue
        if not service:
            continue
        OperationalHours.objects.create(
            aerodrome=ad, service=service,
            hours_text=_safe_str(hours), is_h24=_is_h24(hours))

    # ================================================================= AD 2.4 – Handling
    if (h := _as_dict(data.get("handling"))):
        HandlingService.objects.update_or_create(
            aerodrome=ad,
            defaults={
                "cargo_facilities": _safe_str(h.get("cargo")),
                "fuel_types": _safe_str(h.get("fuel")),
                "fueling_facilities": _safe_str(h.get("fueling")),
                "deicing_facilities": _safe_str(h.get("deicing")),
                "hangar_space": _safe_str(h.get("hangar")),
                "repair_facilities": _safe_str(h.get("repair")),
                "remarks": _safe_str(h.get("remarks")),
            })

    # ================================================================= AD 2.5 – Passenger
    PassengerFacility.objects.filter(aerodrome=ad).delete()
    for p in _as_list(data.get("passenger")):
        PassengerFacility.objects.create(
            aerodrome=ad, kind=p.get("kind", "OTHER"),
            description=_safe_str(p.get("description")),
            remarks=_safe_str(p.get("remarks")))

    # ================================================================= AD 2.6 – RFFS
    if (r := _as_dict(data.get("rffs"))):
        RescueFirefighting.objects.update_or_create(
            aerodrome=ad,
            defaults={
                "category": _safe_str(r.get("category")),
                "rescue_equipment": _safe_str(r.get("equipment")),
                "removal_capability": _safe_str(r.get("removal")),
                "remarks": _safe_str(r.get("remarks")),
            })

    # ================================================================= AD 2.7 – Seasonal
    if (s := _as_dict(data.get("seasonal"))):
        SeasonalAvailability.objects.update_or_create(
            aerodrome=ad,
            defaults={
                "clearing_equipment": _safe_str(s.get("equipment")),
                "clearance_priorities": _safe_str(s.get("priorities")),
                "remarks": _safe_str(s.get("remarks")),
            })

    # ================================================================= AD 2.8 – Aprons
    Apron.objects.filter(aerodrome=ad).delete()
    for a in _as_list(data.get("aprons")):
        Apron.objects.create(
            aerodrome=ad, designator=_safe_str(a.get("designator")),
            surface=_safe_str(a.get("surface")),
            strength=_safe_str(a.get("strength")),
            dimensions=_safe_str(a.get("dimensions")),
            remarks=_safe_str(a.get("remarks")))

    # ================================================================= AD 2.8 – Taxiways
    Taxiway.objects.filter(aerodrome=ad).delete()
    for t in _as_list(data.get("taxiways")):
        Taxiway.objects.create(
            aerodrome=ad, designator=_safe_str(t.get("designator")),
            width_m=t.get("width_m"),
            surface=_safe_str(t.get("surface")),
            strength=_safe_str(t.get("strength")),
            shoulders_m=t.get("shoulders_m"),
            remarks=_safe_str(t.get("remarks")))

    # ================================================================= AD 2.8 – Check locations
    CheckLocation.objects.filter(aerodrome=ad).delete()
    for ck in _as_list(data.get("check_locations")):
        CheckLocation.objects.create(
            aerodrome=ad, kind=ck.get("kind", "ALTIMETER"),
            location=_safe_str(ck.get("location")),
            elevation=_safe_str(ck.get("elevation")),
            remarks=_safe_str(ck.get("remarks")))

    # ================================================================= AD 2.9 – SMGCS
    if (s := _as_dict(data.get("smgcs"))):
        SurfaceMovementGuidance.objects.update_or_create(
            aerodrome=ad,
            defaults={
                "stand_id_signs": _safe_str(s.get("id_signs")),
                "twy_guidelines": _safe_str(s.get("twy_guidelines")),
                "parking_guidance": _safe_str(s.get("parking")),
                "rwy_markings": _safe_str(s.get("rwy_markings")),
                "twy_markings": _safe_str(s.get("twy_markings")),
                "rwy_lights": _safe_str(s.get("rwy_lights")),
                "twy_lights": _safe_str(s.get("twy_lights")),
                "stop_bars": _safe_str(s.get("stop_bars")),
                "remarks": _safe_str(s.get("remarks")),
            })

    # ================================================================= AD 2.10 – Obstacles
    Obstacle.objects.filter(aerodrome=ad).delete()
    for o in _as_list(data.get("obstacles")):
        Obstacle.objects.create(
            aerodrome=ad, obst_id=_safe_str(o.get("id")),
            area=_normalize_area(o.get("area")),
            obstacle_type=_safe_str(o.get("type")),
            latitude=o.get("lat"), longitude=o.get("lon"),
            position_text=_safe_str(o.get("position_text")),
            elevation_m=o.get("elev"), height_m=o.get("hgt"),
            markings=_safe_str(o.get("marking")),
            lighting=_safe_str(o.get("lighting")),
            remarks=_safe_str(o.get("remarks")))

    # ================================================================= AD 2.11 – MET
    if (m := _as_dict(data.get("met"))):
        MeteorologicalService.objects.update_or_create(
            aerodrome=ad,
            defaults={
                "associated_met_office": _safe_str(m.get("office")),
                "hours_of_service": _safe_str(m.get("hours")),
                "met_office_outside_hours": _safe_str(m.get("outside_hours")),
                "taf_office": _safe_str(m.get("taf_office")),
                "validity_periods": _safe_str(m.get("validity")),
                "trend_forecast": _safe_str(m.get("trend")),
                "briefing_provided": _safe_str(m.get("briefing")),
                "flight_documentation": _safe_str(m.get("documentation")),
                "charts_available": _safe_str(m.get("charts")),
                "supplementary_equipment": _safe_str(m.get("equipment")),
                "ats_units_provided": _safe_str(m.get("ats_units")),
                "remarks": _safe_str(m.get("remarks")),
            })

    # ================================================================= AD 2.12 / 2.13 / 2.14 – Runways
    existing_runways = {r.designator: r for r in ad.runways.all()}
    seen = set()

    for r_data in _as_list(data.get("runways")):
        des = r_data.get("designator")
        if not des:
            continue
        seen.add(des)

        rwy, _ = Runway.objects.update_or_create(
            aerodrome=ad, designator=des,
            defaults={
                "paired_designator": _safe_str(r_data.get("paired_designator")),
                "true_bearing": r_data.get("true_bearing"),
                "length_m": r_data.get("length_m"),
                "width_m": r_data.get("width_m"),
                "strength": _safe_str(r_data.get("strength")),
                "surface": _safe_str(r_data.get("surface")),
                "thr_latitude": r_data.get("thr_latitude"),
                "thr_longitude": r_data.get("thr_longitude"),
                "thr_elevation_m": r_data.get("thr_elevation_m"),
                "end_latitude": r_data.get("end_latitude"),
                "end_longitude": r_data.get("end_longitude"),
                "end_elevation_m": r_data.get("end_elevation_m"),
                "thr_geoid_undulation": _safe_str(r_data.get("thr_geoid_undulation")) or "NIL",
                "tdz_elevation_m": r_data.get("tdz_elevation_m"),
                "slope": _safe_str(r_data.get("slope")),
                "swy_dimensions": _safe_str(r_data.get("swy_dimensions")),
                "cwy_dimensions": _safe_str(r_data.get("cwy_dimensions")),
                "strip_dimensions": _safe_str(r_data.get("strip_dimensions")),
                "resa": _safe_str(r_data.get("resa")),
                "ofz": _safe_str(r_data.get("ofz")),
                "remarks": _safe_str(r_data.get("remarks")),
            })

        # AD 2.13
        if (dd := _as_dict(r_data.get("dd"))):
            DeclaredDistance.objects.update_or_create(
                runway=rwy,
                defaults={
                    "tora": dd.get("tora"), "toda": dd.get("toda"),
                    "asda": dd.get("asda"), "lda": dd.get("lda"),
                    "remarks": _safe_str(dd.get("remarks")),
                })

        # AD 2.14
        if (lt := _as_dict(r_data.get("lighting"))):
            RunwayLighting.objects.update_or_create(
                runway=rwy,
                defaults={
                    "apch_lgt_type": _safe_str(lt.get("apch_type")),
                    "apch_lgt_length": _safe_str(lt.get("apch_len")),
                    "apch_lgt_intensity": _safe_str(lt.get("apch_intensity")),
                    "thr_lgt_color": _safe_str(lt.get("thr_color")),
                    "wbar": _safe_str(lt.get("wbar")),
                    "vasis_type": _safe_str(lt.get("vasis_type")),
                    "vasis_meht": _safe_str(lt.get("vasis_meht")),
                    "papi_angle": _safe_str(lt.get("papi")),
                    "tdz_lgt_length": _safe_str(lt.get("tdz")),
                    "rcl_lgt": _safe_str(lt.get("rcl")),
                    "rwy_edge_lgt": _safe_str(lt.get("edge")),
                    "rwy_end_lgt": _safe_str(lt.get("end")),
                    "swy_lgt": _safe_str(lt.get("swy")),
                    "remarks": _safe_str(lt.get("remarks")),
                })

    for des, rwy in existing_runways.items():
        if des not in seen:
            rwy.delete()

    # ================================================================= AD 2.15 – Other lighting
    if (ol := _as_dict(data.get("other_lighting"))):
        OtherLighting.objects.update_or_create(
            aerodrome=ad,
            defaults={
                "abn_location": _safe_str(ol.get("abn_location")),
                "abn_characteristics": _safe_str(ol.get("abn_characteristics")),
                "abn_hours": _safe_str(ol.get("abn_hours")),
                "ldi": _safe_str(ol.get("ldi")),
                "anemometer": _safe_str(ol.get("anemometer")),
                "twy_edge_lights": _safe_str(ol.get("twy_edge_lights")),
                "twy_centre_line_lights": _safe_str(ol.get("twy_centre_line_lights")),
                "secondary_power": _safe_str(ol.get("secondary_power")),
                "switch_over_time": _safe_str(ol.get("switch_over")),
                "remarks": _safe_str(ol.get("remarks")),
            })

    # ================================================================= AD 2.16 – Helipad
    if (hp := _as_dict(data.get("helipad"))):
        HelicopterLandingArea.objects.update_or_create(
            aerodrome=ad,
            defaults={
                "tloF_coordinates": _safe_str(hp.get("tloF_coordinates")),
                "geoid_undulation": _safe_str(hp.get("geoid")),
                "tloF_elevation": _safe_str(hp.get("tloF_elevation")),
                "area_dimensions": _safe_str(hp.get("dimensions")),
                "surface": _safe_str(hp.get("surface")),
                "strength": _safe_str(hp.get("strength")),
                "marking": _safe_str(hp.get("marking")),
                "true_bearings": _safe_str(hp.get("true_bearings")),
                "declared_distance": _safe_str(hp.get("declared_distance")),
                "app_fato_lighting": _safe_str(hp.get("app_fato_lighting")),
                "remarks": _safe_str(hp.get("remarks")),
            })

    # ================================================================= AD 2.17 – Airspace
    Airspace.objects.filter(aerodrome=ad).delete()
    if (asp := _as_dict(data.get("airspace"))):
        Airspace.objects.create(
            aerodrome=ad, kind=asp.get("kind", "CTR"),
            designation=_safe_str(asp.get("designation")),
            lateral_limits=_safe_str(asp.get("lateral")),
            vertical_limits_upper=_safe_str(asp.get("upper")),
            vertical_limits_lower=_safe_str(asp.get("lower")),
            airspace_class=_safe_str(asp.get("class")),
            ats_unit_call_sign=_safe_str(asp.get("unit")),
            languages=_safe_str(asp.get("lang")),
            transition_altitude=_safe_str(asp.get("trans_alt")),
            remarks=_safe_str(asp.get("remarks")))

    # ================================================================= AD 2.18 – Comms
    CommunicationFacility.objects.filter(aerodrome=ad).delete()
    for c in _as_list(data.get("comms")):
        CommunicationFacility.objects.create(
            aerodrome=ad, service=c.get("service", "OTHER"),
            call_sign=_safe_str(c.get("call_sign")),
            frequency=_safe_str(c.get("frequency")),
            hours_of_operation=_safe_str(c.get("hours")),
            remarks=_safe_str(c.get("remarks")))

    # ================================================================= AD 2.19 – Navaids
    Navaid.objects.filter(aerodrome=ad).delete()
    for n in _as_list(data.get("navaids")):
        Navaid.objects.create(
            aerodrome=ad, aid_type=n.get("aid_type", "OTHER"),
            designator=_safe_str(n.get("designator")),
            frequency=_safe_str(n.get("frequency")),
            hours_of_operation=_safe_str(n.get("hours")),
            latitude=n.get("latitude"), longitude=n.get("longitude"),
            elevation_m=n.get("elevation_m"),
            magnetic_variation=_safe_str(n.get("mag_var")),
            remarks=_safe_str(n.get("remarks")))

    # ================================================================= AD 2.20–2.23 – Textes
    TextSection.objects.filter(aerodrome=ad).delete()
    texts = data.get("texts") or {}
    if isinstance(texts, dict):
        for sec, content in texts.items():
            TextSection.objects.create(
                aerodrome=ad, section=sec, content=_safe_str(content) or "NIL")

    # ================================================================= AD 2.24 – Charts
    existing_charts = {(c.chart_type, c.reference or c.title): c
                       for c in ad.charts.all()}
    seen_charts = set()

    for c_data in _as_list(data.get("charts")):
        ctype = c_data.get("chart_type")
        title = _safe_str(c_data.get("title"))
        ref = _safe_str(c_data.get("reference"))
        key = (ctype, ref or title)
        seen_charts.add(key)

        existing = existing_charts.get(key)
        if existing:
            existing.title = title
            existing.effective_date = _parse_date(c_data.get("effective_date"))
            existing.remarks = _safe_str(c_data.get("remarks"))
            existing.save()
        else:
            Chart.objects.create(
                aerodrome=ad, chart_type=ctype or "OTHER",
                title=title, reference=ref,
                effective_date=_parse_date(c_data.get("effective_date")),
                remarks=_safe_str(c_data.get("remarks")))

    for key, ch in existing_charts.items():
        if key not in seen_charts:
            ch.delete()

    # ================================================================= AD 1.1 – Condition
    if (c := _as_dict(data.get("condition_of_use"))):
        AerodromeConditionOfUse.objects.update_or_create(
            aerodrome=ad,
            defaults={
                "availability": _safe_str(c.get("availability")),
                "conditions_of_use": _safe_str(c.get("conditions")),
                "remarks": _safe_str(c.get("remarks")),
            })

    # ================================================================= AD 1.2 – Snow plan
    if (sp := _as_dict(data.get("snow_plan"))):
        SnowPlan.objects.update_or_create(
            aerodrome=ad,
            defaults={
                "clearing_equipment": _safe_str(sp.get("equipment")),
                "clearance_priorities": _safe_str(sp.get("priorities")),
                "remarks": _safe_str(sp.get("remarks")),
            })

    # ================================================================= AD 1.5 – Certificate
    if (cert := _as_dict(data.get("certificate"))):
        AerodromeCertificate.objects.update_or_create(
            aerodrome=ad,
            defaults={
                "certificate_number": _safe_str(cert.get("number")),
                "status": cert.get("status", "NOT_CERTIFIED"),
                "issue_date": _parse_date(cert.get("issue_date")),
                "expiry_date": _parse_date(cert.get("expiry_date")),
                "scope": _safe_str(cert.get("scope")),
                "remarks": _safe_str(cert.get("remarks")),
            })

    return ad