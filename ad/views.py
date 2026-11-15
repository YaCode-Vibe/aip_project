"""
Vues AIP – Part 3 (AD).

Contenu :
- Aerodrome CRUD (list sans pagination, detail avec couverture, create, update, delete)
- Child collections (create avec upsert générique unique_together, update, delete)
- Sections 1:1 (SectionUpdateView)
- Mini formulaire AD 2.13 (DeclaredDistanceUpdateView)
- Mini formulaire AD 2.14 (RunwayLightingUpdateView)
- Import / Export JSON
- Génération PDF AIP (conforme OACI, dates d'effet AIRAC, change bars)
- Génération ODT (LibreOffice / Word)
- Dashboard AIRAC + publication + gestion cycles
"""
import json
from io import BytesIO

from django import forms
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.dateparse import parse_date
from django.views import View
from django.views.generic import (CreateView, DeleteView, DetailView, FormView,
                                  ListView, TemplateView, UpdateView)

from ad.forms import (
    AerodromeForm,
    AiracCycleForm,
    AiracPublishForm,
    DeclaredDistanceForm,
    ImportForm,
    RunwayLightingForm,
    FORM_CLASSES,                       # registre Model → ModelForm (avec DMS)
)
from ad.models import (
    DeclaredDistance,
    Runway,
    RunwayLighting,
    TextSection,
)
from ad.registry import CHILD_COLLECTIONS, SINGLETON_SECTIONS
from ad.services.airac import (
    get_active_cycle,
    get_draft_cycle,
    preview_all_changes,
    publish_draft_cycle,
)
from ad.services.importer import import_aerodrome
from ad.services.serializer import aerodrome_to_dict
from common.models import Aerodrome, AiracCycle


# ===========================================================================
# Helpers
# ===========================================================================
def _get_form_class(model):
    """Retourne un ModelForm avec conversion DMS si défini dans le registre,
    sinon génère un ModelForm standard (exclude aerodrome)."""
    if model in FORM_CLASSES:
        return FORM_CLASSES[model]
    return forms.modelform_factory(model, exclude=("aerodrome",))


# ===========================================================================
# LIST / SEARCH
# ===========================================================================
class AerodromeListView(ListView):
    """AD 1.3 Index to aerodromes – tous les aérodromes sur une seule page."""
    model = Aerodrome
    template_name = "ad/aerodrome_list.html"
    context_object_name = "aerodromes"
    paginate_by = None

    def get_queryset(self):
        qs = super().get_queryset()
        q = self.request.GET.get("q", "").strip()
        if q:
            qs = (qs.filter(icao_code__icontains=q)
                  | qs.filter(name__icontains=q)
                  | qs.filter(city__icontains=q))
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["q"] = self.request.GET.get("q", "")
        ctx["total"] = Aerodrome.objects.count()
        ctx["is_paginated"] = False
        return ctx


# ===========================================================================
# DETAIL
# ===========================================================================
class AerodromeDetailView(DetailView):
    model = Aerodrome
    template_name = "ad/aerodrome_detail.html"
    context_object_name = "ad"
    slug_field = "icao_code"
    slug_url_kwarg = "icao"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ad = self.object
        ctx["collections"] = {
            slug: (getattr(ad, slug).all(), label)
            for slug, (_, label) in CHILD_COLLECTIONS.items()
            if hasattr(ad, slug)
        }
        ctx["child_labels"] = {
            slug: label for slug, (_, label) in CHILD_COLLECTIONS.items()
        }
        ctx["singleton_labels"] = SINGLETON_SECTIONS
        return ctx


# ===========================================================================
# AERODROME CRUD
# ===========================================================================
class AerodromeCreateView(CreateView):
    model = Aerodrome
    form_class = AerodromeForm
    template_name = "ad/aerodrome_form.html"

    def get_success_url(self):
        messages.success(self.request,
                         f"Aerodrome {self.object.icao_code} created.")
        return reverse("ad:aerodrome_detail",
                       kwargs={"icao": self.object.icao_code})


class AerodromeUpdateView(UpdateView):
    model = Aerodrome
    form_class = AerodromeForm
    template_name = "ad/aerodrome_form.html"
    slug_field = "icao_code"
    slug_url_kwarg = "icao"

    def get_success_url(self):
        messages.success(self.request, "Aerodrome updated.")
        return reverse("ad:aerodrome_detail",
                       kwargs={"icao": self.object.icao_code})


class AerodromeDeleteView(DeleteView):
    model = Aerodrome
    template_name = "ad/confirm_delete.html"
    slug_field = "icao_code"
    slug_url_kwarg = "icao"

    def get_success_url(self):
        messages.warning(self.request, "Aerodrome deleted.")
        return reverse("ad:aerodrome_list")


