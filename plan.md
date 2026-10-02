# Deployment Plan — Surfboard Scraper on Vercel (free / Hobby)

Status: **Spike in progress — continuing from a personal Linux machine**
Branch: `feature/vercel-deployment`
Last updated: 2026-10-02

This file records the decisions, verified platform limits, findings, and next
steps from the deployment planning session. It is the single source of truth for
resuming this work in a future session.

---

## 1. Goal and hard requirements

- Deploy the whole app (frontend + backend processes) **inside Vercel**, on the
  **free Hobby plan**.
- A **scheduled Refresh** runs nightly, starting at a **random time between
  00:00 and 05:00** (Europe/Rome).
- **Only the admin** can **disable/re-enable the scheduler** from an admin panel.
- Follow best practices for **data security** on the public internet.

Non-negotiable existing constraints (from `AGENTS.md` / `CONTEXT.md` / ADRs):

- Preserve Subito politeness mechanisms (retry cooldowns, randomised headers,
  delays, single-consumer scraping). Do not weaken them.
- Existing tests are executable requirements — do not modify/skip/relax them.
- Never read/print/commit `backend/.env`; infer keys from `backend/.env.example`.
- Domain terms from `CONTEXT.md` (Ad, Active Ad, Visible Ad, Recipient, Filter,
  Refresh, Mail Sent, Email Config) are canonical.
- Keep `backend/extraction/` pure (no HTTP/DB).

Hobby note: free tier is for **non-commercial personal use**. This project is
personal, so it qualifies.

---

## 2. Verified Vercel + Neon facts (docs as of Aug–Sep 2026)

### Vercel Functions (Hobby)

- Max duration: **300 s (5 min)**. Pro: 800 s (1800 s beta).
- Memory: 2 GB max per instance; Hobby includes **360 GB-hr provisioned memory**,
  **4 h active CPU**, **1,000,000 invocations** per month.
- Python runtime supported (3.12 default, 3.13/3.14 available); Python bundle
  limit 500 MB.
- Active CPU is not billed while waiting on I/O; provisioned memory **is** billed
  for the instance lifetime.
- Source: https://vercel.com/docs/functions/limitations ,
  https://vercel.com/docs/functions/usage-and-pricing

### Vercel Cron (Hobby)

- Up to **100 cron jobs per project**; each runs **at most once per day**.
- Scheduling precision is **per-hour (±59 min)**: a job at 01:00 fires anywhere
  between 01:00 and 01:59. Multiple entries inside the same hour therefore do
  **not** reliably produce multiple invocations.
- Pro is required for per-minute precision.
- Source: https://vercel.com/docs/cron-jobs/usage-and-pricing

### Vercel Queues (Beta, all plans)

- Hobby includes **1,000,000 operations/month**.
- Supports delay-before-visible up to 7 days, concurrency control, at-least-once
  delivery.
- Vercel ships a **Celery adapter**: broker `vercel://`, result backend
  `vercel-runtime-cache://`; no Redis/RabbitMQ required. Workers compile to
  private queue-triggered functions. Celery Beat still cannot run — use Cron.
- Source: https://vercel.com/docs/frameworks/backend/celery ,
  https://vercel.com/docs/queues/pricing

### Vercel Workflows (Beta, all plans)

- Hobby includes **50,000 events + 1 GB written/month**; unlimited run duration
  and `sleep`; Python SDK is beta.
- Considered but not chosen (execution handled by Queues instead).
- Source: https://vercel.com/docs/workflows/pricing

### Vercel Services (Beta, all plans)

- Deploy React frontend + FastAPI backend in **one project**, one domain,
  shared routing via `vercel.json` `services` + `rewrites`. Enables **same-origin**
  (no CORS).
- Source: https://vercel.com/docs/services

### Storage

- Vercel has **no first-party relational DB**; Blob/Global Config are unsuitable
  for the relational Ad store.
