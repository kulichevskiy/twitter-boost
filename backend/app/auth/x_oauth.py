"""OAuth 2.0 Authorization Code with PKCE for the official X API.

Authorize: https://x.com/i/oauth2/authorize   Token: https://api.x.com/2/oauth2/token
Confidential client (client secret set) authenticates with HTTP Basic; a
public client sends client_id in the body.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import logging
import secrets
from collections.abc import Awaitable, Callable
from datetime import timedelta
from typing import Any
from urllib.parse import urlencode

import httpx
from sqlalchemy.orm import Session

from ..db import session_scope
from ..models import Account, Setting, XToken, utcnow
from ..services.settings import Effective

log = logging.getLogger(__name__)

AUTHORIZE_URL = "https://x.com/i/oauth2/authorize"
TOKEN_PATH = "/2/oauth2/token"
REVOKE_PATH = "/2/oauth2/revoke"
SCOPES = ["tweet.read", "users.read", "follows.read", "offline.access"]
PENDING_KEY = "x_oauth_pending"
REDIRECT_PATH = "/api/crm/auth/x/callback"

_refresh_lock = asyncio.Lock()


def redirect_uri(eff: Effective) -> str:
    return eff.public_base_url.rstrip("/") + REDIRECT_PATH


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def begin(session: Session, eff: Effective) -> str:
    """Store a fresh state/verifier pair and return the authorize URL."""
    if not eff.x_client_id:
        raise ValueError("X client id is not configured")
    state = secrets.token_urlsafe(24)
    verifier = secrets.token_urlsafe(64)
    challenge = _b64url(hashlib.sha256(verifier.encode()).digest())
    row = session.get(Setting, PENDING_KEY)
    payload: dict[str, Any] = {"state": state, "verifier": verifier, "created_at": utcnow().isoformat()}
    if row is None:
        session.add(Setting(key=PENDING_KEY, value=payload))
    else:
        row.value = payload
    session.flush()
    params = {
        "response_type": "code",
        "client_id": eff.x_client_id,
        "redirect_uri": redirect_uri(eff),
        "scope": " ".join(SCOPES),
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    return f"{AUTHORIZE_URL}?{urlencode(params)}"


def _auth_for(eff: Effective) -> tuple[httpx.BasicAuth | None, dict[str, str]]:
    if eff.x_client_secret:
        return httpx.BasicAuth(eff.x_client_id, eff.x_client_secret), {}
    return None, {"client_id": eff.x_client_id}


async def complete(session: Session, eff: Effective, code: str, state: str) -> XToken:
    """Exchange the code, store the token, hydrate my account."""
    row = session.get(Setting, PENDING_KEY)
    pending = row.value if row is not None else None
    if not pending or pending.get("state") != state:
        raise ValueError("OAuth state mismatch, start again")
    auth, extra = _auth_for(eff)
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri(eff),
        "code_verifier": pending["verifier"],
        **extra,
    }
    async with httpx.AsyncClient(base_url=eff.x_api_base_url, timeout=30) as client:
        resp = await client.post(TOKEN_PATH, data=data, auth=auth)
        if resp.status_code >= 400:
            raise ValueError(f"token exchange failed: {resp.status_code} {resp.text[:300]}")
        tok = resp.json()
        token = _store_token(session, tok)
        me = await client.get(
            "/2/users/me",
            params={"user.fields": "id,username,name,profile_image_url,public_metrics"},
            headers={"authorization": f"Bearer {token.access_token}"},
        )
    if me.status_code < 400:
        u = me.json().get("data") or {}
        token.user_id = u.get("id")
        token.handle = u.get("username")
        acc = session.get(Account, 1) or Account(id=1)
        acc.user_id = token.user_id
        acc.handle = token.handle
        acc.name = u.get("name")
        acc.avatar_url = (u.get("profile_image_url") or "").replace("_normal.", "_400x400.") or None
        m = u.get("public_metrics") or {}
        acc.followers_count = m.get("followers_count")
        acc.following_count = m.get("following_count")
        session.add(acc)
        handle_row = session.get(Setting, "my_handle")
        if token.handle and (handle_row is None or not handle_row.value):
            session.add(Setting(key="my_handle", value=token.handle)) if handle_row is None else setattr(
                handle_row, "value", token.handle
            )
    session.delete(row)
    session.flush()
    return token


def _store_token(session: Session, tok: dict[str, Any]) -> XToken:
    token = session.get(XToken, 1) or XToken(id=1, access_token="")
    token.access_token = tok["access_token"]
    if tok.get("refresh_token"):
        token.refresh_token = tok["refresh_token"]
    token.expires_at = utcnow() + timedelta(seconds=int(tok.get("expires_in", 7200)))
    token.scopes = tok.get("scope")
    session.add(token)
    session.flush()
    return token


async def refresh(eff: Effective) -> str | None:
    async with _refresh_lock:
        with session_scope() as session:
            token = session.get(XToken, 1)
            if token is None:
                return None
            if token.expires_at and token.expires_at > utcnow() + timedelta(minutes=2):
                return token.access_token
            if not token.refresh_token:
                return token.access_token
            auth, extra = _auth_for(eff)
            async with httpx.AsyncClient(base_url=eff.x_api_base_url, timeout=30) as client:
                resp = await client.post(
                    TOKEN_PATH,
                    data={"grant_type": "refresh_token", "refresh_token": token.refresh_token, **extra},
                    auth=auth,
                )
            if resp.status_code >= 400:
                log.error("X token refresh failed: %s %s", resp.status_code, resp.text[:300])
                return token.access_token
            _store_token(session, resp.json())
            return session.get(XToken, 1).access_token


def access_token_getter(eff: Effective) -> Callable[[], Awaitable[str]]:
    async def _get() -> str:
        tok = await refresh(eff)
        return tok or ""

    return _get


def status(session: Session) -> dict[str, Any]:
    token = session.get(XToken, 1)
    if token is None:
        return {"connected": False}
    return {
        "connected": True,
        "user_id": token.user_id,
        "handle": token.handle,
        "scopes": token.scopes,
        "expires_at": token.expires_at,
        "has_refresh_token": bool(token.refresh_token),
    }


async def disconnect(session: Session, eff: Effective) -> None:
    token = session.get(XToken, 1)
    if token is None:
        return
    auth, extra = _auth_for(eff)
    try:
        async with httpx.AsyncClient(base_url=eff.x_api_base_url, timeout=15) as client:
            await client.post(REVOKE_PATH, data={"token": token.access_token, **extra}, auth=auth)
    except httpx.HTTPError:  # best effort
        pass
    session.delete(token)
    session.flush()
