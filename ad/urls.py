from django.urls import path
from . import views

app_name = "ad"

urlpatterns = [
    # AD 1.3 – index
    path("", views.AerodromeListView.as_view(), name="aerodrome_list"),

    # AD 2.1 / 2.2 – aerodrome CRUD
    path("aerodromes/new/",
         views.AerodromeCreateView.as_view(), name="aerodrome_create"),
    path("aerodromes/<str:icao>/",
         views.AerodromeDetailView.as_view(), name="aerodrome_detail"),
    path("aerodromes/<str:icao>/edit/",
         views.AerodromeUpdateView.as_view(), name="aerodrome_update"),
    path("aerodromes/<str:icao>/delete/",
         views.AerodromeDeleteView.as_view(), name="aerodrome_delete"),

    # =====================================================================
    # ROUTES SPÉCIFIQUES (doivent être AVANT les routes génériques)
    # =====================================================================
    # AD 2.13 – Declared distances (mini formulaire dédié)
    path("aerodromes/<str:icao>/runways/<str:des>/dd/",
         views.DeclaredDistanceUpdateView.as_view(), name="runway_dd_update"),

    # 1:1 sections  (condition-of-use, rffs, handling, met, smgcs, ...)
    path("aerodromes/<str:icao>/section/<str:section>/",
         views.SectionUpdateView.as_view(), name="section_update"),

    # Child collections (contacts, hours, runways, obstacles, navaids, ...)
    path("aerodromes/<str:icao>/<str:collection>/new/",
         views.ChildCreateView.as_view(), name="child_create"),
    path("aerodromes/<str:icao>/<str:collection>/<int:pk>/edit/",
         views.ChildUpdateView.as_view(), name="child_update"),
    path("aerodromes/<str:icao>/<str:collection>/<int:pk>/delete/",
         views.ChildDeleteView.as_view(), name="child_delete"),

    # =====================================================================
    # EXPORT / IMPORT JSON
    # =====================================================================

    path("import/",
         views.AerodromeImportView.as_view(), name="aerodrome_import"),
    path("export/all/",
         views.AerodromeExportAllView.as_view(), name="export_all"),
    path("export/<str:icao>/",
         views.AerodromeExportView.as_view(), name="aerodrome_export"),
    path("aerodromes/<str:icao>/odt/",
         views.AerodromeODTView.as_view(), name="aerodrome_odt"),
    # PDF AIP – format DAUE.pdf
    path("aerodromes/<str:icao>/pdf/",
         views.AerodromePDFView.as_view(), name="aerodrome_pdf"),

    # AIRAC management
    path("airac/", views.AiracDashboardView.as_view(), name="airac_dashboard"),
    path("airac/publish/", views.AiracPublishView.as_view(), name="airac_publish"),
    path("airac/cycles/new/", views.AiracCycleCreateView.as_view(), name="airac_cycle_create"),
    path("airac/cycles/<int:pk>/edit/", views.AiracCycleUpdateView.as_view(), name="airac_cycle_edit"),
    # AD 2.14 – Approach and runway lighting
    path("aerodromes/<str:icao>/runways/<str:des>/lighting/",
         views.RunwayLightingUpdateView.as_view(), name="runway_lighting_update"),
]