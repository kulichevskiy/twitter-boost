# Twitter Boost CRM

A personal CRM for your own X (Twitter) account, built for founders who grow their
audience by hand: follow interesting people, comment on their posts, see who follows
back, unfollow those who never do.

It keeps daily snapshots of your followers and following lists, turns the differences
into a timeline of events ("@someone followed you", "you unfollowed @someone"), tracks
every contact through a small networking pipeline, and, on demand, pulls a person's
recent tweets and asks an LLM for a structured verdict: who they are, how relevant they
are for you, and how to start a conversation. Everything is available to AI agents
through REST and MCP, so Claude Code or any MCP client can work your pipeline with you.

Self-hosted, single user, SQLite. Runs fine on a Mac mini in a closet.

![Overview](docs/screenshots/1-overview.png)

![Person analysis](docs/screenshots/3-person-analysis.png)

## Features

- **Follower history X never gives you.** Full snapshots of both lists, diffed on every
  sync into `followed_me`, `unfollowed_me`, `i_followed`, `i_unfollowed` and
  `profile_changed` events. Unfollows are confirmed over two consecutive syncs and a
  size sanity check protects you from a provider returning a half list.
- **Networking pipeline.** `candidate → followed → engaged → followed_back`, or
  `no_response` after a configurable deadline, plus `unfollowed`, `lost`, `ignored`.
  Transitions happen automatically from events; you can override them by hand.
- **Tweets and analysis on demand.** Fetch someone's last N tweets and get a structured
  verdict (persona, topics, 1–5 relevance score, reasons, behaviour, a draft opener in
  their language, red flags). Results are cached by input hash so re-runs are free.
- **Pluggable model backends.** Claude Code CLI (uses your Anthropic subscription),
  Codex CLI (uses your ChatGPT subscription) or the Anthropic API with a key.
