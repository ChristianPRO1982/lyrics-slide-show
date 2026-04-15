from django import forms
from django.utils.translation import gettext_lazy as _

from app_main.models import SiteParams


class MemberSearchForm(forms.Form):
    member_search = forms.CharField(
        label=_("Recherche membre"),
        max_length=255,
        required=False,
        widget=forms.TextInput(
            attrs={
                "placeholder": _("Username, prénom, nom ou e-mail"),
            }
        ),
    )


class MemberRoleActionForm(forms.Form):
    member_id = forms.UUIDField(widget=forms.HiddenInput())
    role_name = forms.ChoiceField(
        choices=(
            ("moderator", _("Modérateur")),
            ("admin", _("Administrateur")),
        ),
        widget=forms.HiddenInput(),
    )
    enabled = forms.BooleanField(required=False, widget=forms.HiddenInput())
    member_search = forms.CharField(required=False, widget=forms.HiddenInput())


class ModeratorMessageForm(forms.ModelForm):
    class Meta:
        model = SiteParams
        fields = [
            "moderator_message",
            "moderator_message_cooldown_minutes",
        ]
        labels = {
            "moderator_message": _("Message de modération"),
            "moderator_message_cooldown_minutes": _("Délai de réaffichage du message de modération (minutes)"),
        }
        widgets = {
            "moderator_message": forms.Textarea(attrs={"rows": 6}),
        }


class SiteParamsAdminForm(forms.ModelForm):
    class Meta:
        model = SiteParams
        fields = [
            "title",
            "title_h1",
            "home_text",
            "bloc1_text",
            "bloc2_text",
            "verse_max_lines",
            "verse_max_characters_for_a_line",
            "chorus_prefix",
            "verse_prefix1",
            "verse_prefix2",
            "admin_message",
            "admin_message_cooldown_minutes",
            "bg_img_max_bytes",
            "bg_img_min_w",
            "bg_img_min_h",
            "bg_img_max_w",
            "bg_img_max_h",
            "bg_img_ratio_min",
            "bg_img_ratio_max",
            "bg_img_allowed_ext",
            "bg_img_allowed_mime",
        ]
        labels = {
            "title": _("Titre du site"),
            "title_h1": _("Titre principal"),
            "home_text": _("Texte d'accueil"),
            "bloc1_text": _("Texte du bloc 1"),
            "bloc2_text": _("Texte du bloc 2"),
            "verse_max_lines": _("Nombre maximal de lignes par couplet"),
            "verse_max_characters_for_a_line": _("Nombre maximal de caractères par ligne"),
            "chorus_prefix": _("Préfixe du refrain"),
            "verse_prefix1": _("Préfixe de couplet"),
            "verse_prefix2": _("Suffixe de couplet"),
            "admin_message": _("Message global administrateur"),
            "admin_message_cooldown_minutes": _("Délai de réaffichage du message administrateur (minutes)"),
            "bg_img_max_bytes": _("Taille maximale des images de fond (octets)"),
            "bg_img_min_w": _("Largeur minimale des images de fond"),
            "bg_img_min_h": _("Hauteur minimale des images de fond"),
            "bg_img_max_w": _("Largeur maximale des images de fond"),
            "bg_img_max_h": _("Hauteur maximale des images de fond"),
            "bg_img_ratio_min": _("Ratio minimal des images de fond"),
            "bg_img_ratio_max": _("Ratio maximal des images de fond"),
            "bg_img_allowed_ext": _("Extensions d'images autorisées"),
            "bg_img_allowed_mime": _("Types MIME d'images autorisés"),
        }
        widgets = {
            "home_text": forms.Textarea(attrs={"rows": 5}),
            "bloc1_text": forms.Textarea(attrs={"rows": 4}),
            "bloc2_text": forms.Textarea(attrs={"rows": 4}),
            "admin_message": forms.Textarea(attrs={"rows": 6}),
        }
