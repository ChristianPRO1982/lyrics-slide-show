#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys
import dotenv



def main():
    """Run administrative tasks."""

    DEBUG = os.environ.get('DEBUG') == '1'

    if DEBUG :
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'lyrics_slide_show.settings.dev')
    else :
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", 'lyrics_slide_show.settings.prod')

    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    dotenv.load_dotenv(override=True)
    main()
