from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean
from sqlalchemy.ext.hybrid import hybrid_property
from src.database import Base
from datetime import datetime
import math

class Ad(Base):
    __tablename__ = "ads"
    id = Column(Integer, primary_key=True, index=True)
    source = Column(String, nullable=False, default="subito", index=True)
    model = Column(String, index=True)
    brand = Column(String, nullable=True)
    board_type = Column(String, nullable=True, index=True, default="surf")
    price = Column(Float, nullable=True)
    location = Column(String)
    link = Column(String, unique=True)
    image_url = Column(String, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    length_ft = Column(Integer, nullable=True)
    length_in = Column(Float, nullable=True)
    width_in = Column(Float, nullable=True)
    thickness_in = Column(Float, nullable=True)
    liters = Column(Float, nullable=True)
    foil_area_cm2 = Column(Float, nullable=True)
    mast_length_cm = Column(Float, nullable=True)
    foil_wingspan_cm = Column(Float, nullable=True)
    wing_area_m2 = Column(Float, nullable=True)
    board_length_cm = Column(Float, nullable=True)
    board_width_cm = Column(Float, nullable=True)
    equipment_type = Column(String, nullable=True, index=True)

    is_mail_sent = Column(Boolean, default=False, nullable=False, index=True)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    is_visible = Column(Boolean, default=True, nullable=False, index=True)

    @hybrid_property
    def length_total_inches(self):
        total = 0
        if self.length_ft: total += self.length_ft * 12
        if self.length_in: total += self.length_in
        return total if total > 0 else None

    def to_dict(self):
        return {
            "id": self.id,
            "source": self.source,
            "model": self.model,
            "brand": self.brand,
            "board_type": self.board_type,
            "price": self.price,
            "location": self.location,
            "link": self.link,
            "image_url": self.image_url,
            "scraped_at": self.timestamp.isoformat() if self.timestamp else None,
            "length_ft": self.length_ft,
            "length_in": self.length_in,
            "width_in": self.width_in,
            "thickness_in": self.thickness_in,
            "liters": self.liters,
            "foil_area_cm2": self.foil_area_cm2,
            "mast_length_cm": self.mast_length_cm,
            "foil_wingspan_cm": self.foil_wingspan_cm,
            "wing_area_m2": self.wing_area_m2,
            "board_length_cm": self.board_length_cm,
            "board_width_cm": self.board_width_cm,
            "equipment_type": self.equipment_type,
            "is_mail_sent": self.is_mail_sent,
        }
