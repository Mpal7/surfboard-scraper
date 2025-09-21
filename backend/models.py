from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean
from sqlalchemy.ext.hybrid import hybrid_property
from database import Base
from datetime import datetime
import math

def decimal_to_fraction_str(number: float) -> str:
    """
    Converts a float into a mixed fraction string for common surfboard dimensions.
    Example: 21.25 -> "21 1/4", 2.5 -> "2 1/2"
    """
    if number is None:
        return ""

    # A mapping of common decimal values to their fractional representation
    # We use a small tolerance for floating point comparisons.
    fractions = {
        0.125: "1/8", 0.25: "1/4", 0.375: "3/8", 0.5: "1/2",
        0.625: "5/8", 0.75: "3/4", 0.875: "7/8"
    }
    tolerance = 0.01

    integer_part = int(number)
    decimal_part = number - integer_part

    fraction_str = ""
    # Find the closest fraction in our map
    for dec_val, frac_str in fractions.items():
        if abs(decimal_part - dec_val) < tolerance:
            fraction_str = frac_str
            break

    # If no common fraction was found, we just round the original number
    if not fraction_str and decimal_part > 0:
        return f"{round(number, 2)}"

    # Build the final string
    if integer_part > 0 and fraction_str:
        return f"{integer_part} {fraction_str}"
    elif integer_part > 0:
        return str(integer_part)
    elif fraction_str:
        return fraction_str
    
    # Fallback for zero or numbers without a clear fraction match
    return str(integer_part)


class Ad(Base):
    __tablename__ = "ads"
    id = Column(Integer, primary_key=True, index=True)
    model = Column(String, index=True)
    brand = Column(String, nullable=True)
    price = Column(Float, nullable=True)
    location = Column(String)
    link = Column(String)
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
        length_formatted = None
        if self.length_ft is not None and self.length_in is not None:
            length_formatted = f"{self.length_ft}'{int(round(self.length_in))}\""

        width_formatted = f'{decimal_to_fraction_str(self.width_in)}"' if self.width_in is not None else None
        thickness_formatted = f'{decimal_to_fraction_str(self.thickness_in)}"' if self.thickness_in is not None else None

        return {
            "id": self.id,
            "model": self.model,
            "brand": self.brand,
            "price": self.price,
            "location": self.location,
            "link": self.link,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "length": length_formatted,
            "width": width_formatted,
            "thickness": thickness_formatted,
            "liters": self.liters
        }