from __future__ import annotations

import os

import django
from scrapy.cmdline import execute


def main() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "grantradar.settings")
    django.setup()
    execute()


if __name__ == "__main__":
    main()
