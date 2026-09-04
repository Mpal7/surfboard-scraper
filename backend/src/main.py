import os
import time
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy.sql import func

import src.scraper as scraper
from config.settings import COOLDOWN_FILE, REFRESH_COOLDOWN_SECONDS
from src.database import get_db, init_db
from src.email_config import (
    add_recipient,
    delete_recipient,
    get_auto_send_after_refresh,
    get_recipients,
    load_config,
    set_auto_send_after_refresh,
    update_recipient,
)
from src.email_template import build_full_email
from src.models import Ad
from src.sender import send_email

app = FastAPI()

origins = [
    "http://localhost:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Helpers ──────────────────────────────────────────────────────────────────


def get_last_refresh_time():
    if not os.path.exists(COOLDOWN_FILE):
        return 0
    with open(COOLDOWN_FILE, "r") as f:
        try:
            return float(f.read().strip())
        except (ValueError, TypeError):
            return 0


def set_last_refresh_time(timestamp: float):
    with open(COOLDOWN_FILE, "w") as f:
        f.write(str(timestamp))


def apply_filters(query, filters: dict, include_sent: bool = False):
    query = query.filter(Ad.is_active == True, Ad.is_visible == True)

    if not include_sent:
        query = query.filter(Ad.is_mail_sent == False)

    brand = filters.get("brand")
    if brand:
        brands = [b.strip() for b in brand if b.strip()] if isinstance(brand, list) else [b.strip() for b in brand.split(",") if b.strip()]
        if brands:
            query = query.filter(Ad.brand.in_(brands))

    min_price = filters.get("min_price")
    max_price = filters.get("max_price")
    if min_price is not None:
        query = query.filter(Ad.price >= min_price)
    if max_price is not None:
        query = query.filter(Ad.price <= max_price)

    min_length = filters.get("min_length_inches")
    max_length = filters.get("max_length_inches")
    if min_length is not None:
        query = query.filter(Ad.length_total_inches >= min_length)
    if max_length is not None:
        query = query.filter(Ad.length_total_inches <= max_length)

    min_width = filters.get("min_width")
    max_width = filters.get("max_width")
    if min_width is not None:
        query = query.filter(Ad.width_in >= min_width)
    if max_width is not None:
        query = query.filter(Ad.width_in <= max_width)

    min_thickness = filters.get("min_thickness")
    max_thickness = filters.get("max_thickness")
    if min_thickness is not None:
        query = query.filter(Ad.thickness_in >= min_thickness)
    if max_thickness is not None:
        query = query.filter(Ad.thickness_in <= max_thickness)

    min_liters = filters.get("min_liters")
    max_liters = filters.get("max_liters")
    if min_liters is not None:
        query = query.filter(Ad.liters >= min_liters)
    if max_liters is not None:
        query = query.filter(Ad.liters <= max_liters)

    return query


# ── Pydantic models ─────────────────────────────────────────────────────────


class RecipientCreate(BaseModel):
    email: str
    filters: Optional[dict] = {}
    include_sent: Optional[bool] = False
    auto_send: Optional[bool] = True


class RecipientUpdate(BaseModel):
    filters: Optional[dict] = None
    include_sent: Optional[bool] = None
    auto_send: Optional[bool] = None


class AutoRefreshToggle(BaseModel):
    enabled: bool


# ── Startup ──────────────────────────────────────────────────────────────────


@app.on_event("startup")
def startup():
    init_db()


# ── Ads endpoints ────────────────────────────────────────────────────────────


@app.get("/ads")
def list_ads(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1),
    db: Session = Depends(get_db),
):
    query = db.query(Ad).filter(Ad.is_active == True, Ad.is_visible == True)
    total = query.count()
    ads = query.offset((page - 1) * page_size).limit(page_size).all()

    return {
        "total_items": total,
        "page": page,
        "page_size": page_size,
        "items": [ad.to_dict() for ad in ads],
    }


@app.get("/ads/filter")
def filter_ads(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort_by: str = Query(None, description="Sort by 'price_asc', 'price_desc', or 'date_desc'"),
    brand: str = None,
    liters: str = None,
    min_price: float = Query(None, ge=0),
    max_price: float = Query(None, ge=0),
    min_length_inches: float = Query(None, ge=48, le=144),
    max_length_inches: float = Query(None, ge=48, le=144),
    min_width: float = Query(None, ge=17, le=24),
    max_width: float = Query(None, ge=17, le=24),
    min_thickness: float = Query(None, ge=2, le=4),
    max_thickness: float = Query(None, ge=2, le=4),
):
    filters = {
        "brand": brand,
        "min_price": min_price,
        "max_price": max_price,
        "min_length_inches": min_length_inches,
        "max_length_inches": max_length_inches,
        "min_width": min_width,
        "max_width": max_width,
        "min_thickness": min_thickness,
        "max_thickness": max_thickness,
    }
    query = apply_filters(db.query(Ad), filters, include_sent=True)

    if liters:
        try:
            volume_list = [int(vol.strip()) for vol in liters.split(",") if vol.strip()]
            if volume_list:
                query = query.filter(func.round(Ad.liters).in_(volume_list))
        except (ValueError, TypeError):
            pass

    if sort_by == "price_asc":
        query = query.order_by(Ad.price.asc())
    elif sort_by == "price_desc":
        query = query.order_by(Ad.price.desc())
    elif sort_by == "date_asc":
        query = query.order_by(Ad.timestamp.asc())
    else:
        query = query.order_by(Ad.timestamp.desc())

    total = query.count()
    ads = query.offset((page - 1) * page_size).limit(page_size).all()

    return {
        "total_items": total,
        "page": page,
        "page_size": page_size,
        "items": [ad.to_dict() for ad in ads],
    }


