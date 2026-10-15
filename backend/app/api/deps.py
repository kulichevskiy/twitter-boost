from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from ..config import settings as env
from ..db import get_session
from ..services.settings import Effective, load_effective

PUBLIC_PATHS = {"/api/crm/health", "/api/crm/auth/x/callback"}


def require_token(request: Request) -> None:
    if not env.crm_api_token or request.url.path in PUBLIC_PATHS:
        return
    auth = request.headers.get("authorization", "")
    token = auth[7:] if auth.lower().startswith("bearer ") else request.query_params.get("token", "")
    if token != env.crm_api_token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid or missing bearer token")


def effective(session: Session = Depends(get_session)) -> Effective:
    return load_effective(session)


DB = Depends(get_session)
EFF = Depends(effective)
