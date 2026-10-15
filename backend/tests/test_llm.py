import json

import pytest

from app.services import llm
from app.services.settings import Effective
from app.sources.types import NotConfigured


def _eff(**over) -> Effective:
    from app.db import session_scope
    from app.services.settings import load_effective

    with session_scope() as s:
        base = load_effective(s).model_dump()
    base.update(over)
    return Effective(**base)


SCHEMA = {"type": "object", "properties": {"a": {"type": "integer"}}, "required": ["a"], "additionalProperties": False}


async def test_claude_cli_parses_structured_output(monkeypatch):
    async def fake_run(cmd, stdin, cwd, timeout):
        assert "--json-schema" in cmd and "--no-session-persistence" in cmd and "--model" in cmd
        assert stdin.startswith("hello")
        return 0, json.dumps({"is_error": False, "structured_output": {"a": 7}, "usage": {"output_tokens": 3}, "total_cost_usd": 0.01}), ""

    monkeypatch.setattr(llm, "_run", fake_run)
    monkeypatch.setattr(llm, "_resolve", lambda c: c)
    parsed, meta = await llm.complete_json(_eff(analysis_provider="claude_cli", analysis_model="sonnet"), "sys", "hello", SCHEMA)
    assert parsed == {"a": 7} and meta["provider"] == "claude_cli" and meta["cost_usd"] == 0.01


async def test_claude_cli_not_logged_in_is_not_configured(monkeypatch):
    async def fake_run(cmd, stdin, cwd, timeout):
        return 1, json.dumps({"is_error": True, "result": "Not logged in · Please run /login"}), ""

    monkeypatch.setattr(llm, "_run", fake_run)
    monkeypatch.setattr(llm, "_resolve", lambda c: c)
    with pytest.raises(NotConfigured):
        await llm.complete_json(_eff(analysis_provider="claude_cli"), "sys", "hello", SCHEMA)


async def test_codex_cli_reads_output_file(monkeypatch):
    async def fake_run(cmd, stdin, cwd, timeout):
        out = next(cmd[i + 1] for i, c in enumerate(cmd) if c == "-o")
        assert "--output-schema" in cmd and "--ephemeral" in cmd and stdin is None
        with open(out, "w") as f:
            json.dump({"a": 1}, f)
        return 0, 'codex\n{"a":1}\ntokens used\n1.234\n', ""

    monkeypatch.setattr(llm, "_run", fake_run)
    monkeypatch.setattr(llm, "_resolve", lambda c: c)
    parsed, meta = await llm.complete_json(_eff(analysis_provider="codex_cli"), "sys", "hello", SCHEMA)
    assert parsed == {"a": 1} and meta["tokens_used"] == "1.234"


async def test_unknown_provider():
    with pytest.raises(NotConfigured):
        await llm.complete_json(_eff(analysis_provider="nope"), "s", "u", SCHEMA)


def test_missing_binary_is_not_configured():
    with pytest.raises(NotConfigured):
        llm._resolve("definitely-not-a-binary-xyz")
