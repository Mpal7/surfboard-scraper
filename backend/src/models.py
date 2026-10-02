from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text
from sqlalchemy.ext.hybrid import hybrid_property
from src.database import Base
from datetime import datetime, timezone
import json
import math
import uuid

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


def _job_utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class JobRun(Base):
    """A tracked unit of background work (scrape or ad-status check)."""

    __tablename__ = "job_runs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    job_type = Column(String, nullable=False, index=True)
    trigger_source = Column(String, nullable=False, default="manual")
    status = Column(String, nullable=False, default="queued", index=True)
    worker_type = Column(String, nullable=True)
    celery_task_id = Column(String, nullable=True, index=True)
    result_json = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=_job_utcnow, nullable=False, index=True)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)

    def result_payload(self):
        if not self.result_json:
            return None
        try:
            return json.loads(self.result_json)
        except (TypeError, ValueError):
            return {"raw": self.result_json}

    def to_dict(self):
        return {
            "id": self.id,
            "job_type": self.job_type,
            "trigger_source": self.trigger_source,
            "status": self.status,
            "worker_type": self.worker_type,
            "celery_task_id": self.celery_task_id,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "result": self.result_payload(),
        }
