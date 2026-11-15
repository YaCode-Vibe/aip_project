"""Champs et widgets Django pour la saisie DMS."""
from django import forms
from django.core.exceptions import ValidationError

from common.utils import dd_to_dms, dms_to_dd


class DMSInput(forms.TextInput):
    """TextInput qui affiche les coordonnées en DMS et accepte DMS ou DD."""

    def __init__(self, is_lat=True, attrs=None):
        self.is_lat = is_lat
        default_attrs = {
            "class": "form-control",
            "placeholder": "28 03 05.25N" if is_lat else "009 38 34.10E",
            "autocomplete": "off",
        }
        if attrs:
            default_attrs.update(attrs)
        super().__init__(default_attrs)

    def format_value(self, value):
        if value is None or value == "":
            return ""
        # Déjà une chaîne DMS → garder tel quel
        if isinstance(value, str) and any(c in value for c in "NSEWnsew°º'\""):
            return value
        # Essayer de reformater en DMS
        try:
            dms = dd_to_dms(value, is_lat=self.is_lat)
            if dms == "NIL":
                return str(value) if value else ""
            return dms
        except Exception:
            return str(value) if value else ""


class DMSField(forms.DecimalField):
    """Champ qui accepte DMS ou DD, retourne un Decimal (DD)."""

    def __init__(self, is_lat=True, **kwargs):
        self.is_lat = is_lat
        kwargs.setdefault("max_digits", 9)
        kwargs.setdefault("decimal_places", 6)
        kwargs.setdefault("required", False)
        if "widget" not in kwargs:
            kwargs["widget"] = DMSInput(is_lat=is_lat)
        super().__init__(**kwargs)

    def to_python(self, value):
        if value in self.empty_values:
            return None
        if isinstance(value, Decimal):
            return value
        parsed = dms_to_dd(value, is_lat=self.is_lat)
        if parsed is not None:
            return parsed
        example = "28 03 05.25N" if self.is_lat else "009 38 34.10E"
        raise ValidationError(
            f"Format attendu : DMS (ex. '{example}') "
            f"ou décimal (ex. '28.051458')."
        )


from decimal import Decimal  # noqa: E402  (import tardif pour éviter circularité)