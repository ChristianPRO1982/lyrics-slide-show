from django.conf import settings

def global_variables(request):
    return {
        'company_name': 'cARThographie',
        'company_name_small': '🏕️✞🎙🎨🪢',
        'author': 'Chris',
        'description': "cARThographie - des outils gratuits pour vos projets",
        'title_before': '',
        'title_after': ' - Lyrics Slide Show',
        "debug": settings.DEBUG,
        "loader_debug": getattr(settings, "LOADER_DEBUG", False),
        "loader_debug_delay_ms": getattr(settings, "LOADER_DEBUG_DELAY_MS", 0),
        "loader_debug_prenav_delay_ms": getattr(settings, "LOADER_DEBUG_PRENAV_DELAY_MS", 0),
    }