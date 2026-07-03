from django import forms
from django.utils.translation import gettext_lazy as _

from app_main.home_cards import (
    HOME_CARD_ICON_CHOICES,
    build_home_cards_payload,
    parse_home_cards,
)
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
            "moderator_message_cooldown_minutes": _(
                "Délai de réaffichage du message de modération (minutes)"
            ),
        }
        widgets = {
            "moderator_message": forms.Textarea(attrs={"rows": 6}),
        }


class AdminMessageForm(forms.ModelForm):
    class Meta:
        model = SiteParams
        fields = [
            "admin_message",
            "admin_message_cooldown_minutes",
        ]
        labels = {
            "admin_message": _("Message global administrateur"),
            "admin_message_cooldown_minutes": _(
                "Délai de réaffichage du message administrateur (minutes)"
            ),
        }
        widgets = {
            "admin_message": forms.Textarea(attrs={"rows": 6}),
        }


class SiteParamsAdminForm(forms.ModelForm):
    home_card_1_title = forms.CharField(
        label=_("Carte accueil 1 - Titre"), required=False, max_length=255
    )
    home_card_1_text = forms.CharField(
        label=_("Carte accueil 1 - Texte (markdown léger)"),
        required=False,
        widget=forms.Textarea(attrs={"rows": 4}),
    )
    home_card_1_image = forms.ChoiceField(
        label=_("Carte accueil 1 - Image"),
        required=False,
        choices=HOME_CARD_ICON_CHOICES,
    )
    home_card_2_title = forms.CharField(
        label=_("Carte accueil 2 - Titre"), required=False, max_length=255
    )
    home_card_2_text = forms.CharField(
        label=_("Carte accueil 2 - Texte (markdown léger)"),
        required=False,
        widget=forms.Textarea(attrs={"rows": 4}),
    )
    home_card_2_image = forms.ChoiceField(
        label=_("Carte accueil 2 - Image"),
        required=False,
        choices=HOME_CARD_ICON_CHOICES,
    )
    home_card_3_title = forms.CharField(
        label=_("Carte accueil 3 - Titre"), required=False, max_length=255
    )
    home_card_3_text = forms.CharField(
        label=_("Carte accueil 3 - Texte (markdown léger)"),
        required=False,
        widget=forms.Textarea(attrs={"rows": 4}),
    )
    home_card_3_image = forms.ChoiceField(
        label=_("Carte accueil 3 - Image"),
        required=False,
        choices=HOME_CARD_ICON_CHOICES,
    )
    home_card_4_title = forms.CharField(
        label=_("Carte accueil 4 - Titre"), required=False, max_length=255
    )
    home_card_4_text = forms.CharField(
        label=_("Carte accueil 4 - Texte (markdown léger)"),
        required=False,
        widget=forms.Textarea(attrs={"rows": 4}),
    )
    home_card_4_image = forms.ChoiceField(
        label=_("Carte accueil 4 - Image"),
        required=False,
        choices=HOME_CARD_ICON_CHOICES,
    )
    home_card_5_title = forms.CharField(
        label=_("Carte accueil 5 - Titre"), required=False, max_length=255
    )
    home_card_5_text = forms.CharField(
        label=_("Carte accueil 5 - Texte (markdown léger)"),
        required=False,
        widget=forms.Textarea(attrs={"rows": 4}),
    )
    home_card_5_image = forms.ChoiceField(
        label=_("Carte accueil 5 - Image"),
        required=False,
        choices=HOME_CARD_ICON_CHOICES,
    )
    home_card_6_title = forms.CharField(
        label=_("Carte accueil 6 - Titre"), required=False, max_length=255
    )
    home_card_6_text = forms.CharField(
        label=_("Carte accueil 6 - Texte (markdown léger)"),
        required=False,
        widget=forms.Textarea(attrs={"rows": 4}),
    )
    home_card_6_image = forms.ChoiceField(
        label=_("Carte accueil 6 - Image"),
        required=False,
        choices=HOME_CARD_ICON_CHOICES,
    )

    class Meta:
        model = SiteParams
        fields = [
            "title",
            "title_h1",
            "signup_url",
            "home_text",
            "bloc1_text",
            "bloc2_text",
            "verse_max_lines",
            "verse_max_characters_for_a_line",
            "chorus_prefix",
            "verse_prefix1",
            "verse_prefix2",
            "admin_message_cooldown_minutes",
            "moderator_message_cooldown_minutes",
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
            "signup_url": _("URL d'inscription"),
            "home_text": _("Texte d'accueil"),
            "bloc1_text": _("Texte du bloc 1"),
            "bloc2_text": _("Texte du bloc 2"),
            "verse_max_lines": _("Nombre maximal de lignes par couplet"),
            "verse_max_characters_for_a_line": _(
                "Nombre maximal de caractères par ligne"
            ),
            "chorus_prefix": _("Préfixe du refrain"),
            "verse_prefix1": _("Préfixe de couplet"),
            "verse_prefix2": _("Suffixe de couplet"),
            "admin_message_cooldown_minutes": _(
                "Délai de réaffichage du message administrateur (minutes)"
            ),
            "moderator_message_cooldown_minutes": _(
                "Délai de réaffichage du message modérateur (minutes)"
            ),
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
            "signup_url": forms.URLInput(attrs={"placeholder": "https://..."}),
            "home_text": forms.Textarea(attrs={"rows": 5}),
            "bloc1_text": forms.Textarea(attrs={"rows": 4}),
            "bloc2_text": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        cards = parse_home_cards(getattr(self.instance, "home_text", "") or "")
        self.fields["home_text"].required = False
        # These three site-level rendering labels are exceptions: leading/trailing
        # spaces are meaningful and must survive form cleaning unchanged.
        self.fields["chorus_prefix"].strip = False
        self.fields["verse_prefix1"].strip = False
        self.fields["verse_prefix2"].strip = False
        for index in range(6):
            card = (
                cards[index]
                if index < len(cards)
                else {"title": "", "text": "", "image": ""}
            )
            self.fields[f"home_card_{index + 1}_title"].initial = card.get("title", "")
            self.fields[f"home_card_{index + 1}_text"].initial = card.get("text", "")
            self.fields[f"home_card_{index + 1}_image"].initial = card.get("image", "")
        self.fields["home_text"].widget = forms.HiddenInput()

    def clean(self):
        cleaned_data = super().clean()
        cards_payload: list[dict[str, str]] = []
        for index in range(1, 7):
            title = str(cleaned_data.get(f"home_card_{index}_title") or "").strip()
            text = str(cleaned_data.get(f"home_card_{index}_text") or "").strip()
            image = str(cleaned_data.get(f"home_card_{index}_image") or "").strip()
            cards_payload.append({"title": title, "text": text, "image": image})
        cleaned_data["home_text"] = build_home_cards_payload(cards_payload)
        return cleaned_data

    @staticmethod
    def _parse_home_cards(raw_value: str) -> list[dict[str, str]]:
        return parse_home_cards(raw_value)
