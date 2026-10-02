import argparse

from src.database import SessionLocal
from src.vinted_cleanup import cleanup_vinted_ads, logger


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Hide suspicious Vinted rows already stored in the ads database."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report matching rows without modifying the database.",
    )
    args = parser.parse_args()

    logger.info("--- Starting Vinted Cleanup Script ---")
    db = SessionLocal()
    try:
        summary = cleanup_vinted_ads(db, dry_run=args.dry_run)
        logger.info("Cleanup summary: %s", summary)
    finally:
        db.close()
    logger.info("--- Vinted Cleanup Script Finished ---")
