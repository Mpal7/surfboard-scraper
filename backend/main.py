from fastapi import FastAPI, Depends, Query, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from database import get_db, init_db
from models import Ad
import scraper 
import time

app = FastAPI()

last_refresh_time = 0
REFRESH_COOLDOWN = 10 * 60  # 10 minuti

@app.on_event("startup")
def startup():
    init_db()

@app.get("/ads")
def list_ads(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1), db: Session = Depends(get_db)):
    ads = db.query(Ad)..filter(Ad.is_active == True).offset((page - 1) * page_size).limit(page_size).all()
    return [ad.to_dict() for ad in ads]

@app.get("/ads/filter")
def filter_ads(
    db: Session = Depends(get_db),
    brand: str = None,
    min_price: float = Query(None, ge=0),
    max_price: float = Query(None, ge=0),
    min_length_inches: float = Query(None, ge=48, le=144, description="Lunghezza minima in pollici (es. 5'10\" = 70)"),
    max_length_inches: float = Query(None, ge=48, le=144, description="Lunghezza massima in pollici (es. 6'2\" = 74)"),
    min_width: float = Query(None, ge=17, le=24, description="Larghezza minima in pollici"),
    max_width: float = Query(None, ge=17, le=24, description="Larghezza massima in pollici"),
    min_thickness: float = Query(None, ge=2, le=4, description="Spessore minimo in pollici"),
    max_thickness: float = Query(None, ge=2, le=4, description="Spessore massimo in pollici"),
    min_liters: float = Query(None, ge=20, le=100, description="Volume minimo in litri"),
    max_liters: float = Query(None, ge=20, le=100, description="Volume massimo in litri")
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

    ads = query.all()
    return [ad.to_dict() for ad in ads]

@app.post("/refresh")
def refresh_ads(db: Session = Depends(get_db)):
    global last_refresh_time
    now = time.time()
    if now - last_refresh_time < REFRESH_COOLDOWN:
        raise HTTPException(status_code=429, detail=f"Refresh allowed only every {REFRESH_COOLDOWN//60} minutes.")
    
    last_refresh_time = now
    new_ads = scraper.scrape_and_store(db) 
    return {"added": len(new_ads)}