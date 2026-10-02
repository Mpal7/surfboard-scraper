# Surfboard Scraper

Scrapes surfboard **Ads** from [Subito.it](https://www.subito.it/), stores them in SQLite, and notifies **Recipients** by email when new boards matching their **Filters** appear. See [`CONTEXT.md`](CONTEXT.md) for the domain glossary and [`docs/adr/`](docs/adr/) for architecture decisions.

- `backend/` — Python / FastAPI: scraping, extraction, storage, email notifications, Celery/Redis scheduling.
- `frontend/` — React 19 + TypeScript + Tailwind: read-only marketplace UI.

---

## Backend

### Prerequisites

- Python 3.10+
- Redis running on `localhost:6379` (only needed for Celery scheduling, not for the API itself)

### Setup

From the `backend/` directory (imports are rooted there):

```
cd backend
python -m venv venv
venv\Scripts\pip install -r requirements.txt
```

Create the environment file from the template (only needed for email sending):

```
copy .env.example .env
```

Fill in `GMAIL_ADDRESS` and `GMAIL_APP_PASSWORD` in `.env`. **Never commit real credentials.** Nothing loads `.env` automatically — the variables must be present in the shell/session that runs the backend.

### Run the API

```
venv\Scripts\python -m uvicorn src.main:app --reload
```

Serves the API on `http://localhost:8000` (interactive docs at `/docs`).

### Run tests

```
venv\Scripts\python -m pytest
```

### Run the Celery scheduler (optional, for nightly automated scraping)

Needs Redis on `localhost:6379/0`:

```
venv\Scripts\python -m celery -A src.celery_worker worker -B --loglevel=info
```

Celery Beat dispatches a random-time scrape + ad-status check nightly between 12:30 AM and 4:00 AM.

### Maintenance scripts

```
venv\Scripts\python -m scripts.check_ads       # mark Ads inactive when their Subito link dies
venv\Scripts\python -m scripts.update_images   # backfill Ad image URLs
```

---

## Frontend

From the `frontend/` directory:

```
cd frontend
npm install
npm start
```

Serves the dev app on `http://localhost:3000`. It expects the backend at `http://localhost:8000` (configured in `src/services/api.ts`).

### Tests

```
CI=true npm test    # single run
npm test            # watch mode
```

### Build / typecheck

```
npm run build
```

`react-scripts build` also serves as the TypeScript check.

---

## API endpoints (backend)

| Method | Path | Purpose |
|---|---|---|
| GET | `/ads` | List Ads (paginated) |
| GET | `/ads/filter` | List/filter Ads by criteria |
| GET | `/email-config` | Read the Email Config |
| POST | `/email-config/recipient` | Add a Recipient (with Filters) |
| PUT | `/email-config/recipient/{email}` | Update a Recipient |
| DELETE | `/email-config/recipient/{email}` | Remove a Recipient |
| PATCH | `/email-config/auto-refresh` | Toggle auto-refresh |
| POST | `/send_email` | Send email notifications |
| POST | `/refresh` | Trigger a manual Refresh (has a cooldown) |

---

## Useful notes

- **Working directory matters**: always run backend commands from `backend/` (`from src...`, `from config...`, `from extraction...`).
- **Never read or commit `backend/.env`**; infer env keys from `backend/.env.example`. Env keys are only read in `backend/config/settings.py`.
- **Config lives in one place**: `backend/config/settings.py` (refresh cooldown, search cities/terms, HTTP headers, category/term exclusions, Redis URL). Change it there, not scattered in other modules.
- **Runtime state (do not commit):** `backend/data/ads.db`, `backend/data/last_refresh.txt`, `backend/data/email_config.json` (contains recipient emails / PII), `backend/logs/`, `backend/celerybeat-schedule`.
- **Email Config** is persisted in `data/email_config.json` and managed via the `/email-config` API. Recipient emails are PII — never commit them.
- **Refresh cooldown** prevents hammering Subito.it. Politeness mechanisms (retry cooldowns, randomized headers, delays) are intentional — don't weaken them.
- **Testing is mandatory.** Existing tests are executable product requirements. Run the narrowest test first, then the full suite. Tests never hit the real network (HTTP is mocked).
- `backend/main.py` is a **legacy duplicate** with no email endpoints — do not extend it; all API work goes in `backend/src/main.py`.
