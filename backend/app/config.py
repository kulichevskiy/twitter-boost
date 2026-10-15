"""Runtime configuration.

Two layers: environment (.env) gives defaults and secrets; the `settings`
table in SQLite (see services/settings.py) overrides the non-secret knobs and
can also hold credentials entered through the UI.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- server -----------------------------------------------------------
    host: str = "0.0.0.0"
    port: int = 8000
    # Public URL of the Next.js frontend. Used to build the X OAuth redirect
    # URI (/api/crm/auth/x/callback is proxied by Next to this backend).
    public_base_url: str = "http://localhost:3100"
    # Bearer token required on every /api/crm/* and /mcp request. Empty = no auth.
    crm_api_token: str = ""
    database_url: str = f"sqlite:///{BACKEND_DIR / 'data' / 'crm.db'}"
    log_level: str = "INFO"

    # --- data sources -------------------------------------------------------
    # Which adapter serves which operation: "x" | "twitterapi" | "fake".
    source_lists: str = "twitterapi"
    source_tweets: str = "twitterapi"
    source_profiles: str = "twitterapi"

    # The account we track. Needed before the first sync; the X OAuth flow
    # fills it in automatically, twitterapi.io needs it set by hand.
    my_handle: str = ""

    twitterapi_io_key: str = ""
    twitterapi_io_base_url: str = "https://api.twitterapi.io"

    x_client_id: str = ""
    x_client_secret: str = ""
    x_api_base_url: str = "https://api.x.com"

    anthropic_api_key: str = ""

    # --- behaviour ----------------------------------------------------------
    sync_schedule_mode: str = "daily"  # daily | interval | off
    sync_daily_time: str = "06:00"  # local time, for mode=daily
    sync_interval_hours: int = 24  # for mode=interval
    unfollow_confirmations: int = 2  # consecutive misses before "unfollowed"
    count_tolerance_pct: float = 3.0
    count_tolerance_abs: int = 5
    profile_refresh_days: int = 14
    profile_refresh_batch: int = 500
    followback_deadline_days: int = 7

    # How to call the model: claude_cli (Claude Code subscription), codex_cli
    # (ChatGPT/Codex subscription) or anthropic_api (pay per token).
    analysis_provider: str = "claude_cli"
    # Model name passed to the provider; empty = provider default
    # (claude_cli: your subscription default, codex_cli: codex default,
    # anthropic_api: claude-opus-5-5).
    analysis_model: str = ""
    claude_cli_path: str = "claude"
    codex_cli_path: str = "codex"
    analysis_timeout_seconds: int = 300
    analysis_tweets: int = 50
    analysis_include_replies: bool = False
    analysis_goal: str = Field(
        default=(
            "I am a founder growing my presence on X (Twitter). I am looking for people to network "
            "with: founders, investors, marketers, developers and content creators from the startup "
            "scene. My routine: follow, comment on their tweets, wait for a follow-back. Rate how "
            "interesting this person is for that kind of networking and how best to start a conversation."
        )
    )

    worker_concurrency: int = 3
    worker_poll_seconds: float = 2.0

    @property
    def data_dir(self) -> Path:
        return BACKEND_DIR / "data"


settings = Settings()
