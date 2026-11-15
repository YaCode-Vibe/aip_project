"""
Génération PDF AIP – conforme OACI (Doc 8126 / Annexe 15).

Mécanisme AIRAC :
- Version N   : état courant en base (en cours d'édition)
- Version N-1 : instantané JSON figé (previous_snapshot)

Diff automatique section par section :
- champs 1:1 modifiés → change-bar sur toute la section
- listes (contacts, heures, pistes…) → change-bar par ligne
- dicts (textes 2.20–2.23) → change-bar par sous-section

Rendu :
- En-tête  : AIP / ALGERIA  +  AD 2. {ICAO} -{page} / date effective page
- Change bar : trait noir 2pt à gauche de la ligne modifiée
- Pied     : AIS Algeria  +  AIRAC AMDT {ref} (par page)
"""
from io import BytesIO

from django.template.loader import render_to_string
from django.utils import timezone
from weasyprint import CSS, HTML


# ===========================================================================
# Helpers
# ===========================================================================
def _nil(v):
    return "NIL" if v in (None, "") else v


def _join(*parts, sep=" "):
    clean = [str(p) for p in parts if p not in (None, "")]
    return sep.join(clean) if clean else "NIL"


def _related(obj, attr):
    return getattr(obj, attr) if hasattr(obj, attr) else None


# ===========================================================================
# Préparation des sections (identique à la version précédente)
# ===========================================================================
def _rows_hours(ad):
    services = [
        ("AD_ADMIN", "AD administration"),
        ("CUSTOMS", "Customs and immigration"),
        ("HEALTH", "Health and sanitation"),
        ("AIS", "AIS briefing office"),
        ("ARO", "ATS reporting office (ARO)"),
        ("MET", "MET briefing office"),
        ("ATS", "ATS"),
        ("FUELING", "Fueling"),
        ("HANDLING", "Handling"),
        ("SECURITY", "Security"),
        ("DEICING", "De-icing"),
    ]
    by_svc = {h.service: h for h in ad.operational_hours.all()}
    rows = [{"num": i, "label": lbl,
             "value": _nil(by_svc.get(code).hours_text if by_svc.get(code) else None)}
            for i, (code, lbl) in enumerate(services, 1)]
    rows.append({"num": 12, "label": "Remarks", "value": "NIL"})
    return rows


def _rows_passenger(ad):
    kinds = [
        ("HOTELS", "Hotels"), ("RESTAURANTS", "Restaurants"),
        ("TRANSPORT", "Transportation facilities"), ("MEDICAL", "Medical facilities"),
        ("BANK_POST", "Bank and post office"), ("TOURIST", "Tourist office"),
    ]
    by_k = {p.kind: p for p in ad.passenger_facilities.all()}
    rows = [{"num": i, "label": lbl,
             "value": _nil(by_k.get(code).description if by_k.get(code) else None)}
            for i, (code, lbl) in enumerate(kinds, 1)]
    rows.append({"num": 7, "label": "Remarks", "value": "NIL"})
    return rows


def _rows_rffs(ad):
    r = _related(ad, "rffs")
    return [
        {"num": 1, "label": "AD category for firefighting",
         "value": _nil(r.category if r else None)},
        {"num": 2, "label": "Rescue equipment",
         "value": _nil(r.rescue_equipment if r else None)},
        {"num": 3, "label": "Capability for removal of disabled aircraft",
         "value": _nil(r.removal_capability if r else None)},
        {"num": 4, "label": "Remarks", "value": _nil(r.remarks if r else None)},
    ]


def _rows_seasonal(ad):
    s = _related(ad, "seasonal_availability")
    return [
        {"num": 1, "label": "Type of clearing equipment",
         "value": _nil(s.clearing_equipment if s else None)},
        {"num": 2, "label": "Clearance priorities",
         "value": _nil(s.clearance_priorities if s else None)},
        {"num": 3, "label": "Remarks", "value": _nil(s.remarks if s else None)},
    ]


