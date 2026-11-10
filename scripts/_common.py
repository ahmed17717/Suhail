"""Shared bootstrap for CLI scripts: load .env, build validated settings."""

from __future__ import annotations

import os

from dotenv import load_dotenv

from suhail.bootstrap import configure_logging
from suhail.config import Settings


def load_settings() -> Settings:
    load_dotenv()
    settings = Settings.from_env(os.environ)
    configure_logging(settings.log_level)
    return settings
