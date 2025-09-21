from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean
from sqlalchemy.ext.hybrid import hybrid_property
from database import Base
from datetime import datetime
import math

class Ad(Base):
    __tablename__ = "ads"
    id = Column(Integer, primary_key=True, index=True)
    model = Column(String, index=True)
    brand = Column(String, nullable=True)
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

    is_active = Column(Boolean, default=True, nullable=False, index=True)

    @hybrid_property
    def length_total_inches(self):
        total = 0
        if self.length_ft: total += self.length_ft * 12
        if self.length_in: total += self.length_in
        return total if total > 0 else None

    def to_dict(self):
        return {
            "id": self.id,
            "model": self.model,
            "brand": self.brand,
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
        }