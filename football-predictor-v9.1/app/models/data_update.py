"""Data update tracking models."""

from datetime import datetime
from typing import Optional
from sqlalchemy import String, Float, Integer, DateTime, Boolean, JSON, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class UpdateRecord(Base):
    """Tracks when each data category was last updated."""
    __tablename__ = "update_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    category: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    # Categories: full_data, volatile_data, injuries, odds, squads, worldcup
    last_update: Mapped[Optional[datetime]] = mapped_column(DateTime)
    next_update: Mapped[Optional[datetime]] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # ok, error, pending
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    records_updated: Mapped[int] = mapped_column(Integer, default=0)
    duration_seconds: Mapped[float] = mapped_column(Float, default=0.0)
    source: Mapped[Optional[str]] = mapped_column(String(100))
    extra: Mapped[Optional[dict]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class MatchSchedule(Base):
    """Today's matches to predict — with dedup via match_uid."""
    __tablename__ = "match_schedule"
    __table_args__ = (
        UniqueConstraint("competition", "match_date", "home_team", "away_team", name="uq_match_schedule_natural_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    match_uid: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    home_team: Mapped[str] = mapped_column(String(200))
    away_team: Mapped[str] = mapped_column(String(200))
    competition: Mapped[str] = mapped_column(String(200))
    match_date: Mapped[Optional[datetime]] = mapped_column(DateTime, index=True)
    source: Mapped[str] = mapped_column(String(50), default="unknown")
    status: Mapped[str] = mapped_column(String(30), default="SCHEDULED")
    predicted: Mapped[bool] = mapped_column(Boolean, default=False)
    simulation_run: Mapped[bool] = mapped_column(Boolean, default=False)
    result_checked: Mapped[bool] = mapped_column(Boolean, default=False)
    home_score: Mapped[Optional[int]] = mapped_column(Integer)
    away_score: Mapped[Optional[int]] = mapped_column(Integer)
    prediction_snapshot: Mapped[Optional[dict]] = mapped_column(JSON)
    volatile_updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