- Marketplace (Neon/Upstash/Supabase) provides free tiers.

### Neon (chosen DB)

- Security: TLS 1.2+ in transit, AES-256 at rest, KMS; SOC 2 Type II,
  ISO 27001/27701, GDPR (DPA available), CCPA/CPRA; per-customer isolation;
  daily encrypted backups.
- Free plan: **1 GB Postgres storage/project**, 20 GB/account, **100 CU-hours/project**,
  scale-to-zero after 5 min, 5 GB egress; permanent (not a trial).
- **IP Allow is Scale-plan only** and, more importantly, useless here because
  Vercel function egress IPs are dynamic. Security model = strong credentials +
  TLS + least-privilege role + secrets in Vercel's encrypted env.
- Prefer an **EU region (Frankfurt / AWS eu-central-1)** to keep recipient PII in
  the EU and reduce latency to Subito.
- Source: https://neon.com/security , https://neon.com/pricing

---

## 3. Locked decisions

| # | Decision | Choice |
|---|---|---|
| D1 | Database | **Neon Postgres**, EU region, via Vercel Marketplace free tier |
| D2 | Random 00:00–05:00 trigger | **Multiple daily Cron jobs (hourly 00:00–05:00) + DB `planned_start`** |
| D3 | Execution engine | **Vercel Queues** via Celery `vercel://` adapter (beta), concurrency = 1 |
| D4 | Email | **Gmail SMTP 587 first**, Resend HTTP API as fallback |
| D5 | Local dev | **Keep SQLite + Celery/Redis locally**, switch by env var |
| D6 | Admin panel | **Full**: scheduler toggle + status, Recipients CRUD, manual Refresh/Send, run history |
| D7 | Admin session | **Keep `sessionStorage` bearer token** (ADR 0002), add login rate limiting |
| D8 | Existing data | **Migrate** `ads.db` + `email_config.json` into Neon |
| D9 | Hosting topology | **One Vercel project via Services** (same-origin, no CORS) |

### Proposed defaults (confirm in spike)

- Vercel function region: **`fra1` (Frankfurt)**; Neon AWS **`eu-central-1`**.
- Default function memory: **1 GB** (to stretch the 360 GB-hr budget).
- `maxDuration`: **300** (Hobby max).

### Why D2 + D3 split (important)

Cron is used only to **decide when** to start. It cannot **execute** the scrape:

- The nightly scrape is ~26–35 min of wall time (52 configs, ~100–150 page
  fetches, 10–20 s inter-term sleeps, detail fetches), and Subito 403 cooldowns
  can push it far higher.
- Hobby functions cap at 300 s, and Cron gives ~1 reliable invocation/hour →
  only ~25–30 min of compute/night, spilling into daytime.

Therefore execution continuation uses **Vercel Queues**: each invocation processes
search configs until ~240 s, persists a cursor, and re-enqueues itself. This
keeps the run at night and preserves single-consumer politeness. (Workflows was
the alternative; rejected in favour of Queues because the codebase already uses
Celery and the adapter is a smaller change.)

---

## 4. Target architecture

```
Vercel project "surfboard-scraper" (Hobby, region fra1)
├─ Service: frontend  (CRA static)          → /
├─ Service: backend   (FastAPI / Python)     → /api/*
├─ Cron (top-level): daily jobs 00:00–05:00 Europe/Rome
│      → /api/internal/scheduler/tick   (guarded by CRON_SECRET)
└─ Queue subscriber (private function): Celery worker on vercel://

Neon Postgres (EU / Frankfurt): ads · recipients · settings · runs
Vercel Queues (free 1M ops): execution continuation
Gmail SMTP 587 (fallback Resend): email
Local dev: SQLite + Celery/Redis, selected by env
```

### Nightly flow

1. Cron tick → if `scheduler_enabled` **and** now ≥ today's stored random
   `planned_start` (window 00:00–05:00 Europe/Rome) **and** no run active →
   enqueue `run_nightly(cursor=0)` (idempotent).