def _rows_smgcs(ad):
    s = _related(ad, "smgcs")
    return [
        {"num": 1,
         "label": "Use of aircraft stand ID signs, TWY guidelines and visual docking / parking guidance system of aircraft stands",
         "value": _join(f"ID signs: {_nil(s.stand_id_signs if s else None)}",
                        f"TWY guidelines: {_nil(s.twy_guidelines if s else None)}",
                        f"Parking guidance system: {_nil(s.parking_guidance if s else None)}",
                        sep="  ")},
        {"num": 2, "label": "RWY and TWY markings and LGT",
         "value": _join(f"RWY markings: {_nil(s.rwy_markings if s else None)}",
                        f"TWY markings: {_nil(s.twy_markings if s else None)}",
                        f"RWY lights: {_nil(s.rwy_lights if s else None)}",
                        f"TWY lights: {_nil(s.twy_lights if s else None)}",
                        sep="  ")},
        {"num": 3, "label": "Stop bars", "value": _nil(s.stop_bars if s else None)},
        {"num": 4, "label": "Remarks", "value": _nil(s.remarks if s else None)},
    ]


def _rows_met(ad):
    m = _related(ad, "met_service")
    fields = [
        ("Associated MET office", "associated_met_office"),
        ("Hours of service MET Office outside hours", "hours_of_service"),
        ("Office responsible for TAF preparation and periods of validity", "taf_office"),
        ("Trend Forecast and Interval of issuance", "trend_forecast"),
        ("Briefing /consultation provided", "briefing_provided"),
        ("Flight documentation and Language(s) used", "flight_documentation"),
        ("Charts and other information available for briefing or consultation", "charts_available"),
        ("Supplementary equipment available for providing Information on meteorological conditions", "supplementary_equipment"),
        ("ATS units provided with meteorological information", "ats_units_provided"),
        ("Remarks", "remarks"),
    ]
    return [{"num": i, "label": lbl,
             "value": _nil(getattr(m, f, None) if m else None)}
            for i, (lbl, f) in enumerate(fields, 1)]


def _rows_other_lighting(ad):
    ol = _related(ad, "other_lighting")
    return [
        {"num": 1, "label": "ABN/BN location, characteristics and hours of operation",
         "value": _join(_nil(ol.abn_location if ol else None),
                        _nil(ol.abn_characteristics if ol else None),
                        _nil(ol.abn_hours if ol else None))},
        {"num": 2, "label": "LDI location and lighting Anemometer location and lighting",
         "value": _join(f"LDI: {_nil(ol.ldi if ol else None)}",
                        f"Anemometer: {_nil(ol.anemometer if ol else None)}")},
        {"num": 3, "label": "TWY edge and centre line lights",
         "value": _join(_nil(ol.twy_edge_lights if ol else None),
                        _nil(ol.twy_centre_line_lights if ol else None))},
        {"num": 4, "label": "Secondary power supply/switch-over time",
         "value": _join(_nil(ol.secondary_power if ol else None),
                        _nil(ol.switch_over_time if ol else None))},
        {"num": 5, "label": "Remarks", "value": _nil(ol.remarks if ol else None)},
    ]


def _rows_helipad(ad):
    h = _related(ad, "helipad")
    return [
        {"num": 1, "label": "Coordinates TLOF or THR of FATO Geoid undulation",
         "value": _nil(h.tloF_coordinates if h else None)},
        {"num": 2, "label": "TLOF and/or FATO elevation (M/FT)",
         "value": _nil(h.tloF_elevation if h else None)},
        {"num": 3, "label": "TLOF and FATO area dimensions, surface, strength, marking",
         "value": _join(_nil(h.area_dimensions if h else None),
                        _nil(h.surface if h else None),
                        _nil(h.strength if h else None),
                        _nil(h.marking if h else None))},
        {"num": 4, "label": "True bearings of FATO",
         "value": _nil(h.true_bearings if h else None)},
        {"num": 5, "label": "Declared distance available",
         "value": _nil(h.declared_distance if h else None)},
        {"num": 6, "label": "APP and FATO lighting",
         "value": _nil(h.app_fato_lighting if h else None)},
        {"num": 7, "label": "Remarks", "value": _nil(h.remarks if h else None)},
    ]


