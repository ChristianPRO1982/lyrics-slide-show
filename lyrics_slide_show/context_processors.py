from django.conf import settings

def global_variables(request):
    return {
        'company_name': 'cARThographie',
        'company_name_small': '🏕️✞🎙🎨🪢',
        'author': 'Chris',
        'description': "cARThographie - des outils gratuits pour vos projets",
        'title_before': '',
        'title_after': ' - Lyrics Slide Show',
        "loader_debug": getattr(settings, "LOADER_DEBUG", False),
        "loader_debug_delay_ms": getattr(settings, "LOADER_DEBUG_DELAY_MS", 0),
    }
