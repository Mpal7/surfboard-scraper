"""Throwaway Vercel Hobby spike.

Purpose: prove or disprove, from Vercel's servers, the four things the
deployment plan depends on:

  1. /            -> a FastAPI/Python function runs on Vercel at all
  2. /subito      -> Vercel's egress IPs are not hard-blocked by Subito.it
  3. /email       -> Gmail SMTP over port 587 works from a Vercel function
  4. /db          -> a Neon Postgres connection string works from Vercel
  5. /cron        -> Vercel Cron can invoke a function with CRON_SECRET

This module is NOT part of the application. Delete the whole spike/ folder
once the results are recorded.
"""

from __future__ import annotations

import os
import smtplib
from datetime import datetime, timezone
from email.mime.text import MIMEText

import httpx
from fastapi import FastAPI, Header, HTTPException

app = FastAPI(title="surfboard-vercel-spike")

SUBITO_URL = (
    "https://www.subito.it/annunci-lazio/vendita/usato/roma/"
    "?q=tavola+da+surf&o=1"
)

# A representative slice of the real scraper's browser headers.
SUBITO_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,image/apng,*/*;q=0.8"
    ),
    "Accept-Encoding": "gzip, deflate",
    "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.7,en;q=0.6",
    "Referer": "https://www.subito.it/",
    "Sec-Ch-Ua": '"Not/A.Brand";v="99", "Chromium";v="152", "Google Chrome";v="152"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
}


@app.get("/")
def root():
    return {
        "ok": True,
        "on_vercel": bool(os.getenv("VERCEL")),
        "vercel_env": os.getenv("VERCEL_ENV"),
        "region": os.getenv("VERCEL_REGION"),
        "now": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/subito")
def subito():
    """Fetch a real Subito search page and report how it responds."""
    result: dict = {"url": SUBITO_URL}
    try:
        with httpx.Client(
            follow_redirects=True,
            http2=True,
            timeout=httpx.Timeout(connect=10.0, read=30.0, write=10.0, pool=30.0),
            verify=True,
        ) as client:
            response = client.get(SUBITO_URL, headers=SUBITO_HEADERS)
        body = response.text or ""
        result.update(
            status=response.status_code,
            final_url=str(response.url),
            access_denied="Access Denied" in body,
            has_next_data="__NEXT_DATA__" in body,
            article_tags=body.count("<article"),
            length=len(body),
        )
    except Exception as exc:  # noqa: BLE001 - spike wants the raw failure
        result.update(error=type(exc).__name__, detail=str(exc)[:500])
    return result


@app.get("/email")
def email(to: str | None = None):
    """Send one test email through Gmail SMTP (port 587 + STARTTLS)."""
    sender = os.getenv("GMAIL_ADDRESS")
    password = os.getenv("GMAIL_APP_PASSWORD")
    recipient = to or os.getenv("TEST_EMAIL_TO")
    if not sender or not password or not recipient:
        raise HTTPException(
            status_code=400,
            detail="Set GMAIL_ADDRESS, GMAIL_APP_PASSWORD and TEST_EMAIL_TO.",
        )

    message = MIMEText("Gmail SMTP from a Vercel function works.", "plain")
    message["From"] = sender
    message["To"] = recipient
    message["Subject"] = "Surfboard scraper - Vercel SMTP spike"
    try:
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as server:
            server.starttls()
            server.login(sender, password)
            server.sendmail(sender, recipient, message.as_string())
        return {"sent": True, "to": recipient}
    except Exception as exc:  # noqa: BLE001
        return {"sent": False, "error": type(exc).__name__, "detail": str(exc)[:500]}


@app.get("/db")
def db():
    """Open a Neon Postgres connection with SQLAlchemy."""
    url = os.getenv("DATABASE_URL")
    if not url:
        raise HTTPException(status_code=400, detail="Set DATABASE_URL.")
    try:
        from sqlalchemy import create_engine, text

        engine = create_engine(url, pool_pre_ping=True)
        with engine.connect() as connection:
            version = connection.execute(text("select version()")).scalar()
        return {"connected": True, "version": str(version)[:90]}
    except Exception as exc:  # noqa: BLE001
        return {"connected": False, "error": type(exc).__name__, "detail": str(exc)[:500]}


@app.get("/cron")
def cron(authorization: str | None = Header(default=None)):
    """Vercel Cron sends Authorization: Bearer <CRON_SECRET> when set."""
    secret = os.getenv("CRON_SECRET")
    if secret and authorization != f"Bearer {secret}":
        raise HTTPException(status_code=401, detail="bad cron secret")
    return {
        "cron_fired_at": datetime.now(timezone.utc).isoformat(),
        "has_secret": bool(secret),
    }