def _rows_airspace(ad):
    a = ad.airspaces.first()
    return [
        {"num": 1, "label": "Designation and lateral limits",
         "value": _join(a.designation if a else None, a.lateral_limits if a else None, sep=". ")},
        {"num": 2, "label": "Vertical limits",
         "value": f"{_nil(a.vertical_limits_upper if a else None)}/"
                  f"{_nil(a.vertical_limits_lower if a else None)}"},
        {"num": 3, "label": "Airspace classification",
         "value": _nil(a.airspace_class if a else None)},
        {"num": 4, "label": "ATS unit call sign and language(s)",
         "value": _join(a.ats_unit_call_sign if a else None,
                        a.languages if a else None, sep=", ")},
        {"num": 5, "label": "Transition altitude",
         "value": _nil(a.transition_altitude if a else None)},
        {"num": 6, "label": "Remarks", "value": _nil(a.remarks if a else None)},
    ]


# ===========================================================================
# DIFF N / N-1
# ===========================================================================
def _diff_section(cur, prev):
    """
    Diff d'une section.
    - listes  → {'changed': bool, 'rows': [idx...]}
    - dicts   → {'changed': bool, 'keys': [key...]}
    - scalaires/1:1 → {'changed': bool, 'rows': []}
    """
    if prev is None:
        # Pas de N-1 : tout est considéré comme non modifié (premier enregistrement)
        return {"changed": False, "rows": [], "keys": []}

    if isinstance(cur, list):
        prev_list = prev if isinstance(prev, list) else []
        rows = [i for i, v in enumerate(cur)
                if i >= len(prev_list) or v != prev_list[i]]
        return {"changed": bool(rows), "rows": rows, "keys": []}

    if isinstance(cur, dict):
        prev_d = prev if isinstance(prev, dict) else {}
        keys = [k for k in cur if cur.get(k) != prev_d.get(k)]
        return {"changed": bool(keys), "rows": [], "keys": keys}

    return {"changed": cur != prev, "rows": [], "keys": []}


def _compute_diff(current_dict, previous_dict):
    """Diff global sur le dict retourné par aerodrome_to_dict().

    Si `previous_dict` est vide (première publication), on renvoie un diff
    vide → aucun change bar. Les pages seront datées uniformément.
    """
    if not previous_dict:
        return {"_any": False, "ad_2_2": {"changed": False}}

    keys_to_check = [
        "contacts", "hours", "handling", "rffs", "seasonal",
        "passenger", "aprons", "taxiways", "check_locations",
        "smgcs", "obstacles", "met", "other_lighting", "helipad",
        "runways", "airspace", "comms", "navaids", "texts", "charts",
    ]
    diff = {}
    any_changed = False
    for k in keys_to_check:
        cur = current_dict.get(k)
        prev = previous_dict.get(k)
        diff[k] = _diff_section(cur, prev)
        if diff[k]["changed"]:
            any_changed = True

    ad22_changed = False
    for f in ("name", "arp_lat", "arp_lon", "arp_site", "dist_city",
              "elev", "ref_temp", "geoid", "mag_var", "mag_var_year",
              "annual_change", "traffic", "type", "remarks"):
        if current_dict.get(f) != previous_dict.get(f):
            ad22_changed = True
            break
    diff["ad_2_2"] = {"changed": ad22_changed, "rows": [], "keys": []}
    if ad22_changed:
        any_changed = True

    diff["_any"] = any_changed
    return diff

# ===========================================================================
# Contexte
# ===========================================================================