2. `run_nightly(cursor)` processes search configs until ~240 s, saves cursor,
   re-enqueues itself; on completion enqueues `check_ads(cursor)`.
3. `check_ads(cursor)` processes active Ads until ~240 s, re-enqueues itself;
   on completion enqueues `send_emails`.
4. `send_emails` reuses existing per-Recipient logic (ADR 0001 semantics,
   including empty-result emails).
5. Every step re-checks `scheduler_enabled`; disabling mid-run stops
   re-enqueueing and marks the Run `cancelled`.
6. A Run lock/status prevents overlapping nights.

### Admin panel (full)

- Scheduler: enable/disable toggle, computed `planned_start`, last/next run, run
  history (status, duration, new-Ads count, errors), cancel active run.
- Recipients: CRUD with the Filter form.
- Actions: manual Refresh (enqueues, returns `202`), manual Send (all/selected).
- New API: `GET/PUT /scheduler`, `GET /runs`, `GET /runs/{id}`.
  Internal: `/internal/scheduler/tick` behind `CRON_SECRET`.

---

## 5. Component mapping (current → target)

| Current | Target |
|---|---|
| SQLite `backend/data/ads.db` | Neon Postgres + Alembic; drop SQLite `PRAGMA` migration in `database.py` |
| `data/email_config.json` | `recipients` table (DB-backed) |
| `data/auth.json` | Env vars (`ADMIN_USERNAME`, `ADMIN_PASSWORD_HASH`, `AUTH_SECRET`) |
| `data/last_refresh.txt` | `settings` row |
| File + console logging (`utils/logger.py`) | stdout only under Vercel; file handler local |
| Celery Beat (`celery_worker.py`) | Vercel Cron → dispatch endpoint |
| Celery worker + Redis | Vercel Queues (`vercel://` broker; `task_acks_late=True`) |
| Synchronous `POST /refresh` | Enqueue run, return `202` |
| CORS `localhost:3000` | same-origin Services (remove CORS) |
| `verify=False` in `scraper.py` | `verify=True` in production |

---

## 6. Data model (added tables)

- `settings(key text pk, value jsonb)` — `scheduler_enabled`,
  `auto_send_after_refresh`, `planned_start`, `last_refresh`, etc.
- `recipients(id, email unique, filters jsonb, include_sent bool, auto_send bool)`
- `runs(id, status, started_at, finished_at, planned_start, cursor, phase,
  new_ads_count, error)` — status values: `pending|running|completed|failed|cancelled|skipped`
- `ads` — unchanged columns (unique `link`).

---

## 7. Security checklist

- Same-origin frontend/API via Services → no CORS.
- `CRON_SECRET` on `/internal/*`; Vercel Cron sends `Authorization: Bearer <secret>`.
- Rate-limit `POST /auth/login` (currently unbounded).
- **Deployment Protection** on preview deployments (PII endpoints must not be
  exposed on preview URLs).
- Secrets only in Vercel encrypted env: `GMAIL_ADDRESS`, `GMAIL_APP_PASSWORD`,
  `DATABASE_URL`, `CRON_SECRET`, `ADMIN_USERNAME`, `ADMIN_PASSWORD_HASH`,
  `AUTH_SECRET` (and `RESEND_API_KEY` if used).
- Neon: TLS `sslmode=require`, least-privilege role, serverless pooling
  (`pool_pre_ping`, small/Null pool).
- Do not log recipient emails or secrets; Hobby runtime logs are retained 1 h.
- Keep bearer token in `sessionStorage` (ADR 0002); rotate Gmail app password
  before go-live.
- Add new env keys to `backend/.env.example` as placeholders only.

---

## 8. File-by-file change set (implementation, not yet started)