# ===========================================================================
# CHILD COLLECTIONS
# ===========================================================================
class ChildCreateView(CreateView):
    """Création d'une ligne d'une collection enfant (contacts, heures,
    pistes, obstacles…). Gère automatiquement les contraintes
    unique_together incluant 'aerodrome' via update_or_create."""
    template_name = "ad/section_form.html"

    def dispatch(self, request, *args, **kwargs):
        self.aerodrome = get_object_or_404(Aerodrome, icao_code=kwargs["icao"])
        self.model, self.label = CHILD_COLLECTIONS[kwargs["collection"]]
        self.form_class = _get_form_class(self.model)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(aerodrome=self.aerodrome,
                   section_label=self.label, is_child=True)
        return ctx

    def form_valid(self, form):
        form.instance.aerodrome = self.aerodrome

        # --- Détection des contraintes unique_together contenant 'aerodrome' ---
        unique_together = self.model._meta.unique_together or ()
        if (isinstance(unique_together, tuple)
                and unique_together
                and isinstance(unique_together[0], str)):
            unique_together = [unique_together]

        for constraint in unique_together:
            if "aerodrome" not in constraint:
                continue

            lookup = {"aerodrome": self.aerodrome}
            valid = True
            for field_name in constraint:
                if field_name == "aerodrome":
                    continue
                value = getattr(form.instance, field_name, None)
                if value is None:
                    valid = False
                    break
                lookup[field_name] = value
            if not valid:
                continue

            defaults = {}
            for field in form.instance._meta.fields:
                if field.name in lookup or field.name == "id":
                    continue
                if getattr(field, "auto_now", False) or getattr(field, "auto_now_add", False):
                    continue
                defaults[field.name] = getattr(form.instance, field.name)

            obj, created = self.model.objects.update_or_create(
                **lookup, defaults=defaults
            )
            self.object = obj
            messages.success(
                self.request,
                f"{self.label}: {'créé' if created else 'mis à jour'}.",
            )
            return redirect(self.get_success_url())

        # Aucune contrainte applicable → création classique
        messages.success(self.request, f"{self.label}: record created.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("ad:aerodrome_detail",
                       kwargs={"icao": self.aerodrome.icao_code})


class ChildUpdateView(UpdateView):
    template_name = "ad/section_form.html"

    def dispatch(self, request, *args, **kwargs):
        self.aerodrome = get_object_or_404(Aerodrome, icao_code=kwargs["icao"])
        self.model, self.label = CHILD_COLLECTIONS[kwargs["collection"]]
        self.form_class = _get_form_class(self.model)
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return self.model.objects.filter(aerodrome=self.aerodrome)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(aerodrome=self.aerodrome,
                   section_label=self.label, is_child=True)
        return ctx

    def get_success_url(self):
        messages.success(self.request, f"{self.label}: record updated.")
        return reverse("ad:aerodrome_detail",
                       kwargs={"icao": self.aerodrome.icao_code})


class ChildDeleteView(DeleteView):
    template_name = "ad/confirm_delete.html"

    def dispatch(self, request, *args, **kwargs):
        self.aerodrome = get_object_or_404(Aerodrome, icao_code=kwargs["icao"])
        self.model, self.label = CHILD_COLLECTIONS[kwargs["collection"]]
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return self.model.objects.filter(aerodrome=self.aerodrome)

    def get_success_url(self):
        messages.warning(self.request, f"{self.label}: record deleted.")
        return reverse("ad:aerodrome_detail",
                       kwargs={"icao": self.aerodrome.icao_code})


# ===========================================================================
# SECTIONS 1:1
# ===========================================================================
class SectionUpdateView(UpdateView):
    template_name = "ad/section_form.html"

    def dispatch(self, request, *args, **kwargs):
        self.aerodrome = get_object_or_404(Aerodrome, icao_code=kwargs["icao"])
        attr, self.label = SINGLETON_SECTIONS[kwargs["section"]]
        self.model = self.aerodrome.__class__._meta.get_field(attr).related_model
        self.attr = attr
        self.form_class = _get_form_class(self.model)
        return super().dispatch(request, *args, **kwargs)

    def get_object(self, queryset=None):
        obj, _ = self.model.objects.get_or_create(aerodrome=self.aerodrome)
        return obj

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(aerodrome=self.aerodrome, section_label=self.label)
        return ctx

    def get_success_url(self):
        messages.success(self.request, f"{self.label}: saved.")
        return reverse("ad:aerodrome_detail",
                       kwargs={"icao": self.aerodrome.icao_code})