- **Pluggable data sources.** Official X API v2 (OAuth 2.0 PKCE) and
  [twitterapi.io](https://twitterapi.io), selectable per operation. A synthetic `fake`
  source lets you try the UI without any keys.
- **Filters everywhere.** One `PeopleFilter` object powers the table, saved views, bulk
  actions, REST and MCP: relation, stage, tags, follower range, score, events since,
  free text.
- **Agent-ready.** REST with OpenAPI, and an MCP server with 15 tools
  (`search_people`, `get_pipeline`, `set_stage`, `analyze`, …).
- **Job queue with a worker.** Syncs, tweet fetches and analyses run in the background
  with retries, deduplication and a daily schedule. No Redis, just SQLite.

## How it works

![Architecture](docs/architecture.svg)

1. **Sync** (scheduled or on demand): the worker pulls your full followers and
   following lists from the configured source, hydrates profiles of people it has not
   seen, diffs against the previous state and writes events and pipeline transitions.
2. **Fetch tweets** (on demand, per person or in bulk): the last N tweets are stored
   locally.
3. **Analyze** (on demand): profile plus stored tweets go to an LLM with a strict JSON
   schema; the verdict (persona, topics, 1–5 score, reasons, behaviour, opener, red
   flags) is saved and shown on the person card and in filters. The model runs through
   whichever provider you pick: Claude Code CLI or Codex CLI on your subscription, or the
   Anthropic API with a key.
4. **You act**: follow, comment, wait; the next sync records what happened.

Pieces:

- **Frontend**: Next.js 16, React 19, shadcn/ui. A route handler proxies `/api/crm/*`
  to the backend and adds the bearer token, so the browser never sees it.
- **Backend**: FastAPI, SQLAlchemy 2, Alembic, SQLite in WAL mode. Two processes from
  the same code: `crm serve` (API + MCP) and `crm worker` (jobs and schedule).
- **Sources** (`backend/app/sources/`): one `Source` protocol, adapters for the official
  X API and twitterapi.io, plus a synthetic one for development.
- **LLM providers** (`backend/app/services/llm.py`): one function per backend, all
  returning the same validated `AnalysisResult`.
- The sync algorithm and the data model are documented in
  [`backend/README.md`](backend/README.md).

## Requirements

- macOS or Linux
- Node.js 20+ and npm
- Python 3.12+ and [uv](https://docs.astral.sh/uv/) (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- One data source:
  - a [twitterapi.io](https://twitterapi.io) API key (pay as you go, cents per sync), and/or
  - an X developer app with OAuth 2.0 (pay-per-use; reads of your own lists are cheap)
- One analysis provider:
  - [Claude Code](https://claude.com/claude-code) logged in on the machine (`claude /login`), or
  - [Codex CLI](https://github.com/openai/codex) logged in (`codex login`), or
  - an Anthropic API key

## Quick start

```bash
git clone https://github.com/kulichevskiy/twitter-boost.git
cd twitter-boost

# backend
cd backend
cp .env.example .env            # edit: MY_HANDLE, TWITTERAPI_IO_KEY, CRM_API_TOKEN (uv run crm token)
uv sync
uv run crm serve                # http://localhost:8000, applies migrations on start
uv run crm worker               # in a second terminal

# frontend
cd ..
npm install
cp .env.example .env.local      # CRM_API_TOKEN must match backend/.env
npm run dev                     # http://localhost:3100
```

Open `http://localhost:3100/crm`, press **Sync now**. The first sync is a baseline (no
events yet); from the second one on you get diffs. Then open a person and press
**Analyze**.

Want to look around before spending anything? Set `SOURCE_LISTS=fake`,
`SOURCE_TWEETS=fake`, `SOURCE_PROFILES=fake` in `backend/.env`: the fake source generates a
stable population and mutates it a little on every sync.

## Configuration

Every setting lives in `backend/.env` (see [`backend/.env.example`](backend/.env.example))
and most can also be changed on the **Settings** page. Values saved from the UI are stored
in SQLite and override the file; secrets are shown masked.

### Credentials

| What | Where to get it | Keys |
| --- | --- | --- |
| Your handle | without `@`; filled automatically when you connect X | `MY_HANDLE` |
| twitterapi.io | twitterapi.io → Dashboard → API key | `TWITTERAPI_IO_KEY` |
| X OAuth 2.0 app | developer.x.com → your app → Keys and tokens → OAuth 2.0 | `X_CLIENT_ID`, `X_CLIENT_SECRET` |
| Analysis provider | see below | `ANALYSIS_PROVIDER`, `ANALYSIS_MODEL`, `ANTHROPIC_API_KEY` |
| API / MCP token | `uv run crm token`; same value in `backend/.env` and `.env.local` | `CRM_API_TOKEN` |

### Data sources

Three operations, each mapped to a provider: `SOURCE_LISTS` (followers/following),
`SOURCE_TWEETS`, `SOURCE_PROFILES`. Values: `twitterapi`, `x`, `fake`.

| | X API (pay-per-use, Oct 2026) | twitterapi.io |
| --- | --- | --- |
| Your own follower/following lists | $0.001 per account ("owned reads") | ~$0.00001 per entry |
| Someone else's profile | $0.010 | ~$0.00001 (batched) |
| One tweet | $0.005 | $0.00015 |
| Legal footing | official | third party, scrapes X |
| Needs | OAuth app + your login | API key |

A sensible default while your account is small: `SOURCE_LISTS=x` (official, cheap for
your own data, and the OAuth connection is what you would need for write actions later),
`SOURCE_TWEETS=twitterapi`, `SOURCE_PROFILES=twitterapi`. At thousands of followers switch
lists to `twitterapi` too. Prices change; check both providers before relying on these.

### Setting up the X app

1. Create an app at developer.x.com. App permissions: **Read** (or Read and write if you
   plan to add follow/unfollow actions later). Type of app: **Web App, Automated App or
   Bot** (confidential client).
2. Callback URI: `<PUBLIC_BASE_URL>/api/crm/auth/x/callback`, e.g.
   `http://localhost:3100/api/crm/auth/x/callback`. The Settings page shows the exact value.
   Website URL: anything real, e.g. your X profile.
3. Copy the OAuth 2.0 Client ID and Client Secret into Settings → Keys (or `.env`).
4. Settings → X connection → **Connect X**. Scopes requested: `tweet.read users.read
   follows.read offline.access`. Tokens are refreshed automatically.

### Analysis providers

| `ANALYSIS_PROVIDER` | How it runs | Cost |
| --- | --- | --- |
| `claude_cli` (default) | `claude -p --json-schema …`, tools disabled, no session persisted | your Claude subscription |
| `codex_cli` | `codex exec --output-schema … --ephemeral -s read-only` | your ChatGPT subscription |
| `anthropic_api` | Anthropic SDK, structured output, default model `claude-opus-5-5` | per token |

`ANALYSIS_MODEL` is passed through (empty = provider default; `claude_cli` accepts
aliases like `sonnet`). `ANALYSIS_GOAL` is the paragraph that tells the model what you
are looking for; changing it invalidates the analysis cache. `ANALYSIS_TWEETS` (default
50) and `ANALYSIS_INCLUDE_REPLIES` control what the model sees.

### Sync behaviour

| Key | Default | Meaning |
| --- | --- | --- |
| `SYNC_SCHEDULE_MODE` | `daily` | `daily` at `SYNC_DAILY_TIME`, `interval` every `SYNC_INTERVAL_HOURS`, or `off` |
| `UNFOLLOW_CONFIRMATIONS` | `2` | consecutive syncs a person must be missing before an unfollow is recorded |
| `COUNT_TOLERANCE_PCT` / `_ABS` | `3` / `5` | if a fetched list differs from the profile counter by more, the sync is marked `suspicious` and writes no events |
| `FOLLOWBACK_DEADLINE_DAYS` | `7` | how long a contact stays in `followed`/`engaged` before becoming `no_response` |
| `PROFILE_REFRESH_DAYS` / `_BATCH` | `14` / `500` | how often stored profiles are refreshed, and how many per sync |

## Running it for real

Two long-lived processes plus the frontend. On macOS the simplest option is launchd:

```bash
backend/launchd/install.sh      # installs com.twitter-boost.crm-api and crm-worker for your user
npm run build && npm start      # or keep `npm run dev` running; your call
```

Logs go to `backend/data/api.log` and `backend/data/worker.log`. On Linux use two systemd
units running `uv run crm serve` and `uv run crm worker` in `backend/`.

The frontend binds to `0.0.0.0:3100`, so a phone on the same network (or your
[Tailscale](https://tailscale.com) tailnet) can open it. The backend requires the bearer
token on every request when `CRM_API_TOKEN` is set, which it should be if anything but
localhost can reach port 8000.

## Daily use

1. **Overview**: your counters, what changed in the last 7 and 30 days, last sync status,
   queue.
2. **People**: filter (mutual, not following back, fans, by stage, by score, by tag…),
   select rows and run bulk actions: refresh tweets, analyze, set stage, tag. Save a
   filter as a view. Add someone you plan to follow with **Add by @handle**.
3. **Person**: profile, relation history, tweets, the analysis card with a copyable
   opener, notes, tags, and the pipeline card (stage, dates, deadline).
4. **Pipeline**: a board by stage. Overdue contacts (no follow-back by the deadline) are
   highlighted; from the card menu you can mark them unfollowed or ignored.
5. **Events** and **Syncs**: the raw timeline and the job queue with retry/cancel.

Nothing here posts, follows or unfollows on your behalf. The tool records what you did
and tells you what to look at; the clicking is still yours.

## API and MCP for agents

- **REST**: `http://<host>:8000/api/crm/*`, interactive docs at `/api/crm/docs`.
  Header `Authorization: Bearer <CRM_API_TOKEN>`. The same paths work through the
  frontend on `:3100` (the proxy adds the header).
- **MCP** (streamable HTTP): `http://<host>:8000/mcp`, same bearer token.

```bash
# Claude Code
claude mcp add --transport http twitter-crm http://localhost:8000/mcp \
  --header "Authorization: Bearer <CRM_API_TOKEN>"
```

```bash
# Codex CLI (reads the token from an environment variable)
export CRM_API_TOKEN=<CRM_API_TOKEN>
codex mcp add twitter-crm --url http://localhost:8000/mcp --bearer-token-env-var CRM_API_TOKEN
```

Tools: `search_people`, `get_person`, `find_by_handle`, `list_events`, `get_pipeline`,
`set_stage`, `add_note`, `tag_person`, `lookup_handle`, `fetch_tweets`, `analyze`,
`bulk_action`, `run_sync`, `get_job`, `sync_status`. Anything that costs money (sync,
lookup, tweets, analysis) is queued as a job; poll `get_job`.

Example prompt for an agent: *"Find everyone I followed more than 7 days ago who has not
followed back, analyze the ones with 500+ followers, and tag the ones scoring 4 or 5 as
`keep`."*

## What it costs

With ~100 followers and a daily sync on twitterapi.io: about a cent per sync for lists
and new profiles, well under a dollar a month. One analysis fetches ~50 tweets (under a
cent) and spends one model call: free on a subscription provider, a few cents on the API.
At tens of thousands of followers the daily list sync on twitterapi.io is a few dollars a
month; the same on the X API would be hundreds.

## Data and privacy

Everything stays in `backend/data/crm.db`. The tool stores public profile data and
tweets of the people in your lists, your own OAuth tokens, and whatever you type in
notes. Snapshots keep the full id lists per sync (zstd-compressed) so events can be
rebuilt. If you use twitterapi.io, your queries (which accounts you track) go to a third
party; if you use the X API, they go to X. Model providers see the profile and tweets you
send for analysis.

## Development

```bash
cd backend
uv run pytest                   # unit tests against the fake source and mocked HTTP
uv run ruff check app tests
uv run crm sync                 # one sync in the foreground, prints the summary
uv run crm drain                # process queued jobs once, then exit
uv run crm db revision -m "…"   # autogenerate a migration after changing models.py

cd ..
npx tsc --noEmit && npx eslint src && npm run build
```

Project layout:

```
src/app/crm/              CRM pages            src/components/crm/   CRM components
src/app/api/crm/          proxy to the backend src/lib/crm/          DTO types, API client, filters
backend/app/sources/      X API, twitterapi.io, fake adapters behind one Source protocol
backend/app/services/     sync, pipeline, people filters, tweets, analysis, llm providers
backend/app/jobs/         SQLite queue, handlers, worker loop and schedule
backend/app/api/          FastAPI routers        backend/app/mcp.py    MCP tools
backend/alembic/          migrations             backend/tests/        pytest
```

Adding a data provider means implementing `backend/app/sources/base.py` (five methods)
and registering it in `registry.py`. Adding a model backend is one function in
`services/llm.py`.

## Also in this repo

`/course` is the author's private learning cabinet for a Russian-language Twitter
workshop: lesson catalog, video/audio player, transcripts and summaries from `content/`.
It shares the Next.js app but has nothing to do with the CRM, and the media files are not
in git. You can delete `src/app/course`, `src/components/{catalog,player}`,
`src/components/summary.tsx`, `src/content` and `content/` if you only want the CRM.

## Limitations and ideas

- X does not expose follow timestamps, so event time is sync time. Sync more often if
  you need finer resolution (every sync costs a little).
- Single account, single user. Multi-account would need an `account_id` on most tables.
- No write actions yet. Follow/unfollow through the X API (`follows.write`) is the
  obvious next step; twitterapi.io is read-only by design here.
- Analysis prompt and labels are tuned for founder networking. Edit `ANALYSIS_GOAL`
  and `backend/app/services/analysis.py` for other use cases.
