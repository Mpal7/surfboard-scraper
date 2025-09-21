import httpx
import time
import random
import logging
import os
from datetime import datetime
from sqlalchemy.orm import Session
from database import SessionLocal, init_db
from models import Ad
from sqlalchemy import select

# --- 1. Logging Configuration ---
LOG_DIR = "maintenance_logs"
os.makedirs(LOG_DIR, exist_ok=True)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

if not logger.handlers:
    log_filename = os.path.join(LOG_DIR, f"check_{datetime.now().strftime('%Y-%m-%d')}.log")
    file_handler = logging.FileHandler(log_filename, mode='a', encoding='utf-8')
    console_handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

# Use the same headers as the scraper to appear consistent
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9,it;q=0.8',
}

def check_ad_status(db: Session):
    """
    Iterates through active ads and checks if their links are still valid.
    Updates the is_active flag to False for dead links.
    """
    ads_to_check = db.query(Ad).filter(Ad.is_active == True).all()
    if not ads_to_check:
        logger.info("No active ads to check. Exiting.")
        return

    logger.info(f"Starting check for {len(ads_to_check)} active ads.")
    deactivated_count = 0

    with httpx.Client(headers=HEADERS, follow_redirects=True, timeout=10) as client:
        for ad in ads_to_check:
            try:
                # Use a HEAD request for efficiency - we only need the status code
                response = client.head(ad.link)

                # 404 Not Found or 410 Gone means the ad is deleted
                if response.status_code in [404, 410]:
                    logger.warning(f"Ad ID {ad.id} is GONE ({response.status_code}). Deactivating: {ad.link}")
                    ad.is_active = False
                    deactivated_count += 1
                # Check for redirects to the homepage (another sign of a deleted ad)
                elif response.is_redirect and response.headers.get('location') == 'https://www.subito.it/':
                     logger.warning(f"Ad ID {ad.id} REDIRECTS to homepage. Deactivating: {ad.link}")
                     ad.is_active = False
                     deactivated_count += 1
                else:
                    logger.info(f"Ad ID {ad.id} is still ACTIVE ({response.status_code}).")

            except httpx.RequestError as e:
                logger.error(f"Network error checking Ad ID {ad.id}: {e}")
            except Exception as e:
                logger.error(f"An unexpected error occurred for Ad ID {ad.id}: {e}")
            
            time.sleep(random.uniform(1, 3))

    if deactivated_count > 0:
        db.commit()
        logger.info(f"Committed changes to the database. Deactivated {deactivated_count} ads.")
    else:
        logger.info("No ads were deactivated in this run.")


if __name__ == "__main__":
    logger.info("--- Starting Ad Status Check Script ---")
    # This script needs its own database session since it's not part of the FastAPI app
    db = SessionLocal()
    try:
        check_ad_status(db)
    finally:
        db.close()
    logger.info("--- Ad Status Check Script Finished ---")