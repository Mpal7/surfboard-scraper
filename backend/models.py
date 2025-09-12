from sqlalchemy import Column, Integer, String, Float, DateTime
from sqlalchemy.ext.hybrid import hybrid_property
from database import Base
from datetime import datetime

class Ad(Base):
    __tablename__ = "ads"
    id = Column(Integer, primary_key=True, index=True)
    model = Column(String, index=True)
    brand = Column(String, nullable=True)
    price = Column(Float, nullable=True)
    location = Column(String)
    link = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    # Dati numerici per filtri potenti
    length_ft = Column(Integer, nullable=True)
    length_in = Column(Float, nullable=True)
    width_in = Column(Float, nullable=True)
    thickness_in = Column(Float, nullable=True)
    liters = Column(Float, nullable=True)

    @hybrid_property
    def length_total_inches(self):
        total = 0
        if self.length_ft: total += self.length_ft * 12
        if self.length_in: total += self.length_in
        return total if total > 0 else None

    # Formattazione per l'output dell'API
    def to_dict(self):
        length_formatted = None
        if self.length_ft is not None and self.length_in is not None:
            length_formatted = f"{self.length_ft}'{int(round(self.length_in))}\""

        width_formatted = f'{self.width_in}"' if self.width_in is not None else None
        thickness_formatted = f'{self.thickness_in}"' if self.thickness_in is not None else None

        return {
            "id": self.id,
            "model": self.model,
            "brand": self.brand,
            "price": self.price,
            "location": self.location,
            "link": self.link,
            # --- RIGA CORRETTA ---
            # Aggiunto un controllo: formatta il timestamp solo se esiste.
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "length": length_formatted,
            "width": width_formatted,
            "thickness": thickness_formatted,
            "liters": self.liters
        }