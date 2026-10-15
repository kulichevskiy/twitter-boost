"""Pick the adapter for an operation and manage its lifetime."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Literal

from ..services.settings import Effective
from .base import RequestCounter, Source
from .fake import FakeSource
from .twitterapi_io import TwitterApiIoSource
from .types import NotConfigured
from .x_official import XOfficialSource

Operation = Literal["lists", "tweets", "profiles"]
SOURCE_NAMES = ("twitterapi", "x", "fake")


def source_name_for(eff: Effective, op: Operation) -> str:
    return {"lists": eff.source_lists, "tweets": eff.source_tweets, "profiles": eff.source_profiles}[op]


def build_source(name: str, eff: Effective, counter: RequestCounter) -> Source:
    if name == "twitterapi":
        return TwitterApiIoSource(eff.twitterapi_io_key, eff.twitterapi_io_base_url, counter=counter)
    if name == "x":
        from ..auth.x_oauth import access_token_getter

        return XOfficialSource(access_token_getter(eff), eff.x_api_base_url, counter=counter)
    if name == "fake":
        return FakeSource(counter=counter)
    raise NotConfigured(f"unknown source '{name}'")


@asynccontextmanager
async def open_sources(eff: Effective, ops: list[Operation]) -> AsyncIterator[tuple[dict[Operation, Source], RequestCounter]]:
    """Open one adapter instance per distinct provider and map operations onto them."""
    counter = RequestCounter()
    instances: dict[str, Source] = {}
    mapping: dict[Operation, Source] = {}
    try:
        for op in ops:
            name = source_name_for(eff, op)
            if name not in instances:
                instances[name] = build_source(name, eff, counter)
            mapping[op] = instances[name]
        yield mapping, counter
    finally:
        for src in instances.values():
            await src.aclose()
