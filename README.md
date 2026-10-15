# Twitter Boost

Два раздела в одном приложении:

- **/course** — учебный кабинет: 30 уроков, нарезанных из записи воркшопа «Twitter для
  фаундера» (рубрикатор, видео/аудио-плеер с фоновым воспроизведением, саммари).
- **/crm** — CRM по собственному аккаунту в X: снапшоты списков фолловеров и подписок,
  история событий (кто кого когда зафоловил/отфоловил), пайплайн нетворкинга,
  подгрузка твитов и разбор человека через Claude по запросу, REST и MCP для агента.

Фронтенд — Next.js 16 + shadcn/ui. Бэкенд CRM — FastAPI + SQLite в `backend/`.

## Запуск

```bash
# 1. фронтенд
npm install
cp .env.example .env.local        # CRM_BACKEND_URL, CRM_API_TOKEN
npm run dev                       # http://localhost:3100, слушает 0.0.0.0 (доступно по tailnet)

# 2. бэкенд (нужен uv: https://docs.astral.sh/uv/)
cd backend
cp .env.example .env              # ключи и настройки, см. ниже
uv sync
uv run crm serve                  # API на :8000, миграции применяются при старте
uv run crm worker                 # отдельный процесс: расписание синков, твиты, анализ
```

Полезные команды бэкенда: `uv run crm sync` (один синк прямо сейчас), `uv run crm drain`
(выполнить очередь и выйти), `uv run crm token` (сгенерировать `CRM_API_TOKEN`),
`uv run crm db upgrade`.

Для прод-сборки фронтенда: `npm run build && npm start`.

## Куда вводить креды

Два равноправных способа: файл `backend/.env` или страница **/crm/settings** (значения со
страницы хранятся в SQLite и перекрывают `.env`, секреты показываются замаскированными).

| Что | Где взять | Ключ в `.env` |
| --- | --- | --- |
| Мой @handle | без `@`; при подключении X подставляется сам | `MY_HANDLE` |
| twitterapi.io | twitterapi.io → Dashboard → API key | `TWITTERAPI_IO_KEY` |
| X OAuth 2.0 app | developer.x.com → App → Keys and tokens; callback URL показан на странице настроек (`<PUBLIC_BASE_URL>/api/crm/auth/x/callback`) | `X_CLIENT_ID`, `X_CLIENT_SECRET` |
| Модель для разбора | по умолчанию Claude Code CLI с твоей подпиской (`claude /login` на этой машине); альтернативы: Codex CLI (`codex login`) или Anthropic API-ключ | `ANALYSIS_PROVIDER`, `ANALYSIS_MODEL`, `ANTHROPIC_API_KEY` только для `anthropic_api` |
| Токен API/MCP | `uv run crm token`, одинаковый в `backend/.env` и `.env.local` | `CRM_API_TOKEN` |

Какой адаптер что обслуживает задаётся `SOURCE_LISTS`, `SOURCE_TWEETS`, `SOURCE_PROFILES`
(`twitterapi` | `x` | `fake`). Рекомендация: списки через X API (owned reads), твиты и
профили через twitterapi.io. `fake` — синтетические данные для проверки UI без ключей.

## Как устроена CRM

- **Синк** (`backend/app/services/sync.py`): забирает оба списка целиком, сверяет размер с
  счётчиками профиля (расхождение → статус `suspicious`, события не пишутся), догружает
  профили новых людей, сравнивает с прошлым состоянием и пишет события `followed_me`,
  `unfollowed_me`, `i_followed`, `i_unfollowed`, `profile_changed`. Отписка фиксируется только
  после N синков подряд без человека в списке. Снапшоты хранятся целиком (zstd).
- **Пайплайн**: `candidate → followed → engaged → followed_back | no_response → unfollowed`,
  плюс `lost` (отписался после взаимности) и `ignored`. Переходы делает синк по событиям,
  дедлайн ответного фоллоу настраивается.
- **Твиты и анализ** — только по кнопке (или через API/MCP), через очередь задач в SQLite.
  Разбор кэшируется по хэшу входа.
- **Фильтр** — один объект `PeopleFilter` для таблицы, REST и MCP.

## API для агента

- REST: `http://<host>:8000/api/crm/*`, OpenAPI на `/api/crm/docs`. Через Next доступно тем же
  путём на :3100 (прокси добавляет bearer).
- MCP (streamable HTTP): `http://<host>:8000/mcp`, заголовок `Authorization: Bearer <CRM_API_TOKEN>`.
  Инструменты: `search_people`, `get_person`, `find_by_handle`, `list_events`, `get_pipeline`,
  `set_stage`, `add_note`, `tag_person`, `lookup_handle`, `fetch_tweets`, `analyze`, `bulk_action`,
  `run_sync`, `get_job`, `sync_status`.

## Курс

На телефоне открывай `http://<tailscale-имя-машины>:3100/course`; добавь на экран «Домой» в
Safari — манифест стартует с `/course`. В уроке переключи тумблер **Аудио**: один общий
`<audio>` живёт в корневом layout, не пропадает при переходах, управляется с локскрина и сам
переключается на следующий урок. Прогресс, режим и скорость хранятся в `localStorage`.

## Структура

```
video/                    нарезанные главы (NN_slug.mp4) и аудио (video/audio/NN_slug.m4a); в git не попадают
content/transcripts/      транскрипт по главам
content/summaries/        саммари уроков в Markdown
src/content/              данные уроков: chapters.generated.ts (таймкоды) + lessons.ts (рубрики)
src/app/course/           рубрикатор и страницы уроков
src/app/crm/              страницы CRM
src/app/api/media/        отдача медиа с HTTP Range
src/app/api/crm/          прокси к FastAPI с bearer-токеном
src/components/player/    PlayerProvider (глобальный аудио), LessonPlayer, MiniPlayer
src/components/catalog/   рубрикатор с прогрессом
src/components/crm/       компоненты CRM
src/lib/crm/              типы DTO, клиент API, сериализация фильтра, форматирование
backend/app/              FastAPI: sources/ (адаптеры), services/ (синк, пайплайн, анализ),
                          jobs/ (очередь и воркер), api/ (роутеры), mcp.py, cli.py
backend/data/crm.db       SQLite (в git не попадает)
```

Главы 08 и 15 — перерывы, в рубрикатор не включены.
