from django.http import Http404

from app_group.models import Group
from app_group.services import get_selected_group_state

from app_animation.models import Animation


def get_selected_group_or_404(request) -> Group:
    selected_group, _selected_via_secret = get_selected_group_state(request)
    if selected_group is None:
        raise Http404
    return selected_group


def ensure_animation_in_selected_group(request, animation: Animation) -> Group:
    selected_group = get_selected_group_or_404(request)
    if animation.group_id != selected_group.group_id:
        raise Http404
    return selected_group