# ── Email config endpoints ──────────────────────────────────────────────────


@app.get("/email-config")
def get_email_config():
    return load_config()


@app.post("/email-config/recipient", status_code=201)
def add_email_recipient(recipient: RecipientCreate):
    try:
        r = {
            "email": recipient.email,
            "filters": recipient.filters,
            "include_sent": recipient.include_sent,
            "auto_send": recipient.auto_send,
        }
        add_recipient(r)
        return r
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@app.put("/email-config/recipient/{email}")
def update_email_recipient(email: str, updates: RecipientUpdate):
    try:
        update_data = {k: v for k, v in updates.model_dump().items() if v is not None}
        return update_recipient(email, update_data)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.delete("/email-config/recipient/{email}")
def delete_email_recipient(email: str):
    try:
        delete_recipient(email)
        return {"message": f"Recipient {email} deleted"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.patch("/email-config/auto-refresh")
def toggle_auto_refresh(body: AutoRefreshToggle):
    set_auto_send_after_refresh(body.enabled)
    return {"auto_send_after_refresh": body.enabled}


# ── Send email endpoint ─────────────────────────────────────────────────────


def _send_to_recipient(recipient: dict, db: Session) -> dict:
    filters = recipient.get("filters", {})
    include_sent = recipient.get("include_sent", False)
    email_addr = recipient["email"]

    query = apply_filters(db.query(Ad), filters, include_sent=include_sent)
    ads = query.order_by(Ad.timestamp.desc()).all()

    subject, body = build_full_email(ads)
    success = send_email(subject, body, email_addr)

    if success:
        for ad in ads:
            ad.is_mail_sent = True
        db.commit()
        return {"email": email_addr, "ads_count": len(ads), "status": "sent"}
    else:
        return {"email": email_addr, "ads_count": 0, "status": "failed", "error": "SMTP send failed"}


@app.post("/send_email", status_code=200)
def send_email_endpoint(
    emails: Optional[str] = Query(None, description="Comma-separated recipient emails. Omit to send to all."),
    db: Session = Depends(get_db),
):
    all_recipients = get_recipients()
    if not all_recipients:
        raise HTTPException(status_code=400, detail="No recipients configured")

    if emails:
        target_emails = {e.strip().lower() for e in emails.split(",") if e.strip()}
        recipients = [r for r in all_recipients if r["email"].lower() in target_emails]
        not_found = target_emails - {r["email"].lower() for r in recipients}
        if not_found:
            raise HTTPException(status_code=404, detail=f"Recipients not found: {', '.join(not_found)}")
    else:
        recipients = all_recipients

    sent = []
    failed = []
    for recipient in recipients:
        result = _send_to_recipient(recipient, db)
        if result["status"] == "sent":
            sent.append({"email": result["email"], "ads_count": result["ads_count"]})
        else:
            failed.append({"email": result["email"], "error": result.get("error", "Unknown error")})

    return {"sent": sent, "failed": failed}


# ── Refresh endpoint ─────────────────────────────────────────────────────────


@app.post("/refresh", status_code=200)
def refresh_ads(db: Session = Depends(get_db)):
    last_refresh_time = get_last_refresh_time()
    now = time.time()

    if now - last_refresh_time < REFRESH_COOLDOWN_SECONDS:
        raise HTTPException(
            status_code=429,
            detail=f"Refresh allowed only every {REFRESH_COOLDOWN_SECONDS // 60} minutes.",
        )

    set_last_refresh_time(now)
    new_ads = scraper.scrape_and_store(db)

    result = {"message": "Refresh completed.", "new_ads_added": len(new_ads)}

    if get_auto_send_after_refresh():
        recipients = [r for r in get_recipients() if r.get("auto_send", True)]
        if recipients:
            sent = []
            failed = []
            for recipient in recipients:
                email_result = _send_to_recipient(recipient, db)
                if email_result["status"] == "sent":
                    sent.append({"email": email_result["email"], "ads_count": email_result["ads_count"]})
                else:
                    failed.append({"email": email_result["email"], "error": email_result.get("error", "Unknown error")})
            result["email_sent"] = sent
            result["email_failed"] = failed

    return result
