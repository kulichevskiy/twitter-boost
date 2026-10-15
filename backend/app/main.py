"""FastAPI application. Run with `crm serve` (uvicorn)."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import events, jobs, overview, people, syncs, views
from .api import settings as settings_api
from .api.deps import require_token
from .config import settings as env
from .migrate import upgrade_database

log = logging.getLogger(__name__)


def create_app() -> FastAPI:
    from .mcp import mcp

    mcp_app = mcp.http_app(path="/mcp")

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logging.basicConfig(level=env.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
        upgrade_database()
        async with mcp_app.lifespan(app):
            yield

    app = FastAPI(
        title="Twitter CRM API",
        version="0.1.0",
        description="Followers/following snapshots, relationship events, networking pipeline, tweet analysis.",
        lifespan=lifespan,
        docs_url="/api/crm/docs",
        openapi_url="/api/crm/openapi.json",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[env.public_base_url, "http://localhost:3100", "http://127.0.0.1:3100"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    api_deps = [Depends(require_token)]
    for r in (overview.router, people.router, events.router, syncs.router, jobs.router, settings_api.router, views.router):
        app.include_router(r, prefix="/api/crm", dependencies=api_deps)

    # MCP (streamable HTTP) for agents at exactly /mcp. Mounted at the root so the
    # path is not doubled; FastAPI routes above take precedence. Auth: FastMCP token verifier.
    app.mount("/", mcp_app)
    return app


app = create_app()
