from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from config.settings import DATABASE_URL

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def init_db():
    Base.metadata.create_all(bind=engine)
    # ``create_all`` does not add columns to an existing SQLite table. Keep
    # the small, additive migration here so old Ads survive the new fields.
    with engine.begin() as connection:
        existing_columns = {
            row[1] for row in connection.exec_driver_sql("PRAGMA table_info(ads)")
        }
        column_types = {
            "foil_area_cm2": "FLOAT",
            "mast_length_cm": "FLOAT",
            "foil_wingspan_cm": "FLOAT",
            "wing_area_m2": "FLOAT",
            "board_length_cm": "FLOAT",
            "board_width_cm": "FLOAT",
            "equipment_type": "VARCHAR",
            "source": "VARCHAR",
        }
        for column, column_type in column_types.items():
            if column not in existing_columns:
                connection.exec_driver_sql(f"ALTER TABLE ads ADD COLUMN {column} {column_type}")
        # Pre-Vinted Ads have no source; they all came from Subito.
        connection.exec_driver_sql("UPDATE ads SET source = 'subito' WHERE source IS NULL")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
