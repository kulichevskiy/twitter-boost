"""Effective settings = env defaults overridden by rows in the `settings` table."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings as env
from ..models import Setting

# Keys the UI may override. Everything else is env-only.
EDITABLE_KEYS = [
    "source_lists",
    "source_tweets",
    "source_profiles",
    "my_handle",
    "twitterapi_io_key",
    "x_client_id",
    "x_client_secret",
    "anthropic_api_key",
    "sync_schedule_mode",
    "sync_daily_time",
    "sync_interval_hours",
    "unfollow_confirmations",
    "count_tolerance_pct",
    "count_tolerance_abs",
    "profile_refresh_days",
    "profile_refresh_batch",
    "followback_deadline_days",
    "analysis_provider",
    "analysis_model",
    "claude_cli_path",
    "codex_cli_path",
    "analysis_timeout_seconds",
    "analysis_tweets",
    "analysis_include_replies",
    "analysis_goal",
]
SECRET_KEYS = {"twitterapi_io_key", "x_client_secret", "anthropic_api_key"}


class Effective(BaseModel):
    source_lists: str
    source_tweets: str
    source_profiles: str
    my_handle: str
    twitterapi_io_key: str
    twitterapi_io_base_url: str
    x_client_id: str
    x_client_secret: str
    x_api_base_url: str
    anthropic_api_key: str
    public_base_url: str
    sync_schedule_mode: str
    sync_daily_time: str
    sync_interval_hours: int
    unfollow_confirmations: int
    count_tolerance_pct: float
    count_tolerance_abs: int
    profile_refresh_days: int
    profile_refresh_batch: int
    followback_deadline_days: int
    analysis_provider: str
    analysis_model: str
    claude_cli_path: str
    codex_cli_path: str
    analysis_timeout_seconds: int
    analysis_tweets: int
    analysis_include_replies: bool
    analysis_goal: str


def load_overrides(session: Session) -> dict[str, Any]:
    rows = session.execute(select(Setting)).scalars().all()
    return {r.key: r.value for r in rows if r.key in EDITABLE_KEYS}


def load_effective(session: Session) -> Effective:
    base = {k: getattr(env, k) for k in Effective.model_fields}
    for k, v in load_overrides(session).items():
        if v is None or v == "":
            continue
        base[k] = v
    return Effective(**base)


def save_overrides(session: Session, values: dict[str, Any]) -> None:
    for key, value in values.items():
        if key not in EDITABLE_KEYS:
            continue
        row = session.get(Setting, key)
        if value is None or value == "":
            if row is not None:
                session.delete(row)
            continue
        if row is None:
            session.add(Setting(key=key, value=value))
        else:
            row.value = value
    session.flush()


def mask(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "••••"
    return f"{value[:4]}…{value[-4:]}"
