from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from ..auth import x_oauth
from ..schemas import STAGES, SettingsIn, SettingsOut
from ..services.settings import (
    EDITABLE_KEYS,
    SECRET_KEYS,
    Effective,
    load_effective,
    load_overrides,
    mask,
    save_overrides,
)
from ..sources.registry import SOURCE_NAMES
from .deps import DB, EFF

router = APIRouter(tags=["settings"])


def _out(session: Session, eff: Effective) -> SettingsOut:
    overrides = load_overrides(session)
    values: dict[str, Any] = {}
    for k in EDITABLE_KEYS:
        v = getattr(eff, k)
        values[k] = mask(v) if k in SECRET_KEYS else v
    return SettingsOut(
        values=values,
        overrides=sorted(overrides.keys()),
        x=x_oauth.status(session),
        redirect_uri=x_oauth.redirect_uri(eff),
        sources=list(SOURCE_NAMES),
        stages=list(STAGES),
        configured={
            "twitterapi": bool(eff.twitterapi_io_key),
            "x": bool(eff.x_client_id) and x_oauth.status(session)["connected"],
            "x_app": bool(eff.x_client_id),
            "anthropic": bool(eff.anthropic_api_key),
            "my_handle": bool(eff.my_handle),
        },
    )


@router.get("/settings", response_model=SettingsOut)
def get_settings(session: Session = DB, eff: Effective = EFF):
    return _out(session, eff)


@router.put("/settings", response_model=SettingsOut)
def put_settings(body: SettingsIn, session: Session = DB):
    unknown = [k for k in body.values if k not in EDITABLE_KEYS]
    if unknown:
        raise HTTPException(422, f"unknown keys: {unknown}")
    # Masked secrets echoed back unchanged must not overwrite the real value.
    clean = {k: v for k, v in body.values.items() if not (k in SECRET_KEYS and isinstance(v, str) and "…" in v)}
    for k in ("source_lists", "source_tweets", "source_profiles"):
        if k in clean and clean[k] not in SOURCE_NAMES:
            raise HTTPException(422, f"{k}: unknown source {clean[k]!r}")
    save_overrides(session, clean)
    session.commit()
    return _out(session, load_effective(session))


@router.get("/auth/x/start")
def x_start(session: Session = DB, eff: Effective = EFF) -> dict[str, str]:
    try:
        url = x_oauth.begin(session, eff)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    session.commit()
    return {"url": url}


@router.get("/auth/x/callback")
async def x_callback(code: str | None = None, state: str | None = None, error: str | None = None, session: Session = DB, eff: Effective = EFF):
    target = eff.public_base_url.rstrip("/") + "/crm/settings"
    if error or not code or not state:
        return RedirectResponse(f"{target}?x_error={error or 'missing_code'}")
    try:
        await x_oauth.complete(session, eff, code, state)
        session.commit()
    except ValueError as exc:
        session.rollback()
        return RedirectResponse(f"{target}?x_error={str(exc)[:200]}")
    return RedirectResponse(f"{target}?x=connected")


@router.delete("/auth/x")
async def x_disconnect(session: Session = DB, eff: Effective = EFF) -> dict[str, bool]:
    await x_oauth.disconnect(session, eff)
    session.commit()
    return {"connected": False}
