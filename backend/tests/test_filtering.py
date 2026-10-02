from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.database import Base
from src.main import apply_filters
from src.models import Ad


def test_apply_filters_supports_foil_and_kite_measurements():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        matching_ad = Ad(
            model="Foil set",
            board_type="foil",
            equipment_type="foil",
            link="https://example.com/matching",
            mast_length_cm=90,
            foil_area_cm2=1200,
            foil_wingspan_cm=85,
            wing_area_m2=6,
            board_length_cm=135,
            board_width_cm=42,
        )
        non_matching_ad = Ad(
            model="Short mast foil",
            board_type="foil",
            equipment_type="foil",
            link="https://example.com/non-matching",
            mast_length_cm=75,
            foil_area_cm2=900,
            foil_wingspan_cm=70,
            wing_area_m2=4,
            board_length_cm=125,
            board_width_cm=38,
        )
        db.add_all([matching_ad, non_matching_ad])
        db.commit()

        ads = apply_filters(
            db.query(Ad),
            {
                "min_foil_area_cm2": 1000,
                "min_mast_length_cm": 85,
                "min_foil_wingspan_cm": 80,
                "min_wing_area_m2": 5,
                "min_board_length_cm": 130,
                "min_board_width_cm": 40,
            },
            include_sent=True,
        ).all()

        assert [ad.link for ad in ads] == ["https://example.com/matching"]
