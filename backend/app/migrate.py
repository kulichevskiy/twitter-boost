"""Run Alembic migrations programmatically (API start, `crm db upgrade`)."""

from __future__ import annotations

import logging
from pathlib import Path

from alembic.config import Config

from alembic import command

from .config import BACKEND_DIR, settings

log = logging.getLogger(__name__)


def alembic_config() -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    cfg.set_main_option("sqlalchemy.url", settings.database_url)
    return cfg


def upgrade_database(revision: str = "head") -> None:
    Path(settings.data_dir).mkdir(parents=True, exist_ok=True)
    command.upgrade(alembic_config(), revision)
    log.info("database at %s", revision)
