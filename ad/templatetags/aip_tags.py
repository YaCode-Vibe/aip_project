"""Filtres de template pour le diff N/N-1 et les change bars OACI."""
from django import template

register = template.Library()


@register.filter
def row_changed(diff_section, idx):
    """Retourne True si la ligne `idx` a changé entre N et N-1."""
    if not diff_section:
        return False
    return idx in diff_section.get("rows", [])


@register.filter
def section_changed(diff_section):
    """Retourne True si la section (1:1 ou ensemble) a changé."""
    if not diff_section:
        return False
    return diff_section.get("changed", False)


@register.filter
def key_changed(diff_section, key):
    """Retourne True si la clé `key` d'une section dict (texts) a changé."""
    if not diff_section:
        return False
    return key in diff_section.get("keys", [])
@register.filter
def dms(value, kind="lat"):
    """Filtre template : convertit une coordonnée DD en DMS.

    Usage :
        {{ ad.latitude|dms:"lat" }}    →  "28 03 05.25N"
        {{ ad.longitude|dms:"lon" }}   →  "009 38 34.10E"
        {{ ad.latitude|dms:"lat-compact" }} → "280305.25N"
    """
    from common.utils import dd_to_dms

    if kind == "lat":
        return dd_to_dms(value, is_lat=True)
    if kind == "lon":
        return dd_to_dms(value, is_lat=False)
    if kind == "lat-compact":
        return dd_to_dms(value, is_lat=True, compact=True)
    if kind == "lon-compact":
        return dd_to_dms(value, is_lat=False, compact=True)
    return value