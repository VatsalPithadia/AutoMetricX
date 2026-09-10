import datetime
from datetime import timezone
from sqlalchemy import Column, Integer, String, Float, Text, DateTime
from app.database import Base

class ScanRecord(Base):
    __tablename__ = "scans"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    timestamp = Column(DateTime, default=lambda: datetime.datetime.now(timezone.utc), index=True)
    image_filename = Column(String(255), nullable=False)
    product_name = Column(String(255), default="Unknown", index=True)
    overall_status = Column(String(50), nullable=False, index=True)
    compliance_score = Column(Float, nullable=False)
    full_report_json = Column(Text, nullable=False)
