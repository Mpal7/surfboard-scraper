# AGENTS.md

Guidance for AI agents working in this repository. Read this before making any change.

## What this project is

Surfboard Scraper scrapes surfboard Ads from Subito.it, stores them in SQLite, and notifies Recipients by email when new boards matching their Filters appear.

- `backend/` — Python / FastAPI: scraping, extraction, storage, email notifications, Celery/Redis scheduling.
- `frontend/` — React 19 + TypeScript + Tailwind (Create React App): read-only marketplace UI.

## Domain language

`CONTEXT.md` (repo root) is the authoritative glossary: Ad, Active Ad, Visible Ad, Recipient, Filter, Refresh, Mail Sent, Email Config. Use these exact terms in code, identifiers, docs, commit messages, and discussion. Do not use the "Avoid" terms listed there.

## Working directory matters

Backend imports are rooted at `backend/` (`from src...`, `from config...`, `from extraction...`, `from scripts...`, `from utils...`). Run **every** backend command (pytest, uvicorn, celery, scripts) from `backend/`, never from the repo root.

The active FastAPI app is `backend/src/main.py` (module `src.main`). `backend/main.py` is a legacy duplicate with no email endpoints — do not extend it. All API work goes in `src/main.py`.

## Repository layout

| Path | Role |
|---|---|
| `backend/src/scraper.py` | Scraping engine: fetch with retries, parse `__NEXT_DATA__`/HTML, filter, store Ads |
| `backend/extraction/extraction.py` | Pure parsing logic: dimensions, liters, price, brand (no HTTP) |
| `backend/extraction/surfboard_parser.py` | Facade over `extraction.py` (`parse_listing`) — import from here |
| `backend/src/models.py` | The `Ad` SQLAlchemy model (single table `ads`) |
| `backend/src/database.py` | Engine, `SessionLocal`, `init_db()`, `get_db()` |
| `backend/src/main.py` | Active FastAPI app: `/ads`, `/ads/filter`, `/refresh`, `/email-config`, `/send_email` |
| `backend/src/sender.py` | Gmail SMTP sending (`send_email`) |
| `backend/src/email_config.py` | Recipient/Filter persistence in `data/email_config.json` |
| `backend/src/email_template.py` | HTML email rendering |
| `backend/src/celery_worker.py` | Celery tasks + beat schedule (randomized nightly scrape, ad-status check) |
| `backend/scripts/check_ads.py` | Marks Ads inactive when their Subito link dies |
| `backend/scripts/update_images.py` | CLI backfill of Ad image URLs |
| `backend/config/settings.py` | Single source of configuration — see below |
| `docs/adr/` | Architecture Decision Records |

## Commands

Backend (from `backend/`; venv at `backend/venv`):

```
venv\Scripts\pip install -r requirements.txt   # setup
venv\Scripts\python -m pytest                  # canonical backend suite
venv\Scripts\python -m pytest tests\test_extraction_logic.py -k liters   # narrowest tests first
venv\Scripts\python -m uvicorn src.main:app --reload                        # run API on :8000
venv\Scripts\python -m celery -A src.celery_worker worker -B --loglevel=info  # needs Redis on localhost:6379/0
venv\Scripts\python -m scripts.check_ads       # maintenance
```

Frontend (from `frontend/`):

```
npm install        # required once; node_modules is not committed
npm start          # dev server on :3000
CI=true npm test   # single test run (plain `npm test` starts watch mode)
npm run build      # also serves as the TypeScript check
```

There is no separate lint tooling configured for either side.

## Secrets and environment

- **NEVER read `backend/.env`.** Not to check keys, not to debug, not for any reason. Never print, copy, quote, or commit its contents.
- Infer required environment parameter keys from **`backend/.env.example`** — that file is the only sanctioned source of key names.
- If a change needs a new environment variable: add a placeholder key to `backend/.env.example` and read it in `backend/config/settings.py` (nothing else in the codebase touches env vars).
- Nothing loads `.env` automatically (no python-dotenv). The environment must be set in the shell/session that runs the backend.
- Never hardcode credentials, SMTP passwords, or recipient addresses in code or tests. `data/email_config.json` contains recipient emails (PII) — never commit it.

## Configuration

`backend/config/settings.py` is the single source of configuration: paths, refresh cooldown, HTTP headers/timeouts, search cities/terms, `ALLOWED_CATEGORY_IDS`, `EXCLUDED_TERMS`, image CDN rules, `REDIS_URL`. Make config changes there, never by scattering constants into other modules.

## Runtime state — do not commit, do not hand-edit casually

- `backend/data/ads.db` — SQLite database
- `backend/data/last_refresh.txt` — Refresh cooldown timestamp
- `backend/data/email_config.json` — Email Config (created on first save)
- `backend/logs/` — daily log files
- `backend/celerybeat-schedule` — Celery beat state

## Architecture decisions

Read `docs/adr/` before touching the related area. ADR 0001 governs the email notification system (JSON config file, per-recipient Filters, `include_sent`/`auto_send` toggles, synchronous Gmail SMTP, empty-result emails are sent deliberately). Significant new design decisions deserve a new numbered ADR.

## Testing is mandatory

- Agents MUST NOT bypass, skip, disable, or weaken testing when modifying or adding application capabilities.
- Existing tests are executable product requirements. It is NOT permitted to modify an existing test merely to make a new implementation pass.
- If an implementation causes an existing test to fail, stop and report the failure, the affected behavior, and the evidence needed to resolve it together with the user.
- Agents may add tests autonomously only when fixing a newly discovered bug or introducing a new capability. Added tests must assert the intended behavior and must not relax existing expectations. They can only ADD new tests not disable/skip/modify existing one.
- Every code change must run the narrowest relevant tests first and then the canonical suite before the work is considered complete.

## Test suite specifics

- Backend: pytest + pytest-mock in `backend/tests/`, run from `backend/` (no pytest config file; imports are `src.*`).
  - `test_extraction_logic.py` — parametrized real-world Italian listing strings against `extract_dimensions`, `extract_liters`, `extract_price`, `find_brand`. The `test_cases` are the spec for the parsers; if a parser refactor breaks them, the refactor is wrong (or the case was wrong all along — report it, do not edit it away).
  - `test_scraping_process.py` — mocks `httpx.Client`; covers happy path, Access-Denied page, and HTTP-error abort.
- Frontend: `CI=true npm test` (CRA jest). `src/App.test.tsx` is the stock CRA placeholder asserting a "learn react" link the app does not render — it fails when run. This is a known pre-existing failure: report it, do not delete or weaken it to go green.
- Tests must never hit Subito.it or any real network. Always mock HTTP (see existing `mocker.patch` patterns).
- Keep `backend/extraction/` pure (no HTTP, no DB) so it stays trivially testable; scraping concerns stay in `src/scraper.py`.

## Scraper etiquette

Subito.it is an external site we depend on. Preserve the existing politeness mechanisms (retry cooldowns in `fetch_with_resilience`, randomized headers via `build_headers`, delays between link checks). Do not add loops that hammer the site, and never test against it live.
