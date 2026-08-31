from app_main.wiki_help import get_wiki_help_url


def wiki_help(request) -> dict[str, str]:
    resolver_match = getattr(request, "resolver_match", None)
    url_name = getattr(resolver_match, "url_name", None)
    return {"wiki_help_url": get_wiki_help_url(url_name)}
