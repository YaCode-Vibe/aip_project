"""Registries used by the generic CRUD views."""
from common.models import Airspace, Chart, CommunicationFacility, Navaid, Obstacle
from .models import (Apron, OperationalHours, PassengerFacility, Runway,
                     Taxiway, TextSection)
from common.models import ContactPoint

# Child collections (multi-row) : slug -> (Model, label)
CHILD_COLLECTIONS = {
    "contacts":    (ContactPoint,            "Contact point (AD 2.2)"),
    "hours":       (OperationalHours,        "Operational hours (AD 2.3)"),
    "passenger":   (PassengerFacility,       "Passenger facilities (AD 2.5)"),
    "aprons":      (Apron,                   "Aprons (AD 2.8)"),
    "taxiways":    (Taxiway,                 "Taxiways (AD 2.8)"),
    "obstacles":   (Obstacle,                "Obstacles (AD 2.10)"),
    "runways":     (Runway,                  "Runways (AD 2.12)"),
    "airspaces":   (Airspace,                "ATS airspace (AD 2.17)"),
    "comms":       (CommunicationFacility,   "Communication facilities (AD 2.18)"),
    "navaids":     (Navaid,                  "Radio navigation aids (AD 2.19)"),
    "texts":       (TextSection,             "Text sections (AD 2.20–2.23)"),
    "charts":      (Chart,                   "Charts (AD 2.24)"),
}

# Singleton sections : slug -> (Model, AIP code)
SINGLETON_SECTIONS = {
    "condition-of-use":   ("condition_of_use",       "AD 1.1 – Availability & conditions of use"),
    "rffs":               ("rffs",                   "AD 2.6 – Rescue and firefighting"),
    "snow-plan":          ("snow_plan",              "AD 1.2 – Snow plan"),
    "certificate":        ("certificate",            "AD 1.5 – Certification"),
    "handling":           ("handling",               "AD 2.4 – Handling services and facilities"),
    "seasonal":           ("seasonal_availability",  "AD 2.7 – Seasonal availability"),
    "smgcs":              ("smgcs",                  "AD 2.9 – SMGCS & markings"),
    "met":                ("met_service",            "AD 2.11 – Meteorological information"),
    "other-lighting":     ("other_lighting",         "AD 2.15 – Other lighting"),
    "helipad":            ("helipad",                "AD 2.16 – Helicopter landing area"),
}