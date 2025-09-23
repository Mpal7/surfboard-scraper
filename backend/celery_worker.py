import random
import logging
from celery import Celery
from celery.schedules import crontab
from database import SessionLocal
import scraper
import check_ads

logger = logging.getLogger(__name__)

# --- Celery App Initialization ---
celery_app = Celery(
    "tasks",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/0"
)

# --- Define the Core Logic Tasks  ---
@celery_app.task(name="scrape_new_ads")
def scrape_new_ads_task():
    """
    Celery task to scrape new ads.
    """
    db = SessionLocal()
    try:
        logger.info("Executing scrape_new_ads_task...")
        scraper.scrape_and_store(db)
        logger.info("Finished scrape_new_ads_task.")
    finally:
        db.close()

@celery_app.task(name="check_existing_ads")
def check_existing_ads_task():
    """
    Celery task to check the status of existing ads.
    """
    db = SessionLocal()
    try:
        logger.info("Executing check_existing_ads_task...")
        check_ads.check_ad_status(db)
        logger.info("Finished check_existing_ads_task.")
    finally:
        db.close()

# --- The Randomized Dispatcher Task ---
@celery_app.task(name="schedule_randomized_scraping")
def schedule_randomized_scraping_task():
    """
    This task calculates a random delay and schedules the actual
    scraping and checking tasks to run sometime between 12:30 AM and 04:00 AM.
    """
    # 3.5 hours * 60 minutes/hour * 60 seconds/minute = 12,600 seconds.
    max_delay_seconds = 12600
    
    random_delay = random.randint(0, max_delay_seconds)
    
    # We want the check to run shortly after the scrape is finished.
    # Let's add a fixed 5-minute (300 seconds) gap.
    check_task_delay = random_delay + 300 
    
    logger.info(
        f"Dispatcher task running. Scheduling scrape task to run in {random_delay} seconds "
        f"and check task in {check_task_delay} seconds."
    )
    
    # Schedule the actual tasks using 'apply_async' with a 'countdown'.
    scrape_new_ads_task.apply_async(countdown=random_delay)
    check_existing_ads_task.apply_async(countdown=check_task_delay)


# --- Configure the Schedule to use the Dispatcher ---
@celery_app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    """
    Configures Celery Beat to run the dispatcher task every day
    at the beginning of our time window.
    """
    # Run the dispatcher task every day at 12:30 AM.
    sender.add_periodic_task(
        crontab(hour=0, minute=30),
        schedule_randomized_scraping_task.s(),
        name='dispatch scraping and checking tasks daily at 12:30 AM',
    )

# Optional: Set a timezone for your schedule
celery_app.conf.timezone = 'Europe/Rome'