def _build_context(ad, diff, airac_date_str, prev_airac_date_str):
    """Construit le contexte du template PDF.

    Obstacles retournés SANS wrapper (instances Obstacle brutes)
    → le template doit utiliser o.obst_id, o.obstacle_type, etc.
    """
    from ad.services.serializer import aerodrome_to_dict
    from common.utils import dd_pair_to_dms_string, dd_to_dms

    # ---- Contacts
    contacts = [f"{c.get_role_display()}: {c.value}" for c in ad.contacts.all()]
    contacts_html = "<br>".join(contacts) if contacts else "NIL"

    # ---- Textes
    texts = {t.section: t.content for t in ad.text_sections.all()}

    # ---- Pistes
    runways = []
    for r in ad.runways.all():
        runways.append({
            "runway": r,
            "dd": _related(r, "declared_distance"),
            "lighting": _related(r, "lighting"),
            "thr_dms": dd_pair_to_dms_string(r.thr_latitude, r.thr_longitude),
            "end_dms": dd_pair_to_dms_string(r.end_latitude, r.end_longitude),
        })

    # ---- Navaids
    navaids_dms = [
        {"obj": n, "coords_dms": dd_pair_to_dms_string(n.latitude, n.longitude)}
        for n in ad.navaids.all()
    ]

    # ---- Obstacles : SANS WRAPPER, filtrage défensif
    obstacles_approach = []
    obstacles_circling = []
    for o in ad.obstacles.all():
        area_norm = (o.area or "").strip().upper()
        if "APPROACH" in area_norm or "TAKE" in area_norm or area_norm == "APP":
            obstacles_approach.append(o)      # instance brute
        else:
            obstacles_circling.append(o)      # instance brute

    # ---- Dates par section
    def d(section_key):
        return (airac_date_str
                if diff.get(section_key, {}).get("changed")
                else prev_airac_date_str)

    return {
        "ad": ad,
        "diff": diff,
        "contacts_html": contacts_html,

        "arp_lat_dms": dd_to_dms(ad.latitude, is_lat=True),
        "arp_lon_dms": dd_to_dms(ad.longitude, is_lat=False),
        "arp_dms":     dd_pair_to_dms_string(ad.latitude, ad.longitude),

        "rows_hours":          _rows_hours(ad),
        "rows_passenger":      _rows_passenger(ad),
        "rows_rffs":           _rows_rffs(ad),
        "rows_seasonal":       _rows_seasonal(ad),
        "rows_smgcs":          _rows_smgcs(ad),
        "rows_met":            _rows_met(ad),
        "rows_other_lighting": _rows_other_lighting(ad),
        "rows_helipad":        _rows_helipad(ad),
        "rows_airspace":       _rows_airspace(ad),

        "aprons":          list(ad.aprons.all()),
        "taxiways":        list(ad.taxiways.all()),
        "check_locations": list(ad.check_locations.all()),

        # ⚠️ Instances brutes — pas de .obj
        "obstacles_approach": obstacles_approach,
        "obstacles_circling": obstacles_circling,

        "runways": runways,
        "comms":   list(ad.comms.all()),
        "navaids": navaids_dms,

        "text_2_20": texts.get("2.20", "NIL"),
        "text_2_21": texts.get("2.21", "NIL"),
        "text_2_22": texts.get("2.22", "NIL"),
        "text_2_23": texts.get("2.23", "NIL"),

        "charts": list(ad.charts.all()),

        # Dates par section
        "d_ad_2_2":         d("ad_2_2"),
        "d_hours":          d("hours"),
        "d_handling":       d("handling"),
        "d_passenger":      d("passenger"),
        "d_rffs":           d("rffs"),
        "d_seasonal":       d("seasonal"),
        "d_aprons":         d("aprons"),
        "d_taxiways":       d("taxiways"),
        "d_smgcs":          d("smgcs"),
        "d_obstacles":      d("obstacles"),
        "d_met":            d("met"),
        "d_runways":        d("runways"),
        "d_lighting":       d("runways"),
        "d_other_lighting": d("other_lighting"),
        "d_helipad":        d("helipad"),
        "d_airspace":       d("airspace"),
        "d_comms":          d("comms"),
        "d_navaids":        d("navaids"),
        "d_texts":          d("texts"),
        "d_charts":         d("charts"),
    }


