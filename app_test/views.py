from django.shortcuts import render


SONGS = [
    {
        "id": 1,
        "title": "Lumiere Sur Nos Pas",
        "subtitle": "Marche d'aurore",
        "theme": "Espoir",
        "tempo": "Medium",
        "language": "FR",
        "tags": ["assemblee", "ouverture", "lumineux"],
    },
    {
        "id": 2,
        "title": "Riviere de Grace",
        "subtitle": "Version acoustique",
        "theme": "Grace",
        "tempo": "Slow",
        "language": "FR",
        "tags": ["adoration", "calme", "priere"],
    },
    {
        "id": 3,
        "title": "Feu Dans La Nuit",
        "subtitle": "Chant de veillee",
        "theme": "Confiance",
        "tempo": "Fast",
        "language": "FR",
        "tags": ["live", "jeunesse", "energie"],
    },
    {
        "id": 4,
        "title": "Anchor Over Tides",
        "subtitle": "Harbor Session",
        "theme": "Peace",
        "tempo": "Slow",
        "language": "EN",
        "tags": ["reflection", "piano", "night"],
    },
    {
        "id": 5,
        "title": "Ville En Priere",
        "subtitle": "Chorale urbaine",
        "theme": "Intercession",
        "tempo": "Medium",
        "language": "FR",
        "tags": ["choeur", "ville", "appel"],
    },
    {
        "id": 6,
        "title": "Mountain Mercy",
        "subtitle": "Campfire Edit",
        "theme": "Mercy",
        "tempo": "Medium",
        "language": "EN",
        "tags": ["folk", "warm", "guitar"],
    },
    {
        "id": 7,
        "title": "Danse Encore Mon Ame",
        "subtitle": "Refrain ouvert",
        "theme": "Joy",
        "tempo": "Fast",
        "language": "FR",
        "tags": ["fete", "rythme", "clap"],
    },
    {
        "id": 8,
        "title": "Silent Harbor Hymn",
        "subtitle": "Moonlit Chorus",
        "theme": "Rest",
        "tempo": "Slow",
        "language": "EN",
        "tags": ["ambient", "rest", "chorus"],
    },
    {
        "id": 9,
        "title": "Source Et Desert",
        "subtitle": "Psaume nomade",
        "theme": "Hope",
        "tempo": "Medium",
        "language": "FR",
        "tags": ["voyage", "psaume", "desert"],
    },
    {
        "id": 10,
        "title": "Glory In The Courtyard",
        "subtitle": "Evening Revival",
        "theme": "Praise",
        "tempo": "Fast",
        "language": "EN",
        "tags": ["crowd", "big-room", "celebration"],
    },
]


def _filtered_songs(request):
    query = request.GET.get("q", "").strip().lower()
    if not query:
        return SONGS, ""

    filtered = []
    for song in SONGS:
        haystack = " ".join(
            [
                song["title"],
                song["subtitle"],
                song["theme"],
                song["language"],
                " ".join(song["tags"]),
            ]
        ).lower()
        if query in haystack:
            filtered.append(song)
    return filtered, request.GET.get("q", "").strip()


def _context(request, mockup_name, description):
    songs, query = _filtered_songs(request)
    return {
        "songs": songs,
        "query": query,
        "songs_total": len(SONGS),
        "results_count": len(songs),
        "mockup_name": mockup_name,
        "description": description,
        "mockups": [
            {"slug": "maquette-1", "label": "Maquette 1"},
            {"slug": "maquette-2", "label": "Maquette 2"},
            {"slug": "maquette-3", "label": "Maquette 3"},
            {"slug": "maquette-4", "label": "Maquette 4"},
            {"slug": "maquette-5", "label": "Maquette 5"},
        ],
    }


def index(request):
    return render(
        request,
        "app_test/index.html",
        {"songs": SONGS, "songs_total": len(SONGS)},
    )


def mockup_1(request):
    return render(
        request,
        "app_test/mockup_1.html",
        _context(request, "Maquette 1", "Direction editoriale lumineuse et accueillante."),
    )


def mockup_2(request):
    return render(
        request,
        "app_test/mockup_2.html",
        _context(request, "Maquette 2", "Direction scene live, plus dramatique et immersive."),
    )


def mockup_3(request):
    return render(
        request,
        "app_test/mockup_3.html",
        _context(request, "Maquette 3", "Direction utilitaire dense, pensee pour preparer vite."),
    )


def mockup_4(request):
    return render(
        request,
        "app_test/mockup_4.html",
        _context(request, "Maquette 4", "Direction mobile-first, douce et tres lisible."),
    )


def mockup_5(request):
    return render(
        request,
        "app_test/mockup_5.html",
        _context(request, "Maquette 5", "Direction premium, split-view et filtres lateraux."),
    )


def mockup_v1(request):
    return render(
        request,
        "app_test/mockup_v1.html",
        _context(
            request,
            "V1",
            "Base fonctionnelle generale avec rail lateral compact et menu deployable.",
        ),
    )


def mockup_v2(request):
    return render(
        request,
        "app_test/mockup_v2.html",
        _context(
            request,
            "V2",
            "Base generale avec rail lateral, navigation de section et outils de page separes.",
        ),
    )


def mockup_v3(request):
    return render(
        request,
        "app_test/mockup_v3.html",
        {
            "mockup_name": "V3",
            "description": "Base generique vide pour construire le template principal du site.",
        },
    )


def mockup_v4(request):
    return render(
        request,
        "app_test/mockup_v4.html",
        {
            "mockup_name": "V4",
            "description": "Validation du nouveau base.html via heritage de template.",
        },
    )
