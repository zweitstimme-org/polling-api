from sqlalchemy import Column, Integer, String, Text

from .database import Base


class Forecast(Base):
    __tablename__ = "forecasts"

    id = Column(Integer, primary_key=True, nullable=False)
    publish_date = Column(String(50))
    Befragte = Column(String(255))
    Zeitraum = Column(String(255))
    survey_date_start = Column(String(255))
    survey_date_end = Column(String(255))
    parties = Column(Text)
    institute_id = Column(String(255))
    forecast_provider = Column(String(255))
    source = Column(String(255))
    scope = Column(String(255))
    election_id = Column(String(255))
    method_id = Column(String(255))
    date_downloaded = Column(String(50))
    content_hash = Column(String(64))