# ===========================================================================
# CSS
# ===========================================================================
def _build_css(airac_ref, icao):
    return f"""
@page {{
    size: A4 portrait;
    margin: 22mm 8mm 15mm 8mm;

    /* En-tête : running element (table à 2 colonnes, alignement garanti) */
    @top-center {{
        content: element(page-header);
        width: 100%; vertical-align: top; padding: 0; border: none;
    }}

    /* Pied : AMDT dynamique (string-set sur chaque section) */
    @bottom-left {{
        content: "AIS Algeria";
        font-family: Arial, Helvetica, sans-serif;
        font-size: 8pt;
        vertical-align: bottom; padding-bottom: 4pt; text-align: left;
    }}
    @bottom-right {{
        content: "AIRAC AMDT " string(page-amdt, first);
        font-family: Arial, Helvetica, sans-serif;
        font-size: 8pt;
        vertical-align: bottom; padding-bottom: 4pt; text-align: right;
    }}
}}

body {{
    font-family: Arial, Helvetica, sans-serif;
    font-size: 7.5pt;
    color: #000; line-height: 1.18; margin: 0; padding: 0;
}}

/* -------- En-tête running -------- */
.page-header {{
    position: running(page-header);
    width: 100%;
    font-family: Arial, Helvetica, sans-serif;
    font-size: 8pt; font-weight: bold;
    margin: 0; padding: 0;
}}
.page-header table {{ width: 100%; border-collapse: collapse; border: none; margin: 0; padding: 0; }}
.page-header td {{
    border: none !important; padding: 0 !important; margin: 0;
    vertical-align: top; line-height: 10pt;
    font-family: Arial, Helvetica, sans-serif; font-size: 8pt; font-weight: bold;
}}
.ph-left  {{ text-align: left;  width: 50%; }}
.ph-right {{ text-align: right; width: 50%; }}

/* -------- Sections -------- */
.section-block {{
    margin-bottom: 4pt;
    /* Alimente les running headers pour la page courante */
    string-set: page-date attr(data-page-date), page-amdt attr(data-page-amdt);
}}

/* -------- Tables -------- */
table.aip {{ width: 100%; border-collapse: collapse; table-layout: auto; }}
table.aip th, table.aip td {{
    border: 0.5pt solid #000; padding: 1pt 2pt;
    vertical-align: top; text-align: left;
    word-wrap: break-word; overflow-wrap: break-word;
}}
table.aip th.section-heading {{
    text-align: center; font-weight: bold; font-size: 8pt;
    padding: 2pt 3pt; background: #fff;
    text-transform: uppercase; letter-spacing: 0.2pt;
}}
table.aip th.sub-header {{
    text-align: left; font-weight: bold; font-size: 7pt;
    padding: 1.5pt 3pt; background: #f2f2f2; font-style: italic;
}}
table.aip th.col-header {{
    text-align: center; font-weight: bold; font-size: 6.5pt;
    padding: 2pt 1pt; background: #f8f8f8; line-height: 1.1;
}}

/* -------- Colonne numéro 5 mm -------- */
table.aip td.num {{
    width: 5mm; min-width: 5mm; max-width: 5mm;
    text-align: center; font-size: 7pt; padding: 1pt 0.5pt;
    white-space: nowrap; overflow: hidden;
}}
table.aip td.label {{ width: 76mm; min-width: 76mm; }}
table.aip.multi th, table.aip.multi td {{ font-size: 6.5pt; padding: 1pt; }}

/* =========================================================
   CHANGE BAR OACI (trait vertical noir à gauche)
   ========================================================= */
.change-bar,
table.aip td.change-bar,
table.aip tr.change-bar > td:first-child {{
    border-left: 2.5pt solid #000 !important;
    padding-left: 3pt !important;
}}

/* Change bar pour une section entière (1:1) */
.section-block.changed table.aip {{
    border-left: 2.5pt solid #000;
    padding-left: 3pt;
}}

/* Utilitaires */
.center {{ text-align: center; }}
.bold   {{ font-weight: bold; }}
.text-header {{
    font-weight: bold; font-size: 8pt;
    margin: 6pt 0 2pt 0; text-transform: uppercase;
}}
.text-body {{
    font-size: 7.5pt; margin: 0 0 4pt 0; padding: 2pt 3pt;
    border: 0.5pt solid #000; min-height: 10pt;
}}
table.aip tr {{ page-break-inside: avoid; }}
"""


