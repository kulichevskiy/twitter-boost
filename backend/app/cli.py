"""Command line: `uv run crm --help`."""

from __future__ import annotations

import asyncio
import json
import logging

import typer

from .config import settings as env

app = typer.Typer(no_args_is_help=True, help="Twitter CRM backend")
db_app = typer.Typer(help="Database")
app.add_typer(db_app, name="db")


def _log() -> None:
    logging.basicConfig(level=env.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@app.command()
def serve(host: str = env.host, port: int = env.port, reload: bool = False) -> None:
    """Run the API server."""
    import uvicorn

    uvicorn.run("app.main:app", host=host, port=port, reload=reload, log_level=env.log_level.lower())


@app.command()
def worker() -> None:
    """Run the job worker (sync schedule, tweets, analysis)."""
    from .jobs.worker import main

    asyncio.run(main())


@app.command()
def sync(trigger: str = "cli") -> None:
    """Run one full sync right now, in this process."""
    _log()
    from .db import session_scope
    from .migrate import upgrade_database
    from .models import Sync
    from .services.settings import load_effective
    from .services.sync import run_sync

    upgrade_database()
    with session_scope() as session:
        eff = load_effective(session)
    sync_id = asyncio.run(run_sync(eff, trigger=trigger))
    with session_scope() as session:
        s = session.get(Sync, sync_id)
        typer.echo(
            json.dumps(
                {
                    "id": s.id,
                    "status": s.status,
                    "kind": s.kind,
                    "followers": s.followers_total,
                    "following": s.following_total,
                    "added_followers": s.added_followers,
                    "removed_followers": s.removed_followers,
                    "added_following": s.added_following,
                    "removed_following": s.removed_following,
                    "profiles_refreshed": s.profiles_refreshed,
                    "requests": s.requests,
                    "error": s.error,
                    "notes": s.notes,
                },
                ensure_ascii=False,
                indent=2,
            )
        )


@app.command()
def drain() -> None:
    """Process queued jobs until the queue is empty, then exit."""
    _log()
    from .jobs.worker import Worker
    from .migrate import upgrade_database

    upgrade_database()
    n = asyncio.run(Worker().run_until_idle())
    typer.echo(f"processed {n} job(s)")


@app.command()
def token() -> None:
    """Print a fresh random value suitable for CRM_API_TOKEN."""
    import secrets

    typer.echo(secrets.token_urlsafe(32))


@db_app.command("upgrade")
def db_upgrade(revision: str = "head") -> None:
    _log()
    from .migrate import upgrade_database

    upgrade_database(revision)
    typer.echo("ok")


@db_app.command("revision")
def db_revision(message: str) -> None:
    """Autogenerate a migration from model changes."""
    from alembic import command

    from .migrate import alembic_config

    command.revision(alembic_config(), message=message, autogenerate=True)


if __name__ == "__main__":
    app()
