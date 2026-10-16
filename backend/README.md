# Twitter CRM backend

FastAPI + SQLite service behind the `/crm` section of the Next.js app. It keeps
snapshots of my followers / following lists, derives follow and unfollow events
from the differences, tracks a networking pipeline per contact, fetches tweets
and asks Claude for a structured verdict on demand, and exposes everything as
REST (`/api/crm/*`) and MCP (`/mcp`) for agents.

## Run

```bash
cd backend
cp .env.example .env          # fill in keys, or do it later on the settings page
uv sync
uv run crm serve              # API on :8000, runs migrations on start
uv run crm worker             # job queue + scheduled syncs (second terminal)
```

Useful one-offs:

```bash
uv run crm sync               # one full sync in the foreground, prints the summary
uv run crm drain              # process queued jobs once and exit
uv run crm token              # generate a CRM_API_TOKEN
uv run crm db revision -m "…" # autogenerate a migration after changing models.py
uv run pytest                 # tests run against the synthetic "fake" source
```

`launchd/install.sh` installs the API and the worker as launchd agents for the current
user (it fills in the `uv` path and the repo location in the plist templates).

## Credentials

Everything can be entered on `/crm/settings` in the UI (stored in SQLite,
overrides `.env`) or in `backend/.env`:

| What | Where to get it | Keys |
|---|---|---|
| twitterapi.io | https://twitterapi.io/dashboard | `TWITTERAPI_IO_KEY`, plus `MY_HANDLE` |
| Official X API (OAuth 2.0) | https://developer.x.com/en/portal, app type "Web App", callback `PUBLIC_BASE_URL + /api/crm/auth/x/callback` | `X_CLIENT_ID`, `X_CLIENT_SECRET`, then "Подключить X" on the settings page |
| Model for analysis | default `claude_cli`: Claude Code CLI logged in on this machine (`claude /login`); or `codex_cli` (`codex login`); or `anthropic_api` with a key | `ANALYSIS_PROVIDER`, `ANALYSIS_MODEL`, `ANTHROPIC_API_KEY` |
| API/MCP auth | `uv run crm token` | `CRM_API_TOKEN` (also in the frontend `.env.local`) |

`SOURCE_LISTS`, `SOURCE_TWEETS`, `SOURCE_PROFILES` pick the adapter per
operation: `twitterapi`, `x` or `fake`. Recommended: `x` for lists while the
account is small (owned reads are cheap and legal), `twitterapi` for tweets and
profiles. Switch lists to `twitterapi` when the account grows.

## How a sync works (`services/sync.py`)

1. Fetch my profile from the lists source (gives the expected follower and
   following counts).
2. Pull both lists completely. twitterapi.io returns follower ids only (5000 per
   call) and following with profiles (200 per call); the X API returns profiles
   for both (1000 per call).
3. Hydrate profiles for ids never seen before, plus up to
   `PROFILE_REFRESH_BATCH` stale ones (older than `PROFILE_REFRESH_DAYS`).
4. Sanity check: if a list size differs from the profile counter by more than
   `max(COUNT_TOLERANCE_ABS, COUNT_TOLERANCE_PCT%)`, the sync is stored as
   `suspicious` and no relation changes or events are written. Snapshots are
   kept anyway.
5. Diff against `relations`: new ids become active relations and
   `followed_me` / `i_followed` events; ids present reset `missing_streak`; ids
   missing increment it and only after `UNFOLLOW_CONFIRMATIONS` consecutive
   misses become inactive with an `unfollowed_me` / `i_unfollowed` event.
   The very first sync is a `baseline` and writes no per-person events.
6. Profile field changes (handle, name, bio, location, url) become
   `profile_changed` events.
7. Pipeline reactions: `i_followed` -> stage `followed` with a deadline
   (`FOLLOWBACK_DEADLINE_DAYS`), `followed_me` while waiting -> `followed_back`,
   `i_unfollowed` -> `unfollowed`, `unfollowed_me` after mutual -> `lost`.
   Waiting contacts past their deadline become `no_response`.
8. Full id lists per direction are stored zstd-compressed in `snapshots`, so
   events can be rebuilt later if a provider glitch slips through.

## Jobs

`jobs` table + one worker process. Types: `sync_full` (exclusive), `fetch_tweets`,
`analyze`, `fetch_and_analyze`, `refresh_profiles`, `lookup`, `bulk` (fans out).
Duplicates of a queued job are collapsed; failures retry with backoff unless the
error is a configuration problem or an exhausted balance. The worker also runs
the schedule (`SYNC_SCHEDULE_MODE` daily/interval/off).

## Analysis

`services/analysis.py` builds the prompt (profile plus the last `ANALYSIS_TWEETS`
tweets) and `services/llm.py` runs it through the selected provider with the
JSON schema of `schemas.AnalysisResult`:

- `claude_cli`: `claude -p --output-format json --json-schema … --no-session-persistence`,
  tools disabled; uses the Claude Code login on this machine (subscription, no key).
- `codex_cli`: `codex exec --ephemeral -s read-only --output-schema … -o …`; uses the
  Codex/ChatGPT login.
- `anthropic_api`: Anthropic SDK with `output_config.format`, default model
  `claude-opus-5-5`, server-side refusal fallbacks on.

Results are cached by a hash of prompt version, provider, model, goal text, bio
and tweet ids. The worker's PATH gets `~/.local/bin` appended so launchd finds
the CLIs; override with `CLAUDE_CLI_PATH` / `CODEX_CLI_PATH`.

## MCP

Streamable HTTP at `http://<host>:8000/mcp`, bearer token = `CRM_API_TOKEN`.
Tools: `search_people`, `get_person`, `find_by_handle`, `list_events`,
`get_pipeline`, `set_stage`, `add_note`, `tag_person`, `lookup_handle`,
`fetch_tweets`, `analyze`, `bulk_action`, `run_sync`, `get_job`, `sync_status`.
Paid actions (lookups, tweets, analysis, sync) are queued jobs; poll `get_job`.

Claude Code: `claude mcp add --transport http twitter-crm http://localhost:8000/mcp --header "Authorization: Bearer <token>"`.
