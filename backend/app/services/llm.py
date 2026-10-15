"""Model backends for analysis.

Three ways to get a structured verdict, chosen by the `analysis_provider`
setting:

- claude_cli   `claude -p --json-schema ...`  (Claude Code, uses the subscription login)
- codex_cli    `codex exec --output-schema ...` (Codex CLI, uses the ChatGPT login)
- anthropic_api Anthropic SDK with an API key (pay per token)

All three return (parsed dict, meta dict). CLI backends never get tools and
never persist sessions, so each call is a single stateless model turn.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

from ..sources.types import NotConfigured
from .settings import Effective

log = logging.getLogger(__name__)

PROVIDERS = ("claude_cli", "codex_cli", "anthropic_api")
DEFAULT_API_MODEL = "claude-opus-5-5"
_DENIED_TOOLS = "Bash,Read,Edit,Write,MultiEdit,NotebookEdit,WebSearch,WebFetch,Agent,Glob,Grep,Task,TodoWrite"


class LLMError(RuntimeError):
    """Model call failed in a way that may succeed on retry."""


def _resolve(cmd: str) -> str:
    """Find the binary even when the worker's PATH is minimal (launchd)."""
    if os.path.isabs(cmd):
        return cmd
    found = shutil.which(cmd)
    if found:
        return found
    for candidate in (Path.home() / ".local/bin" / cmd, Path("/usr/local/bin") / cmd, Path("/opt/homebrew/bin") / cmd):
        if candidate.exists():
            return str(candidate)
    raise NotConfigured(f"{cmd} not found on PATH; set the CLI path in settings")


def _clean_env() -> dict[str, str]:
    env = dict(os.environ)
    # Running inside an interactive Claude Code session would otherwise be refused.
    for k in ("CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT"):
        env.pop(k, None)
    env["PATH"] = env.get("PATH", "") + os.pathsep + str(Path.home() / ".local/bin") + ":/usr/local/bin:/opt/homebrew/bin"
    return env


async def _run(cmd: list[str], stdin: str | None, cwd: str, timeout: int) -> tuple[int, str, str]:
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdin=asyncio.subprocess.PIPE if stdin is not None else asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=cwd,
        env=_clean_env(),
    )
    try:
        out, err = await asyncio.wait_for(proc.communicate(stdin.encode() if stdin is not None else None), timeout=timeout)
    except TimeoutError:
        proc.kill()
        raise LLMError(f"{cmd[0]} timed out after {timeout}s") from None
    return proc.returncode or 0, out.decode(errors="replace"), err.decode(errors="replace")


async def complete_json(eff: Effective, system: str, user: str, schema: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    provider = eff.analysis_provider
    if provider == "claude_cli":
        return await _claude_cli(eff, system, user, schema)
    if provider == "codex_cli":
        return await _codex_cli(eff, system, user, schema)
    if provider == "anthropic_api":
        return await _anthropic_api(eff, system, user, schema)
    raise NotConfigured(f"unknown analysis_provider {provider!r}; one of {PROVIDERS}")


# --------------------------------------------------------------------- claude
async def _claude_cli(eff: Effective, system: str, user: str, schema: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    cmd = [
        _resolve(eff.claude_cli_path),
        "-p",
        "--output-format", "json",
        "--json-schema", json.dumps(schema),
        "--no-session-persistence",
        "--disallowedTools", _DENIED_TOOLS,
        "--append-system-prompt", system,
    ]
    if eff.analysis_model:
        cmd += ["--model", eff.analysis_model]
    with tempfile.TemporaryDirectory(prefix="crm-llm-") as cwd:
        code, out, err = await _run(cmd, user, cwd, eff.analysis_timeout_seconds)
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        raise LLMError(f"claude returned non-JSON (exit {code}): {out[:300]} {err[:300]}") from None
    if data.get("is_error"):
        msg = str(data.get("result") or err)[:300]
        if "login" in msg.lower() or "not logged in" in msg.lower() or "api key" in msg.lower():
            raise NotConfigured(f"claude CLI: {msg}. Run `claude /login` on this machine.")
        raise LLMError(f"claude CLI error: {msg}")
    parsed = data.get("structured_output")
    if parsed is None:
        # Older CLIs put the JSON text into result.
        try:
            parsed = json.loads(data.get("result") or "")
        except json.JSONDecodeError:
            raise LLMError(f"claude returned no structured output: {str(data.get('result'))[:300]}") from None
    meta = {
        "provider": "claude_cli",
        "model": eff.analysis_model or "default",
        "usage": data.get("usage"),
        "model_usage": data.get("modelUsage"),
        "cost_usd": data.get("total_cost_usd"),
        "duration_ms": data.get("duration_ms"),
    }
    return parsed, meta


# ---------------------------------------------------------------------- codex
async def _codex_cli(eff: Effective, system: str, user: str, schema: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    with tempfile.TemporaryDirectory(prefix="crm-llm-") as cwd:
        schema_path = Path(cwd) / "schema.json"
        out_path = Path(cwd) / "out.json"
        schema_path.write_text(json.dumps(schema))
        cmd = [
            _resolve(eff.codex_cli_path),
            "exec",
            "--ephemeral",
            "--skip-git-repo-check",
            "-s", "read-only",
            "-C", cwd,
            "--output-schema", str(schema_path),
            "-o", str(out_path),
        ]
        if eff.analysis_model:
            cmd += ["-m", eff.analysis_model]
        cmd.append(f"{system}\n\n---\n\n{user}")
        code, out, err = await _run(cmd, None, cwd, eff.analysis_timeout_seconds)
        text = out_path.read_text() if out_path.exists() else ""
    if not text:
        low = (out + err).lower()
        if "login" in low or "not logged in" in low or "unauthorized" in low:
            raise NotConfigured("codex CLI is not logged in. Run `codex login` on this machine.")
        raise LLMError(f"codex produced no output (exit {code}): {(err or out)[-400:]}")
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        raise LLMError(f"codex output is not JSON: {text[:300]}") from None
    tokens = None
    for line in reversed(out.splitlines()):
        if line.strip().startswith("tokens used"):
            try:
                tokens = out.splitlines()[out.splitlines().index(line) + 1].strip()
            except (ValueError, IndexError):
                pass
            break
    meta = {"provider": "codex_cli", "model": eff.analysis_model or "default", "tokens_used": tokens}
    return parsed, meta


# ------------------------------------------------------------------ anthropic
async def _anthropic_api(eff: Effective, system: str, user: str, schema: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    import anthropic

    try:
        client = anthropic.AsyncAnthropic(api_key=eff.anthropic_api_key or None)
    except TypeError as exc:  # "Could not resolve authentication method"
        raise NotConfigured("Anthropic API key is not set (settings page or ANTHROPIC_API_KEY)") from exc
    model = eff.analysis_model or DEFAULT_API_MODEL
    response = await client.beta.messages.create(
        model=model,
        max_tokens=4000,
        system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": user}],
        output_config={"format": {"type": "json_schema", "schema": schema}},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    )
    if response.stop_reason == "refusal":
        detail = getattr(response, "stop_details", None)
        raise LLMError(f"model refused: {getattr(detail, 'explanation', None) or 'no explanation'}")
    text = next((b.text for b in response.content if b.type == "text"), "")
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        raise LLMError(f"model returned non-JSON: {text[:300]}") from None
    meta = {
        "provider": "anthropic_api",
        "model": response.model or model,
        "usage": response.usage.model_dump() if response.usage else None,
    }
    return parsed, meta
