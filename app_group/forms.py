from django import forms
from django.utils.translation import gettext_lazy as _

from .models import Group, GroupStatus, normalize_group_info, normalize_group_name


class GroupCreateForm(forms.ModelForm):
    class Meta:
        model = Group
        fields = ["name", "info"]
        widgets = {
            "name": forms.TextInput(attrs={"maxlength": 255}),
            "info": forms.Textarea(attrs={"rows": 5}),
        }
        labels = {
            "name": _("Nom du groupe"),
            "info": _("Informations"),
        }
        help_texts = {
            "info": _("Texte simple uniquement. Les retours à la ligne sont conservés."),
        }

    def clean_name(self) -> str:
        name = normalize_group_name(self.cleaned_data["name"])
        if not name:
            raise forms.ValidationError(_("Le nom du groupe est obligatoire."))
        return name

    def clean_info(self) -> str | None:
        info = self.cleaned_data.get("info")
        return normalize_group_info(info) if info else None


class GroupSettingsForm(forms.ModelForm):
    is_open = forms.TypedChoiceField(
        label=_("Ouverture du groupe"),
        choices=(
            ("open", _("Ouvert")),
            ("private", _("Fermé")),
        ),
        coerce=str,
        empty_value=GroupStatus.OPEN,
    )

    class Meta:
        model = Group
        fields = ["name", "info"]
        widgets = {
            "name": forms.TextInput(attrs={"maxlength": 255}),
            "info": forms.Textarea(attrs={"rows": 6}),
        }
        labels = {
            "name": _("Nom du groupe"),
            "info": _("Informations"),
        }
        help_texts = {
            "info": _("Texte simple uniquement. Les retours à la ligne sont conservés."),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        current_status = self.instance.status if self.instance and self.instance.pk else GroupStatus.OPEN
        self.fields["is_open"].initial = current_status

    def clean_name(self) -> str:
        name = normalize_group_name(self.cleaned_data["name"])
        if not name:
            raise forms.ValidationError(_("Le nom du groupe est obligatoire."))
        return name

    def clean_info(self) -> str | None:
        info = self.cleaned_data.get("info")
        return normalize_group_info(info) if info else None

    def save(self, commit: bool = True):
        instance = super().save(commit=False)
        instance.status = self.cleaned_data["is_open"]
        if commit:
            instance.save()
        return instance