# ===========================================================================
# AD 2.13 – Declared distances (mini formulaire)
# ===========================================================================
class DeclaredDistanceUpdateView(UpdateView):
    model = DeclaredDistance
    form_class = DeclaredDistanceForm
    template_name = "ad/section_form.html"
    context_object_name = "dd"

    def dispatch(self, request, *args, **kwargs):
        self.aerodrome = get_object_or_404(Aerodrome, icao_code=kwargs["icao"])
        self.runway = get_object_or_404(
            Runway, aerodrome=self.aerodrome, designator=kwargs["des"])
        return super().dispatch(request, *args, **kwargs)

    def get_object(self, queryset=None):
        obj, _ = DeclaredDistance.objects.get_or_create(runway=self.runway)
        return obj

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(
            aerodrome=self.aerodrome,
            section_label=(
                f"AD 2.13 – Declared distances · "
                f"RWY {self.runway.designator} ({self.aerodrome.icao_code})"
            ),
        )
        return ctx

    def form_valid(self, form):
        messages.success(
            self.request,
            f"Distances déclarées RWY {self.runway.designator}: enregistrées.",
        )
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("ad:aerodrome_detail",
                       kwargs={"icao": self.aerodrome.icao_code})


# ===========================================================================
# AD 2.14 – Approach and runway lighting (mini formulaire)
# ===========================================================================
class RunwayLightingUpdateView(UpdateView):
    model = RunwayLighting
    form_class = RunwayLightingForm
    template_name = "ad/section_form.html"
    context_object_name = "lighting"

    def dispatch(self, request, *args, **kwargs):
        self.aerodrome = get_object_or_404(Aerodrome, icao_code=kwargs["icao"])
        self.runway = get_object_or_404(
            Runway, aerodrome=self.aerodrome, designator=kwargs["des"])
        return super().dispatch(request, *args, **kwargs)

    def get_object(self, queryset=None):
        obj, _ = RunwayLighting.objects.get_or_create(runway=self.runway)
        return obj

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(
            aerodrome=self.aerodrome,
            section_label=(
                f"AD 2.14 – Approach and runway lighting · "
                f"RWY {self.runway.designator} ({self.aerodrome.icao_code})"
            ),
        )
        return ctx

    def form_valid(self, form):
        messages.success(
            self.request,
            f"Balisage RWY {self.runway.designator}: enregistré.",
        )
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("ad:aerodrome_detail",
                       kwargs={"icao": self.aerodrome.icao_code})


# ===========================================================================
# EXPORT / IMPORT JSON
# ===========================================================================
class AerodromeExportView(View):
    def get(self, request, icao):
        ad = get_object_or_404(Aerodrome, icao_code=icao)
        data = aerodrome_to_dict(ad)
        resp = JsonResponse(
            data, json_dumps_params={"indent": 2, "ensure_ascii": False})
        resp["Content-Disposition"] = f'attachment; filename="{icao}.json"'
        return resp


class AerodromeExportAllView(View):
    def get(self, request):
        data = [aerodrome_to_dict(ad)
                for ad in Aerodrome.objects.all().order_by("icao_code")]
        resp = JsonResponse(
            data, safe=False,
            json_dumps_params={"indent": 2, "ensure_ascii": False})
        resp["Content-Disposition"] = (
            'attachment; filename="aip_algeria_full.json"')
        return resp


class AerodromeImportView(FormView):
    template_name = "ad/aerodrome_import.html"
    form_class = ImportForm

    def form_valid(self, form):
        raw = form.cleaned_data.get("json_data", "").strip()
        if (upload := form.cleaned_data.get("json_file")):
            raw = upload.read().decode("utf-8")

        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as e:
            messages.error(self.request, f"JSON invalide : {e}")
            return self.form_invalid(form)

        if isinstance(payload, dict):
            payload = [payload]

        ok, fail, errors = 0, 0, []
        for d in payload:
            try:
                import_aerodrome(d)
                ok += 1
            except Exception as e:
                fail += 1
                errors.append(f"{d.get('icao', '?')}: {e}")

        if ok:
            messages.success(self.request,
                             f"{ok} aérodrome(s) importé(s) / mis à jour.")
        if fail:
            messages.warning(self.request,
                             f"{fail} échec(s) : " + " · ".join(errors[:3]))
        return redirect("ad:aerodrome_list")