# ===========================================================================
# API principale
# ===========================================================================
# ===========================================================================
# API principale
# ===========================================================================
def generate_aerodrome_pdf(
    ad,
    airac_ref=None,
    effective_date=None,
    previous_airac_ref=None,
    previous_effective_date=None,
):
    """
    Génère le PDF AIP conforme OACI (Doc 8126).

    Convention d'affichage :
    - En-tête de chaque page : **date d'entrée en vigueur** du cycle
      (et non la date de publication/distribution).
    - Pied de page : **numéro AIRAC AMDT** du cycle.

    Args:
        ad                      : instance Aerodrome
        airac_ref               : code du cycle N  ("04/26")
        effective_date          : date d'effet du cycle N (YYYY-MM-DD)
        previous_airac_ref      : code du cycle N-1 ("03/26")
        previous_effective_date : date d'effet du cycle N-1
    """
    from ad.services.serializer import aerodrome_to_dict

    # -------- Résolution des valeurs par défaut --------
    if airac_ref is None:
        airac_ref = (ad.last_airac_cycle.code
                     if ad.last_airac_cycle else "NIL")

    if effective_date is None:
        if ad.last_airac_cycle:
            # Priorité : effective_date → fallback publication_date
            effective_date = (ad.last_airac_cycle.effective_date
                              or ad.last_airac_cycle.publication_date)
        if effective_date is None:
            effective_date = timezone.now().date()

    if previous_airac_ref is None:
        previous_airac_ref = (ad.previous_airac_cycle.code
                              if ad.previous_airac_cycle else "NIL")

    if previous_effective_date is None:
        if ad.previous_airac_cycle:
            previous_effective_date = (
                ad.previous_airac_cycle.effective_date
                or ad.previous_airac_cycle.publication_date
            )
        if previous_effective_date is None:
            # Pas de cycle précédent : on uniformise toutes les pages
            # sur la date d'effet du cycle courant.
            previous_effective_date = effective_date

    # -------- Formatage (ex. "12 NOV 26") --------
    date_str = (effective_date.strftime("%d %b %y").upper()
                if effective_date else "NIL")
    prev_date_str = (previous_effective_date.strftime("%d %b %y").upper()
                     if previous_effective_date else "NIL")

    # -------- Diff N / N-1 --------
    current_dict = aerodrome_to_dict(ad)
    previous_dict = ad.previous_snapshot or {}
    diff = _compute_diff(current_dict, previous_dict)

    # -------- Contexte --------
    context = _build_context(ad, diff, date_str, prev_date_str)
    context["header_date_str"] = date_str
    context["airac_ref"] = airac_ref
    context["prev_airac_ref"] = previous_airac_ref
    context["airac_date_str"] = date_str
    context["prev_airac_date_str"] = prev_date_str

    html_string = render_to_string("ad/aerodrome_pdf.html", context)
    css = CSS(string=_build_css(airac_ref, ad.icao_code))
    pdf_bytes = HTML(string=html_string).write_pdf(stylesheets=[css])

    return BytesIO(pdf_bytes)