from django import forms
from django.utils.translation import gettext_lazy as _

from app_animation.services.background_images import (
    fetch_genre_options,
    fetch_target_options,
)

from .font_catalog import (
    is_allowed_font_family,
    list_font_choices,
    normalize_animation_font_family,
)
from .models import Animation


class AnimationForm(forms.ModelForm):
    font_family = forms.ChoiceField(
        choices=list_font_choices(),
        label=_("Police"),
    )

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
            "font_size": _("Taille de police"),
            "horizontal_padding": _("Marge horizontale"),
            "background_asset_code": _("Code d'image de fond"),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        scheduled_value = self.initial.get("scheduled_at")
        if scheduled_value is None and getattr(self.instance, "pk", None):
            scheduled_value = self.instance.scheduled_at
        if scheduled_value is not None:
            self.initial["scheduled_at"] = scheduled_value.strftime("%Y-%m-%dT%H:%M")

        if not self.is_bound:
            initial_font = self.initial.get("font_family")
            if initial_font is None and getattr(self.instance, "pk", None):
                initial_font = self.instance.font_family
            self.initial["font_family"] = normalize_animation_font_family(initial_font)

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

    def clean_font_family(self) -> str:
        value = str(self.cleaned_data.get("font_family") or "").strip()
        if not is_allowed_font_family(value):
            raise forms.ValidationError(_("Police invalide."))
        return value


class BackgroundImageUploadForm(forms.Form):
    no_targets_message = _("Aucune cible n'est disponible. Un modérateur doit d'abord en créer une.")
    title = forms.CharField(max_length=255, label=_("Titre"))
    target = forms.ChoiceField(label=_("Cible"), choices=())
    description = forms.CharField(
        required=False,
        label=_("Description"),
        widget=forms.Textarea(attrs={"rows": 4}),
    )
    image_file = forms.ImageField(label=_("Image"))
    genre_ids = forms.MultipleChoiceField(
        required=False,
        label=_("Genres"),
        widget=forms.CheckboxSelectMultiple,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        target_options = tuple(fetch_target_options())
        self.has_target_options = bool(target_options)
        self.fields["target"].choices = [
            (option["name"], option["name"]) for option in target_options
        ]
        if self.has_target_options and not self.is_bound and not self.initial.get("target"):
            self.initial["target"] = str(target_options[0]["name"])
        if not self.has_target_options:
            self.fields["target"].required = False
            self.fields["target"].widget.attrs["disabled"] = True

        genre_options = tuple(fetch_genre_options())
        self.fields["genre_ids"].choices = [
            (str(option["id"]), option["label"]) for option in genre_options
        ]

        if self.is_bound:
            selected_ids = {
                str(value).strip()
                for value in self.data.getlist(self.add_prefix("genre_ids"))
                if str(value).strip()
            }
        else:
            initial_values = self.initial.get("genre_ids", [])
            if initial_values is None:
                initial_values = []
            selected_ids = {
                str(value).strip() for value in initial_values if str(value).strip()
            }

        selected_options: list[dict[str, str]] = []
        available_options: list[dict[str, str]] = []
        for option in genre_options:
            payload = {
                "id": str(option["id"]),
                "label": str(option["label"]),
            }
            if payload["id"] in selected_ids:
                selected_options.append(payload)
            else:
                available_options.append(payload)

        self.genre_selected_options = tuple(selected_options)
        self.genre_available_options = tuple(available_options)

    def clean_target(self) -> str:
        if not getattr(self, "has_target_options", False):
            raise forms.ValidationError(self.no_targets_message)
        return str(self.cleaned_data.get("target") or "").strip()
