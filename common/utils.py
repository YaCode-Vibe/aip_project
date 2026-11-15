"""Utilitaires de conversion DMS ↔ DD pour l'affichage et la saisie."""
from decimal import Decimal, InvalidOperation


# ===========================================================================
# DD → DMS (affichage)
# ===========================================================================
def dd_to_dms(value, is_lat=True, decimals=2, compact=False):
    """
    Convertit une coordonnée en degrés décimaux (DD) vers DMS.

    Args:
        value      : valeur DD (Decimal, float ou str)
        is_lat     : True = latitude (2 chiffres degrés, N/S)
                     False = longitude (3 chiffres degrés, E/W)
        decimals   : nombre de décimales sur les secondes (défaut 2)
        compact    : True → "280305.25N"  /  False → "28 03 05.25N"

    Returns:
        str : coordonnée formatée DMS, ou "NIL" si value est None.
    """
    if value is None or value == "":
        return "NIL"

    try:
        v = float(value)
    except (TypeError, ValueError):
        return "NIL"

    if is_lat:
        direction = "N" if v >= 0 else "S"
    else:
        direction = "E" if v >= 0 else "W"

    av = abs(v)
    degrees = int(av)
    minutes_full = (av - degrees) * 60
    minutes = int(minutes_full)
    seconds = round((minutes_full - minutes) * 60, decimals)

    if seconds >= 60:
        seconds = 0.0
        minutes += 1
    if minutes >= 60:
        minutes = 0
        degrees += 1

    deg_width = 2 if is_lat else 3
    sec_width = 3 + decimals
    sec_str = f"{seconds:0{sec_width}.{decimals}f}"

    if compact:
        return f"{degrees:0{deg_width}d}{minutes:02d}{sec_str}{direction}"
    return f"{degrees:0{deg_width}d} {minutes:02d} {sec_str}{direction}"


def dd_pair_to_dms(lat, lon, decimals=2, compact=False):
    """Convertit une paire lat/lon DD vers deux éléments DMS."""
    return (
        dd_to_dms(lat, is_lat=True, decimals=decimals, compact=compact),
        dd_to_dms(lon, is_lat=False, decimals=decimals, compact=compact),
    )


def dd_pair_to_dms_string(lat, lon, decimals=2, compact=False):
    """Format '28 03 05.25N 009 38 34.10E' (une seule chaîne)."""
    dms_lat, dms_lon = dd_pair_to_dms(lat, lon, decimals, compact)
    if dms_lat == "NIL" and dms_lon == "NIL":
        return "NIL"
    return f"{dms_lat} {dms_lon}"


# ===========================================================================
# DMS → DD (saisie formulaire)
# ===========================================================================
def dms_to_dd(value, is_lat=True):
    """Parse DMS ou DD vers Decimal (degrees decimal).

    Formats acceptés :
        - DD         : "28.051458", "-8.167847"
        - DMS espacé : "28 03 05.25N", "009 38 34.10E"
        - DMS symboles : "28° 03' 05.25\"N"
        - DMS compact : "280305.25N", "0093834.10E"

    Returns:
        Decimal (négatif si S/W) ou None si non parsable.
    """
    if value is None or value == "":
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float)):
        return Decimal(str(value))

    s = str(value).strip().upper()
    if not s:
        return None

    # Fast-path : nombre décimal pur (éventuellement négatif)
    try:
        return Decimal(s)
    except (InvalidOperation, ValueError):
        pass

    # Direction suffixe
    direction = None
    if s[-1] in ("N", "S", "E", "W"):
        direction = s[-1]
        s = s[:-1].strip()

    # Normaliser les symboles DMS
    for ch in ("°", "º", "'", "’", '"', "”"):
        s = s.replace(ch, " ")

    parts = [p for p in s.split() if p]

    if len(parts) == 3:
        try:
            deg = float(parts[0])
            mn = float(parts[1])
            sec = float(parts[2])
        except ValueError:
            return None
    elif len(parts) == 1:
        raw = parts[0]
        if "." in raw:
            int_part, dec_part = raw.split(".", 1)
        else:
            int_part, dec_part = raw, ""
        if not int_part.isdigit():
            return None
        iv = int(int_part)
        deg = iv // 10000
        mn = (iv % 10000) // 100
        sec = (iv % 100) + (float("0." + dec_part) if dec_part else 0.0)
    else:
        return None

    max_deg = 90 if is_lat else 180
    if not (0 <= deg <= max_deg):
        return None
    if not (0 <= mn < 60):
        return None
    if not (0 <= sec < 60):
        return None

    dd = deg + mn / 60.0 + sec / 3600.0
    if direction in ("S", "W"):
        dd = -dd
    return Decimal(str(round(dd, 6)))