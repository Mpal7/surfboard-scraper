# Asynchronous Refresh Jobs

`POST /refresh` no longer scrapes inline. It records a Job and returns immediately so a long scrape cannot block or time out the API request.

## Context

A full Refresh walks every search configuration across both marketplaces, so a synchronous request could take minutes. Holding the HTTP request open for that long risked gateway timeouts and gave the frontend no way to observe progress. The nightly Celery schedule already ran the same work in the background but left no durable record of it.

## Key decisions

- **`JobRun` is the durable record** of a background run. It stores `job_type` (`scrape` or `check_ads`), `trigger_source` (`manual` or `schedule`), `status`, `worker_type`, timing, and a trimmed JSON result.
- **`POST /refresh` returns `202`** with `job_id` and a `status_url`. Clients poll `GET /jobs/{id}` for status and result; `GET /jobs` lists recent runs.
- **Dispatch prefers Celery and falls back to a local thread.** `task_dispatcher` enqueues `scrape_new_ads` when a broker is reachable, otherwise runs the job on a daemon thread so local development works without Redis.
- **Post-refresh emails move into the job.** When auto-send is enabled, the notification emails are sent by the job runner on completion, so the asynchronous Refresh preserves the previous auto-send behaviour.
- **The cooldown is unchanged.** `refresh_service` still enforces `REFRESH_COOLDOWN_SECONDS` and returns `429` when a Refresh is requested too soon; the cooldown timestamp is written when the Job is queued.