| Area | Change |
|---|---|
| `config/settings.py` | `DATABASE_URL` from env (SQLite default); broker selection (Redis vs `vercel://`); region/memory; `CRON_SECRET` |
| `src/database.py` | Branch engine args on dialect; Postgres pooling; remove `PRAGMA` migration |
| **new** `alembic/` + `alembic.ini` | Schema + migrations |
| `src/models.py` | Add `Recipient`, `Setting`, `Run`; keep `Ad` |
| `src/email_config.py` | DB-backed; preserve ADR 0001 semantics |
| `src/scraper.py` | Resumable per-config orchestrator (cursor + time budget); keep politeness; `verify=True` prod |
| `scripts/check_ads.py` | Same cursor/budget treatment |
| `src/celery_worker.py` | `vercel://` broker, `vercel-runtime-cache://` backend, `task_acks_late=True`; drop Beat; add run/check/email tasks |
| `src/main.py` | `/refresh` → enqueue + `202`; `/scheduler`, `/runs`, `/runs/{id}`; `/internal/scheduler/tick`; remove CORS |
| `utils/logger.py` | stdout-only under Vercel |
| `src/sender.py` | Gmail unchanged; add Resend fallback behind env switch |
| `frontend/src/services/api.ts` | API base same-origin (`''`) |
| **new** `frontend/src/pages/Admin*.tsx` | Scheduler, Recipients, Actions, Run history |
| **new** `vercel.json` | `services`, `crons`, `rewrites`, per-function `maxDuration`/`memory` |
| **new** `pyproject.toml` | `[tool.vercel] entrypoint = "src.main:app"`, `[[tool.vercel.subscribers]]`, deps |
| `backend/.env.example` | Add `DATABASE_URL`, `CRON_SECRET` placeholders |
| **new** `scripts/migrate_sqlite_to_postgres.py` | One-time data migration |
| **new** `docs/adr/0003-*.md` | Deployment/serverless architecture decision |

---

## 9. Local dev parity (D5)

Default `DATABASE_URL` stays SQLite and default broker stays Redis, so `pytest`
and the existing Celery Beat flow keep working locally. Production selects
Postgres/Queues purely via env. This preserves existing tests unchanged.

## 10. Testing plan (additions only)

- Scheduler tick: disabled → no-op; before `planned_start` → no-op; due →
  enqueue once; double tick → no duplicate run.
- Orchestrator cursor: stops at budget, resumes without reprocessing, marks Run
  complete.
- `CRON_SECRET` rejects unauthorized tick calls.
- Recipients/settings DB CRUD.
- Migration script correctness (fixture `ads.db`).
- Reminder: `frontend/src/App.test.tsx` is a **known pre-existing failure** —
  report, do not delete/weaken.

## 11. Free-tier budget (estimate)

| Resource | Estimate | Hobby allowance |
|---|---|---|
| Provisioned memory | ~60–120 GB-hr/mo (at 2 GB; ~half at 1 GB) | 360 GB-hr |
| Active CPU | ~1–3 h/mo | 4 h |
| Invocations | a few thousand/mo | 1,000,000 |
| Queue ops | tens of thousands/mo | 1,000,000 |
| Neon storage | well under 1 GB | 1 GB |

Tightest is **active CPU**; can balloon if Subito forces long 403 cooldowns.

---

## 12. Risks

1. **Subito blocking Vercel egress IPs** — the spike's `/subito` is the gate.
   Fallback: different egress (home/RPi or free off-Vercel worker).
2. **Gmail SMTP 587** unverified until deployed; Resend fallback.
3. **Beta surface**: Queues + Services + Celery adapter.
4. **Hobby**: non-commercial only, no SLA, 1 h log retention, ±59 min cron.
5. **Overlap/DST**: Run lock prevents overlap; Cron is UTC, Europe/Rome computed
   in-app.
6. **Services + `[[tool.vercel.subscribers]]`** is the least-documented combo —
   spike early.
7. **Local dev machine TLS trust** — the spike was moved to a personal Linux
   machine for policy/privacy reasons; affects the CLI only, not production.