# ===========================================================================
# PDF AIP (conforme OACI, dates d'effet AIRAC, change bars)
# ===========================================================================
class AerodromePDFView(View):
    """PDF AIP avec dates d'effet AIRAC et change bars N/N-1."""

    def get(self, request, icao):
        from ad.services.pdf_generator import generate_aerodrome_pdf

        ad = get_object_or_404(Aerodrome, icao_code=icao)
        draft = get_draft_cycle()

        # ---------- Cycle N ----------
        if draft:
            airac_ref = draft.code
            eff_date = draft.effective_date or draft.publication_date
        else:
            airac_ref = (ad.last_airac_cycle.code
                         if ad.last_airac_cycle else "NIL")
            if ad.last_airac_cycle:
                eff_date = (ad.last_airac_cycle.effective_date
                            or ad.last_airac_cycle.publication_date)
            else:
                eff_date = None

        # ---------- Cycle N-1 ----------
        if ad.last_airac_cycle:
            prev_ref = ad.last_airac_cycle.code
            prev_eff = (ad.last_airac_cycle.effective_date
                        or ad.last_airac_cycle.publication_date)
        else:
            prev_ref = airac_ref
            prev_eff = eff_date

        # ---------- Overrides via URL ----------
        if request.GET.get("airac"):
            airac_ref = request.GET["airac"]
        if request.GET.get("effective_date"):
            parsed = parse_date(request.GET["effective_date"])
            if parsed:
                eff_date = parsed
        if request.GET.get("prev_effective_date"):
            parsed = parse_date(request.GET["prev_effective_date"])
            if parsed:
                prev_eff = parsed

        try:
            pdf_buffer = generate_aerodrome_pdf(
                ad,
                airac_ref=airac_ref,
                effective_date=eff_date,
                previous_airac_ref=prev_ref,
                previous_effective_date=prev_eff,
            )
        except Exception as e:
            messages.error(request, f"Erreur génération PDF : {e}")
            return redirect("ad:aerodrome_detail", icao=icao)

        response = HttpResponse(pdf_buffer.getvalue(),
                                content_type="application/pdf")
        response["Content-Disposition"] = (
            f'inline; filename="{icao}_AIP_AD2_'
            f'{str(airac_ref).replace("/", "-")}.pdf"'
        )
        return response


