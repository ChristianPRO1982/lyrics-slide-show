from django import forms
from django.utils.translation import gettext_lazy as _

from .models import Animation


class AnimationForm(forms.ModelForm):
    class Meta:
        model = Animation
        fields = [
            "title",
            "description",
            "scheduled_at",
            "text_color",
            "bg_color",
            "font_family",
            "font_size",
            "horizontal_padding",
            "background_asset_code",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"maxlength": 255}),
            "description": forms.Textarea(attrs={"rows": 4}),
            "scheduled_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "text_color": forms.TextInput(attrs={"maxlength": 32}),
            "bg_color": forms.TextInput(attrs={"maxlength": 32}),
            "font_family": forms.TextInput(attrs={"maxlength": 120}),
            "font_size": forms.NumberInput(attrs={"min": 10, "max": 300}),
            "horizontal_padding": forms.NumberInput(attrs={"min": 0, "max": 600}),
            "background_asset_code": forms.TextInput(attrs={"maxlength": 128}),
        }
        labels = {
            "title": _("Titre de l'animation"),
            "description": _("Description"),
            "scheduled_at": _("Date et heure"),
            "text_color": _("Couleur du texte"),
            "bg_color": _("Couleur de fond"),
            "font_family": _("Police"),
            "font_size": _("Taille de police"),
            "horizontal_padding": _("Marge horizontale"),
            "background_asset_code": _("Code d'image de fond"),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        scheduled_value = self.initial.get("scheduled_at")
        if scheduled_value is not None:
            self.initial["scheduled_at"] = scheduled_value.strftime("%Y-%m-%dT%H:%M")

    def clean_title(self) -> str:
        title = str(self.cleaned_data["title"] or "").strip()
        if not title:
            raise forms.ValidationError(_("Le titre est obligatoire."))
        return title

    def clean_description(self) -> str | None:
        value = str(self.cleaned_data.get("description") or "").strip()
        return value or None

    def clean_background_asset_code(self) -> str | None:
        value = str(self.cleaned_data.get("background_asset_code") or "").strip()
        return value or None
