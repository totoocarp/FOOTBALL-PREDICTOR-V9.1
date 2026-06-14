"""Player models."""

from datetime import datetime, date
from typing import Optional
from sqlalchemy import String, Float, Integer, DateTime, Boolean, Text, ForeignKey, Date
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Player(Base):
    __tablename__ = "players"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    external_id: Mapped[Optional[str]] = mapped_column(String(50), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    team_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("teams.id"), index=True)
    position: Mapped[Optional[str]] = mapped_column(String(10))
    nationality: Mapped[Optional[str]] = mapped_column(String(100))
    birth_date: Mapped[Optional[date]] = mapped_column(Date)
    market_value: Mapped[float] = mapped_column(Float, default=0.0)  # millions EUR
    photo_url: Mapped[Optional[str]] = mapped_column(String(500))
    is_injured: Mapped[bool] = mapped_column(Boolean, default=False)
    is_suspended: Mapped[bool] = mapped_column(Boolean, default=False)
    injury_return_date: Mapped[Optional[date]] = mapped_column(Date)
    international_caps: Mapped[int] = mapped_column(Integer, default=0)
    international_goals: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    stats: Mapped[Optional["PlayerStats"]] = relationship("PlayerStats", back_populates="player", uselist=False)


class PlayerStats(Base):
    __tablename__ = "player_stats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_id: Mapped[int] = mapped_column(Integer, ForeignKey("players.id"), unique=True, index=True)
    season: Mapped[Optional[str]] = mapped_column(String(20))
    goals: Mapped[int] = mapped_column(Integer, default=0)
    assists: Mapped[int] = mapped_column(Integer, default=0)
    appearances: Mapped[int] = mapped_column(Integer, default=0)
    minutes_played: Mapped[int] = mapped_column(Integer, default=0)
    xg: Mapped[float] = mapped_column(Float, default=0.0)
    xa: Mapped[float] = mapped_column(Float, default=0.0)
    rating_avg: Mapped[float] = mapped_column(Float, default=6.5)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    player: Mapped["Player"] = relationship("Player", back_populates="stats")