# ===========================================================================
# ODT (LibreOffice / Word – édition libre)
# ===========================================================================
class AerodromeODTView(View):
    """Génère et renvoie un fichier ODT modifiable de l'aérodrome
    (toutes les sections AD 2.1 → AD 2.24)."""

    def get(self, request, icao):
        from ad.services.odf_generator import ODTBuilder
        from common.utils import dd_pair_to_dms_string

        ad = get_object_or_404(Aerodrome, icao_code=icao)
        builder = ODTBuilder()

        # ---------------------------------------------------------- AD 2.1
        builder.add_heading(
            f"{ad.icao_code} AD 2.1 AERODROME LOCATION INDICATOR AND NAME")
        builder.add_title_box(f"{ad.icao_code} - {ad.name}")

        # ---------------------------------------------------------- AD 2.2
        contacts = "\n".join(
            [f"{c.get_role_display()}: {c.value}" for c in ad.contacts.all()]
        ) or "NIL"
        builder.add_key_value_table(
            f"{ad.icao_code} AD 2.2 AERODROME GEOGRAPHICAL AND ADMINISTRATIVE DATA",
            [
                {"num": 1, "label": "ARP coordinates and site at AD",
                 "value": f"{ad.coordinates_dms}\n{ad.arp_site or 'NIL'}"},
                {"num": 2, "label": "Direction and distance from (city)",
                 "value": ad.distance_from_city or "NIL"},
                {"num": 3, "label": "Elevation/Reference Temperature",
                 "value": f"{ad.elevation_m or 'NIL'} M / "
                          f"{ad.reference_temperature_c or 'NIL'}°C"},
                {"num": 4, "label": "Geoid undulation at AD ELEV PSN",
                 "value": ad.geoid_undulation or "NIL"},
                {"num": 5, "label": "MAG VAR / Annual change",
                 "value": f"{ad.magnetic_variation_deg or 'NIL'}° "
                          f"({ad.magnetic_variation_year or 'NIL'}) / "
                          f"{ad.annual_change_deg or 'NIL'}°"},
                {"num": 6, "label": "AD Administration, address, telephone, telefax, Telex, AFS",
                 "value": contacts},
                {"num": 7, "label": "Type of traffic (IFR/VFR)",
                 "value": ad.get_traffic_type_display()},
                {"num": 8, "label": "Remarks",
                 "value": ad.remarks or "NIL"},
            ])

        # ---------------------------------------------------------- AD 2.3
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
        by_service = {h.service: h for h in ad.operational_hours.all()}
        rows_2_3 = [
            {"num": i, "label": label,
             "value": (by_service.get(code).hours_text
                       if by_service.get(code) else None) or "NIL"}
            for i, (code, label) in enumerate(services, 1)
        ]
        rows_2_3.append({"num": 12, "label": "Remarks", "value": "NIL"})
        builder.add_key_value_table(
            f"{ad.icao_code} AD 2.3 OPERATIONAL HOURS", rows_2_3)

        # ---------------------------------------------------------- AD 2.4
        h = getattr(ad, "handling", None)
        builder.add_key_value_table(
            f"{ad.icao_code} AD 2.4 HANDLING SERVICES AND FACILITIES",
            [
                {"num": 1, "label": "Cargo handling facilities",
                 "value": (h.cargo_facilities if h else None) or "NIL"},
                {"num": 2, "label": "Fuel and oil types",
                 "value": (h.fuel_types if h else None) or "NIL"},
                {"num": 3, "label": "Fuelling facilities and capacity",
                 "value": (h.fueling_facilities if h else None) or "NIL"},
                {"num": 4, "label": "De-icing facilities",
                 "value": (h.deicing_facilities if h else None) or "NIL"},
                {"num": 5, "label": "Hangar space for visiting aircraft",
                 "value": (h.hangar_space if h else None) or "NIL"},
                {"num": 6, "label": "Repair facilities for visiting aircraft",
                 "value": (h.repair_facilities if h else None) or "NIL"},
                {"num": 7, "label": "Remarks",
                 "value": (h.remarks if h else None) or "NIL"},
            ])

        # ---------------------------------------------------------- AD 2.5
        kinds = [
            ("HOTELS", "Hotels"),
            ("RESTAURANTS", "Restaurants"),
            ("TRANSPORT", "Transportation facilities"),
            ("MEDICAL", "Medical facilities"),
            ("BANK_POST", "Bank and post office"),
            ("TOURIST", "Tourist office"),
        ]
        by_kind = {p.kind: p for p in ad.passenger_facilities.all()}
        rows_2_5 = [
            {"num": i, "label": label,
             "value": (by_kind.get(code).description
                       if by_kind.get(code) else None) or "NIL"}
            for i, (code, label) in enumerate(kinds, 1)
        ]
        rows_2_5.append({"num": 7, "label": "Remarks", "value": "NIL"})
        builder.add_key_value_table(
            f"{ad.icao_code} AD 2.5 PASSENGER FACILITIES", rows_2_5)

        # ---------------------------------------------------------- AD 2.6
        r = getattr(ad, "rffs", None)
        builder.add_key_value_table(
            f"{ad.icao_code} AD 2.6 RESCUE AND FIREFIGHTING SERVICES",
            [
                {"num": 1, "label": "AD category for firefighting",
                 "value": (r.category if r else None) or "NIL"},
                {"num": 2, "label": "Rescue equipment",
                 "value": (r.rescue_equipment if r else None) or "NIL"},
                {"num": 3, "label": "Capability for removal of disabled aircraft",
                 "value": (r.removal_capability if r else None) or "NIL"},
                {"num": 4, "label": "Remarks",
                 "value": (r.remarks if r else None) or "NIL"},
            ])

        # ---------------------------------------------------------- AD 2.7
        s = getattr(ad, "seasonal_availability", None)
        builder.add_key_value_table(
            f"{ad.icao_code} AD 2.7 SEASONAL AVAILABILITY - CLEARING",
            [
                {"num": 1, "label": "Type of clearing equipment",
                 "value": (s.clearing_equipment if s else None) or "NIL"},
                {"num": 2, "label": "Clearance priorities",
                 "value": (s.clearance_priorities if s else None) or "NIL"},
                {"num": 3, "label": "Remarks",
                 "value": (s.remarks if s else None) or "NIL"},
            ])

        # ---------------------------------------------------------- AD 2.8
        aprons_txt = "\n".join([
            f"{a.designator or 'Apron'} – Surface: {a.surface or 'NIL'}, "
            f"Strength: {a.strength or 'NIL'}"
            for a in ad.aprons.all()
        ]) or "NIL"
        taxiways_txt = "\n".join([
            f"{t.designator} – Width: {t.width_m or 'NIL'} M, "
            f"Surface: {t.surface or 'NIL'}, Strength: {t.strength or 'NIL'}"
            for t in ad.taxiways.all()
        ]) or "NIL"
        alts = [c for c in ad.check_locations.all() if c.kind == "ALTIMETER"]
        vors = [c for c in ad.check_locations.all() if c.kind == "VOR"]
        inss = [c for c in ad.check_locations.all() if c.kind == "INS"]
        builder.add_key_value_table(
            f"{ad.icao_code} AD 2.8 APRONS, TAXIWAYS AND CHECK LOCATIONS / POSITION DATA",
            [
                {"num": 1, "label": "Apron surface and strength",
                 "value": aprons_txt},
                {"num": 2, "label": "Taxiway width, surface and strength",
                 "value": taxiways_txt},
                {"num": 3, "label": "Altimeter checkpoint location and elevation",
                 "value": "\n".join([f"{c.location} {c.elevation}"
                                     for c in alts]) or "NIL"},
                {"num": 4, "label": "VOR checkpoints",
                 "value": "\n".join([c.location for c in vors]) or "NIL"},
                {"num": 5, "label": "INS checkpoints",
                 "value": "\n".join([c.location for c in inss]) or "NIL"},
                {"num": 6, "label": "Remarks", "value": "NIL"},
            ])

        # ---------------------------------------------------------- AD 2.9
        s = getattr(ad, "smgcs", None)
        builder.add_key_value_table(
            f"{ad.icao_code} AD 2.9 SURFACE MOVEMENT GUIDANCE AND CONTROL SYSTEM AND MARKINGS",
            [
                {"num": 1,
                 "label": "Use of aircraft stand ID signs, TWY guidelines and visual docking / parking guidance system of aircraft stands",
                 "value": (f"ID signs: {(s.stand_id_signs if s else None) or 'NIL'}  "
                           f"TWY guidelines: {(s.twy_guidelines if s else None) or 'NIL'}  "
                           f"Parking guidance system: {(s.parking_guidance if s else None) or 'NIL'}")},
                {"num": 2, "label": "RWY and TWY markings and LGT",
                 "value": (f"RWY markings: {(s.rwy_markings if s else None) or 'NIL'}  "
                           f"TWY markings: {(s.twy_markings if s else None) or 'NIL'}  "
                           f"RWY lights: {(s.rwy_lights if s else None) or 'NIL'}  "
                           f"TWY lights: {(s.twy_lights if s else None) or 'NIL'}")},
                {"num": 3, "label": "Stop bars",
                 "value": (s.stop_bars if s else None) or "NIL"},
                {"num": 4, "label": "Remarks",
                 "value": (s.remarks if s else None) or "NIL"},
            ])

        # ---------------------------------------------------------- AD 2.10
        builder.add_heading(f"{ad.icao_code} AD 2.10 AERODROME OBSTACLES")
        for sub_label, area in [("Approach and take-off areas", "APPROACH"),
                                ("Circling area and at aerodrome", "CIRCLING")]:
            builder.add_subheading(sub_label)
            obstacles = ad.obstacles.filter(area=area)
            headers = ["OBST ID / Designation", "OBST type", "OBST position",
                       "ELEV/HGT", "Markings / Type, Color", "Remarks"]
            data = []
            for o in obstacles:
                if o.elevation_m and o.height_m:
                    elev_hgt = f"{o.elevation_m}/{o.height_m} M"
                elif o.elevation_m:
                    elev_hgt = f"{o.elevation_m} M"
                elif o.height_m:
                    elev_hgt = f"HGT {o.height_m} M"
                else:
                    elev_hgt = "NIL"
                pos = o.coordinates_dms if o.coordinates_dms != "NIL" else (o.position_text or "NIL")
                data.append([
                    o.obst_id or "NIL",
                    o.obstacle_type or "NIL",
                    pos,
                    elev_hgt,
                    o.markings or "NIL",
                    o.remarks or "NIL",
                ])
            if not data:
                data = [["NIL"] * 6]
            n = len(headers)
            builder._build_table(None, [f"{21.0 / n:.2f}cm"] * n, headers, data)

        # ---------------------------------------------------------- AD 2.11
        m = getattr(ad, "met_service", None)
        met_fields = [
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
        builder.add_key_value_table(
            f"{ad.icao_code} AD 2.11 METEOROLOGICAL INFORMATION PROVIDED",
            [
                {"num": i, "label": label,
                 "value": (getattr(m, field, None) if m else None) or "NIL"}
                for i, (label, field) in enumerate(met_fields, 1)
            ])

        # ---------------------------------------------------------- AD 2.12
        runways = list(ad.runways.all())
        builder.add_multi_column_table(
            f"{ad.icao_code} AD 2.12 RUNWAY PHYSICAL CHARACTERISTICS",
            ["RWY NR", "TRUE BRG", "Dimensions (M)",
             "Strength (PCR) / Surface", "THR coords / elevation",
             "RWY end coords", "THR geoid"],
            [[
                r.designator,
                f"{r.true_bearing or 'NIL'}°",
                (f"{r.length_m} x {r.width_m}"
                 if r.length_m and r.width_m else "NIL"),
                f"{r.strength or 'NIL'}\n{r.surface or ''}",
                f"{r.thr_coordinates_dms}\n{r.thr_elevation_m or 'NIL'} M",
                f"{r.end_coordinates_dms}\n{r.end_elevation_m or 'NIL'} M",
                r.thr_geoid_undulation or "NIL",
            ] for r in runways] or [["NIL"] * 7])

        # ---------------------------------------------------------- AD 2.13
        builder.add_multi_column_table(
            f"{ad.icao_code} AD 2.13 DECLARED DISTANCES",
            ["RWY Designator", "TORA (m)", "TODA (m)", "ASDA (m)",
             "LDA (m)", "Remarks"],
            [[
                r.designator,
                (getattr(r, "declared_distance", None).tora
                 if getattr(r, "declared_distance", None) else "NIL"),
                (getattr(r, "declared_distance", None).toda
                 if getattr(r, "declared_distance", None) else "NIL"),
                (getattr(r, "declared_distance", None).asda
                 if getattr(r, "declared_distance", None) else "NIL"),
                (getattr(r, "declared_distance", None).lda
                 if getattr(r, "declared_distance", None) else "NIL"),
                (getattr(r, "declared_distance", None).remarks
                 if getattr(r, "declared_distance", None) else "NIL"),
            ] for r in runways] or [["NIL"] * 6])

        # ---------------------------------------------------------- AD 2.14
        def _lt(r, attr):
            lt = getattr(r, "lighting", None)
            return (getattr(lt, attr, None) if lt else None) or "NIL"

        builder.add_multi_column_table(
            f"{ad.icao_code} AD 2.14 APPROACH AND RUNWAY LIGHTING",
            ["RWY", "APCH LGT Type LEN INTST", "THR LGT Color WBAR",
             "VASIS (MEHT) PAPI", "TDZ LGT LEN", "RWY Center Line LGT",
             "RWY edge LGT", "RWY end LGT", "SWY LGT", "Remarks"],
            [[
                r.designator,
                f"{_lt(r, 'apch_lgt_type')} {_lt(r, 'apch_lgt_length')}",
                _lt(r, "thr_lgt_color"),
                f"{_lt(r, 'vasis_type')} {_lt(r, 'papi_angle')}",
                _lt(r, "tdz_lgt_length"),
                _lt(r, "rcl_lgt"),
                _lt(r, "rwy_edge_lgt"),
                _lt(r, "rwy_end_lgt"),
                _lt(r, "swy_lgt"),
                _lt(r, "remarks"),
            ] for r in runways] or [["NIL"] * 10])

        # ---------------------------------------------------------- AD 2.15
        ol = getattr(ad, "other_lighting", None)
        def _ol(attr):
            return (getattr(ol, attr, None) if ol else None) or "NIL"
        builder.add_key_value_table(
            f"{ad.icao_code} AD 2.15 OTHER LIGHTING AND SECONDARY POWER SUPPLY",
            [
                {"num": 1,
                 "label": "ABN/BN location, characteristics and hours of operation",
                 "value": " ".join(filter(
                     lambda x: x != "NIL",
                     [_ol("abn_location"), _ol("abn_characteristics"),
                      _ol("abn_hours")])) or "NIL"},
                {"num": 2,
                 "label": "LDI location and lighting Anemometer location and lighting",
                 "value": f"LDI: {_ol('ldi')}  Anemometer: {_ol('anemometer')}"},
                {"num": 3, "label": "TWY edge and centre line lights",
                 "value": " ".join(filter(
                     lambda x: x != "NIL",
                     [_ol("twy_edge_lights"),
                      _ol("twy_centre_line_lights")])) or "NIL"},
                {"num": 4, "label": "Secondary power supply/switch-over time",
                 "value": " ".join(filter(
                     lambda x: x != "NIL",
                     [_ol("secondary_power"),
                      _ol("switch_over_time")])) or "NIL"},
                {"num": 5, "label": "Remarks", "value": _ol("remarks")},
            ])

        # ---------------------------------------------------------- AD 2.16
        hp = getattr(ad, "helipad", None)
        def _hp(attr):
            return (getattr(hp, attr, None) if hp else None) or "NIL"
        builder.add_key_value_table(
            f"{ad.icao_code} AD 2.16 HELICOPTER LANDING AREA",
            [
                {"num": 1,
                 "label": "Coordinates TLOF or THR of FATO Geoid undulation",
                 "value": _hp("tloF_coordinates")},
                {"num": 2, "label": "TLOF and/or FATO elevation (M/FT)",
                 "value": _hp("tloF_elevation")},
                {"num": 3,
                 "label": "TLOF and FATO area dimensions, surface, strength, marking",
                 "value": " ".join(filter(
                     lambda x: x != "NIL",
                     [_hp("area_dimensions"), _hp("surface"),
                      _hp("strength"), _hp("marking")])) or "NIL"},
                {"num": 4, "label": "True bearings of FATO",
                 "value": _hp("true_bearings")},
                {"num": 5, "label": "Declared distance available",
                 "value": _hp("declared_distance")},
                {"num": 6, "label": "APP and FATO lighting",
                 "value": _hp("app_fato_lighting")},
                {"num": 7, "label": "Remarks", "value": _hp("remarks")},
            ])

        # ---------------------------------------------------------- AD 2.17
        a = ad.airspaces.first()
        builder.add_key_value_table(
            f"{ad.icao_code} AD 2.17 ATS AIRSPACE",
            [
                {"num": 1, "label": "Designation and lateral limits",
                 "value": (f"{a.designation}. {a.lateral_limits}"
                           if a else "NIL")},
                {"num": 2, "label": "Vertical limits",
                 "value": (f"{a.vertical_limits_upper or 'NIL'}/"
                           f"{a.vertical_limits_lower or 'NIL'}"
                           if a else "NIL")},
                {"num": 3, "label": "Airspace classification",
                 "value": (a.airspace_class if a else None) or "NIL"},
                {"num": 4, "label": "ATS unit call sign and language(s)",
                 "value": (f"{a.ats_unit_call_sign or ''}, {a.languages or ''}"
                           if a else "NIL")},
                {"num": 5, "label": "Transition altitude",
                 "value": (a.transition_altitude if a else None) or "NIL"},
                {"num": 6, "label": "Remarks",
                 "value": (a.remarks if a else None) or "NIL"},
            ])

        # ---------------------------------------------------------- AD 2.18
        builder.add_multi_column_table(
            f"{ad.icao_code} AD 2.18 ATS COMMUNICATION FACILITIES",
            ["Service designation", "Call sign", "Channel",
             "Hours of operation", "Remarks"],
            [[c.get_service_display(), c.call_sign or "NIL",
              c.frequency or "NIL", c.hours_of_operation or "NIL",
              c.remarks or "NIL"]
             for c in ad.comms.all()] or [["NIL"] * 5])

        # ---------------------------------------------------------- AD 2.19
        builder.add_multi_column_table(
            f"{ad.icao_code} AD 2.19 RADIO NAVIGATION AND LANDING AIDS",
            ["Type of aid", "ID", "Frequency", "Hours",
             "Position", "Elevation DME", "Remarks"],
            [[n.get_aid_type_display(), n.designator or "NIL",
              n.frequency or "NIL", n.hours_of_operation or "NIL",
              n.coordinates_dms,
              n.elevation_m or "NIL", n.remarks or "NIL"]
             for n in ad.navaids.all()] or [["NIL"] * 7])

        # ---------------------------------------------------------- AD 2.20 – 2.23
        texts = {t.section: t.content for t in ad.text_sections.all()}
        for code, title in [
            ("2.20", "LOCAL AERODROME REGULATIONS"),
            ("2.21", "NOISE ABATEMENT PROCEDURES"),
            ("2.22", "FLIGHT PROCEDURES"),
            ("2.23", "ADDITIONAL INFORMATION"),
        ]:
            builder.add_text_block(f"{ad.icao_code} AD {code} {title}:",
                                   texts.get(code, "NIL"))

        # ---------------------------------------------------------- AD 2.24
        builder.add_multi_column_table(
            f"{ad.icao_code} AD 2.24 CHARTS RELATED TO AN AERODROME",
            ["Title", "Reference"],
            [[c.title or "NIL", c.reference or "NIL"]
             for c in ad.charts.all()] or [["NIL", "NIL"]])

        # ---------------------------------------------------------- Réponse
        output = BytesIO()
        builder.save(output)
        output.seek(0)
        response = HttpResponse(
            output.getvalue(),
            content_type="application/vnd.oasis.opendocument.text",
        )
        response["Content-Disposition"] = (
            f'attachment; filename="{icao}_AIP_AD2.odt"'
        )
        return response


# ===========================================================================
# AIRAC – dashboard, publication, cycles
# ===========================================================================
class AiracDashboardView(TemplateView):
    template_name = "ad/airac_dashboard.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["draft"] = get_draft_cycle()
        ctx["active"] = get_active_cycle()
        ctx["changes"] = preview_all_changes()
        ctx["total_aerodromes"] = Aerodrome.objects.count()
        ctx["cycles"] = AiracCycle.objects.order_by("-publication_date")[:15]
        return ctx


class AiracPublishView(FormView):
    template_name = "ad/airac_publish.html"
    form_class = AiracPublishForm

    def dispatch(self, request, *args, **kwargs):
        self.draft = get_draft_cycle()
        if not self.draft:
            messages.error(
                request,
                "Aucun cycle brouillon. Créez-en un d'abord depuis /airac/.")
            return redirect("ad:airac_dashboard")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["draft"] = self.draft
        ctx["changes"] = preview_all_changes()
        return ctx

    def form_valid(self, form):
        try:
            cycle, count = publish_draft_cycle()
            messages.success(
                self.request,
                f"✅ Cycle {cycle.code} publié pour {count} aérodrome(s).",
            )
        except Exception as e:
            messages.error(self.request, f"Erreur : {e}")
        return redirect("ad:airac_dashboard")


class AiracCycleCreateView(CreateView):
    model = AiracCycle
    form_class = AiracCycleForm
    template_name = "ad/airac_cycle_form.html"

    def get_context_data(self, **kwargs):
        from common.airac_calendar import AIRAC_CALENDAR
        ctx = super().get_context_data(**kwargs)
        ctx["airac_calendar_json"] = AIRAC_CALENDAR
        return ctx

    def form_valid(self, form):
        AiracCycle.objects.filter(is_draft=True).update(is_draft=False)
        form.instance.is_draft = True
        form.instance.is_active = False
        messages.success(self.request,
                         f"Brouillon {form.instance.code} créé.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("ad:airac_dashboard")


class AiracCycleUpdateView(UpdateView):
    model = AiracCycle
    form_class = AiracCycleForm
    template_name = "ad/airac_cycle_form.html"

    def get_context_data(self, **kwargs):
        from common.airac_calendar import AIRAC_CALENDAR
        ctx = super().get_context_data(**kwargs)
        ctx["airac_calendar_json"] = AIRAC_CALENDAR
        return ctx

    def get_success_url(self):
        messages.success(self.request, "Cycle mis à jour.")
        return reverse("ad:airac_dashboard")