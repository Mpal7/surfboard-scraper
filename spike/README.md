# Vercel deployment spike (throwaway)

Proves the four deployment assumptions on the free Hobby plan. Not part of the
application; delete after recording results.

## Endpoints

| Path | Proves |
|---|---|
| `/` | Python/FastAPI function executes on Vercel; reports region |
| `/subito` | Vercel egress can fetch a real Subito search page |
| `/email` | Gmail SMTP port 587 works from a Vercel function |
| `/db` | A Neon Postgres connection string works from Vercel |
| `/cron` | Vercel Cron invokes the function (guarded by `CRON_SECRET`) |

## Environment variables to set in Vercel (Production)

- `GMAIL_ADDRESS`
- `GMAIL_APP_PASSWORD`
- `TEST_EMAIL_TO`
- `DATABASE_URL` (Neon, `postgresql://...?sslmode=require`)
- `CRON_SECRET`

Never commit any of these values.
