import httpx
import time
import random
import logging
import os
from datetime import datetime
from sqlalchemy.orm import Session
from bs4 import BeautifulSoup

# Import necessary components from your existing project files
from database import SessionLocal
from models import Ad
from scraper import find_brand, HEADERS

# --- 1. Logging Configuration ---
LOG_DIR = "maintenance_logs"
os.makedirs(LOG_DIR, exist_ok=True)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

if not logger.handlers:
    log_filename = os.path.join(LOG_DIR, f"update_brands_{datetime.now().strftime('%Y-%m-%d')}.log")
    file_handler = logging.FileHandler(log_filename, mode='a', encoding='utf-8')
    console_handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

def update_missing_brands(db: Session):
    """
    Finds active ads with no brand, re-scrapes them, and tries to update the brand.
    """
    # Query for active ads where the brand is currently NULL
    ads_to_check = db.query(Ad).filter(Ad.brand == None, Ad.is_active == True).all()

    if not ads_to_check:
        logger.info("No active ads with missing brands to update. Exiting.")
        return

    logger.info(f"Found {len(ads_to_check)} ads with missing brands. Starting update process...")
    updated_count = 0
    deactivated_count = 0

    with httpx.Client(headers=HEADERS, follow_redirects=True, timeout=10) as client:
        for ad in ads_to_check:
            logger.info(f"--- \n Checking Ad ID: {ad.id}, Link: {ad.link}")
            try:
                response = client.get(ad.link)

                # If ad is no longer available, mark it as inactive
                if response.status_code in [404, 410]:
                    logger.warning(f"  > Ad is GONE ({response.status_code}). Marking as inactive.")
                    ad.is_active = False
                    deactivated_count += 1
                    continue

                response.raise_for_status() # Raise an exception for other bad statuses

                detail_soup = BeautifulSoup(response.text, "html.parser")
                
                # Scrape the description text from the page
                desc_div = detail_soup.find("p", class_="AdDescription_description__154FP")
                description_text = desc_div.get_text(separator=" ", strip=True) if desc_div else ""
                
                # Combine the ad's title (model) and the scraped description
                full_text_to_search = f"{ad.model} {description_text}"
                
                # Run the brand extraction logic from your scraper
                found_brand = find_brand(full_text_to_search)

                if found_brand:
                    logger.info(f"  > SUCCESS: Found brand '{found_brand}'. Updating database.")
                    ad.brand = found_brand
                    updated_count += 1
                else:
                    logger.info("  > No brand found with the updated list.")

            except httpx.RequestError as e:
                logger.error(f"  > Network error checking Ad ID {ad.id}: {e}")
            except Exception as e:
                logger.error(f"  > An unexpected error occurred for Ad ID {ad.id}: {e}")
            
            # Be polite to the server with a delay
            time.sleep(random.uniform(1, 3))

    if updated_count > 0 or deactivated_count > 0:
        db.commit()
        logger.info("Committed changes to the database.")
    
    logger.info("--- Update Process Summary ---")
    logger.info(f"Ads checked: {len(ads_to_check)}")
    logger.info(f"Brands updated: {updated_count}")
    logger.info(f"Ads deactivated: {deactivated_count}")
    logger.info("-----------------------------")


if __name__ == "__main__":
    logger.info("--- Starting Missing Brands Update Script ---")
    db = SessionLocal()
    try:
        update_missing_brands(db)
    finally:
        db.close()
    logger.info("--- Missing Brands Update Script Finished ---")