---

## 13. Spike (in progress)

Throwaway project in `spike/` (delete after recording results):

| Path | Endpoint / purpose |
|---|---|
| `spike/index.py` | `/`, `/subito`, `/email`, `/db`, `/cron` |
| `spike/vercel.json` | functions `maxDuration: 60`; one daily cron `0 0 * * *` → `/cron` |
| `spike/requirements.txt` | fastapi, httpx[http2], sqlalchemy, psycopg2-binary |
| `spike/README.md` | endpoint + env-var notes |

Spike proves: (a) FastAPI runs on Hobby, (b) Vercel egress can fetch Subito,
(c) Gmail SMTP 587 works, (d) Neon connects, (e) Cron fires with `CRON_SECRET`.

### Spike status

- [x] Spike files created.
- [x] Vercel CLI verified working (62.1.0); initial machine reverted.
- [x] Spike moved to a personal Linux machine for policy/privacy reasons.
- [ ] `vercel login` on the Linux machine.
- [ ] `/` and `/subito` tested (make-or-break).
- [ ] `/email` tested (Gmail env set).
- [ ] `/db` tested (Neon `DATABASE_URL` set).
- [ ] `/cron` tested and scheduled cron verified.

### Why the spike moved to personal Linux

The initial workstation was company-managed with TLS inspection, which breaks
Node's certificate trust for CLI tools (the Vercel CLI). Rather than work around
a company security stack, the deployment work moved to a personal Linux machine
off the corporate network: this project needs a Vercel token, a Gmail app
password, and Neon credentials, which should not be handled on a company device.

Everything temporary set up on the initial machine while spiking was reverted,
including the local certificate-trust workaround, the exported cert bundle, temp
scripts, and the globally installed `vercel` npm package. No credentials were
ever committed to the repository from that machine.

Production is unaffected: this was a local CLI-only issue, and deployed Vercel
functions run outside the company network.

### Spike run commands (once authenticated, Linux)

```bash
# from spike/
vercel link --yes --project surfboard-vercel-spike
vercel deploy --prod --yes
# then curl the production URLs: /, /subito (then /email, /db, /cron)
vercel crons ls
```

Env vars for later spike steps are set **by the user** in Vercel (never pasted
into chat):

- `GMAIL_ADDRESS`, `GMAIL_APP_PASSWORD`, `TEST_EMAIL_TO`
- `DATABASE_URL` (Neon, `postgresql://...?...sslmode=require`)
- `CRON_SECRET`

---

## 14. Open items / next actions

1. ~~Decide machine~~ → personal Linux (done).
2. On Linux: clone/pull branch `feature/vercel-deployment` (includes `plan.md`
   and `spike/`).
3. Install Node 20+ and `npm i -g vercel`; `vercel login` (personal Hobby).
4. Link + deploy `spike/`.
5. Run `/subito` — **if blocked, stop and rethink egress before any refactor**.
6. Run `/email`, `/db`, `/cron`; record results.
7. Confirm region (`fra1` + Neon `eu-central-1`) and function memory (1 GB).
8. Only then: write the concrete implementation plan and start the data-layer
   work (`DATABASE_URL` switch, Alembic, models, migration).

## 15. Resuming on Linux (quickstart)

```bash
git clone <repo-url> surfboard-scraper
cd surfboard-scraper
git checkout feature/vercel-deployment

# Vercel CLI (Node 20+)
npm install -g vercel
vercel login            # personal Hobby scope

# Run the spike
cd spike
vercel link --yes --project surfboard-vercel-spike
vercel deploy --prod --yes
# then curl the deployment URL / and /subito
```

Set secrets only in Vercel (Project → Settings → Environment Variables,
Production), never in chat or git: `GMAIL_ADDRESS`, `GMAIL_APP_PASSWORD`,
`TEST_EMAIL_TO`, `DATABASE_URL`, `CRON_SECRET`.
