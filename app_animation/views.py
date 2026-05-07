from __future__ import annotations

from django.contrib import messages
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _

from .font_catalog import list_font_choices, list_font_previews
from .forms import AnimationForm
from .models import Animation
from .services.access import (
    get_selected_group_or_404,
    redirect_to_groups_when_no_selection,
)


def animations(request: HttpRequest) -> HttpResponse:
    try:
        selected_group = get_selected_group_or_404(request)
    except Http404:
        return redirect_to_groups_when_no_selection(request)
    now = timezone.now()
    upcoming_animations = Animation.objects.filter(
        group_id=selected_group.group_id,
        scheduled_at__gte=now,
    ).order_by("scheduled_at", "animation_id")

    return render(
        request,
        "animation/animations.html",
        {
            "selected_group": selected_group,
            "upcoming_animations": upcoming_animations,
        },
    )


def animation_history(request: HttpRequest) -> HttpResponse:
    try:
        selected_group = get_selected_group_or_404(request)
    except Http404:
        return redirect_to_groups_when_no_selection(request)
    now = timezone.now()
    past_animations = Animation.objects.filter(
        group_id=selected_group.group_id,
        scheduled_at__lt=now,
    ).order_by("-scheduled_at", "-animation_id")

    return render(
        request,
        "animation/animation_history.html",
        {
            "selected_group": selected_group,
            "past_animations": past_animations,
        },
    )


def modify_animation(request: HttpRequest, animation_id: int) -> HttpResponse:
    try:
        selected_group = get_selected_group_or_404(request)
    except Http404:
        return redirect_to_groups_when_no_selection(request)

    animation = get_object_or_404(Animation, animation_id=animation_id)
    if animation.group_id != selected_group.group_id:
        raise Http404

    if request.method == "POST":
        form = AnimationForm(request.POST, instance=animation)
        if form.is_valid():
            form.save()
            messages.success(request, _("L'animation a été enregistrée."))
            return redirect("modify_animation", animation_id=animation.animation_id)
    else:
        form = AnimationForm(instance=animation)

    font_choices = [{"value": value, "label": label} for value, label in list_font_choices()]
    font_previews = [
        {
            "fontFamily": item.family,
            "sample": item.sample,
            "label": item.family,
        }
        for item in list_font_previews()
    ]

    return render(
        request,
        "animation/modify_animation.html",
        {
            "selected_group": selected_group,
            "animation": animation,
            "form": form,
            "popup_data": {
                "fontChoices": font_choices,
                "fontPreviews": font_previews,
            },
        },
    )


def delete_animation(request: HttpRequest, animation_id: int) -> HttpResponse:
    if request.method != "POST":
        raise Http404

    animation = get_object_or_404(Animation, animation_id=animation_id)
    selected_group = get_selected_group_or_404(request)
    if animation.group_id != selected_group.group_id:
        raise Http404
    animation.delete()
    messages.success(request, _("L'animation a été supprimée."))
    return redirect("animations")
