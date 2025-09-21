from fastapi import FastAPI, Depends, Query, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from database import get_db, init_db
from models import Ad
import scraper
import time
import os

app = FastAPI()

COOLDOWN_FILE = "last_refresh.txt"
REFRESH_COOLDOWN = 10 * 60  # 10 minutes

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

@app.on_event("startup")
def startup():
    init_db()

@app.get("/ads")
def list_ads(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1),
    db: Session = Depends(get_db)
):
    query = db.query(Ad).filter(Ad.is_active == True)
    total = query.count()
    ads = query.offset((page - 1) * page_size).limit(page_size).all()
    
    return {
        "total_items": total,
        "page": page,
        "page_size": page_size,
        "items": [ad.to_dict() for ad in ads]
    }

@app.get("/ads/filter")
def filter_ads(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort_by: str = Query(None, description="Sort by 'price_asc', 'price_desc', or 'date_desc'"),
    brand: str = None,
    min_price: float = Query(None, ge=0),
    max_price: float = Query(None, ge=0),
    min_length_inches: float = Query(None, ge=48, le=144, description="Minimum length in inches (e.g., 5'10\" = 70)"),
    max_length_inches: float = Query(None, ge=48, le=144, description="Maximum length in inches (e.g., 6'2\" = 74)"),
    min_width: float = Query(None, ge=17, le=24, description="Minimum width in inches"),
    max_width: float = Query(None, ge=17, le=24, description="Maximum width in inches"),
    min_thickness: float = Query(None, ge=2, le=4, description="Minimum thickness in inches"),
    max_thickness: float = Query(None, ge=2, le=4, description="Maximum thickness in inches"),
    min_liters: float = Query(None, ge=20, le=100, description="Minimum volume in liters"),
    max_liters: float = Query(None, ge=20, le=100, description="Maximum volume in liters")
):
    query = db.query(Ad).filter(Ad.is_active == True)
    
    if brand:
        query = query.filter(Ad.brand.ilike(f"%{brand}%"))
    if min_price is not None:
        query = query.filter(Ad.price >= min_price)
    if max_price is not None:
        query = query.filter(Ad.price <= max_price)
    
    if min_length_inches is not None:
        query = query.filter(Ad.length_total_inches >= min_length_inches)
    if max_length_inches is not None:
        query = query.filter(Ad.length_total_inches <= max_length_inches)

    if min_width is not None:
        query = query.filter(Ad.width_in >= min_width)
    if max_width is not None:
        query = query.filter(Ad.width_in <= max_width)

    if min_thickness is not None:
        query = query.filter(Ad.thickness_in >= min_thickness)
    if max_thickness is not None:
        query = query.filter(Ad.thickness_in <= max_thickness)
        
    if min_liters is not None:
        query = query.filter(Ad.liters >= min_liters)
    if max_liters is not None:
        query = query.filter(Ad.liters <= max_liters)

    if sort_by == "price_asc":
        query = query.order_by(Ad.price.asc())
    elif sort_by == "price_desc":
        query = query.order_by(Ad.price.desc())
    elif sort_by == "date_desc":
        query = query.order_by(Ad.timestamp.desc())

    total = query.count()
    ads = query.offset((page - 1) * page_size).limit(page_size).all()
    
    return {
        "total_items": total,
        "page": page,
        "page_size": page_size,
        "items": [ad.to_dict() for ad in ads]
    }

@app.post("/refresh", status_code=200)
def refresh_ads(db: Session = Depends(get_db)):
    last_refresh_time = get_last_refresh_time()
    now = time.time()

    if now - last_refresh_time < REFRESH_COOLDOWN:
        raise HTTPException(status_code=429, detail=f"Refresh allowed only every {REFRESH_COOLDOWN//60} minutes.")
    
    set_last_refresh_time(now)
    new_ads = scraper.scrape_and_store(db) 
    return {"message": "Refresh completed.", "new_ads_added": len(new_ads)}