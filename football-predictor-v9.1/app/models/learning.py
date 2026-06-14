"""Learning engine models."""

from datetime import datetime
from typing import Optional
from sqlalchemy import String, Float, Integer, DateTime, Boolean, JSON, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class LearningPrediction(Base):
    """Individual variable predictions for the learning engine."""
    __tablename__ = "learning_predictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    match_id: Mapped[int] = mapped_column(Integer, ForeignKey("matches.id"), index=True)
    variable_name: Mapped[str] = mapped_column(String(50), index=True)
    model_version: Mapped[str] = mapped_column(String(20), default="9.0.0")

    home_win_prob: Mapped[float] = mapped_column(Float)
    draw_prob: Mapped[float] = mapped_column(Float)
    away_win_prob: Mapped[float] = mapped_column(Float)
    home_goals_expected: Mapped[float] = mapped_column(Float)
    away_goals_expected: Mapped[float] = mapped_column(Float)

    was_correct: Mapped[Optional[bool]] = mapped_column(Boolean)
    error_magnitude: Mapped[Optional[float]] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ModelWeight(Base):
    """Auto-adjusted weights for each variable."""
    __tablename__ = "model_weights"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    variable_name: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    accuracy: Mapped[float] = mapped_column(Float, default=0.0)
    predictions_count: Mapped[int] = mapped_column(Integer, default=0)
    correct_count: Mapped[int] = mapped_column(Integer, default=0)
    last_adjusted: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ModelStatistics(Base):
    """Aggregate model statistics."""
    __tablename__ = "model_statistics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    stat_key: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    stat_value: Mapped[float] = mapped_column(Float, default=0.0)
    stat_label: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(50), default="general")
    period: Mapped[Optional[str]] = mapped_column(String(20))
    extra_data: Mapped[Optional[dict]] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class WeightHistory(Base):
    """Historical record of weight changes for Learning History section."""
    __tablename__ = "weight_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    snapshot_date: Mapped[str] = mapped_column(String(10), index=True)  # YYYY-MM-DD
    variable_name: Mapped[str] = mapped_column(String(50), index=True)
    weight: Mapped[float] = mapped_column(Float)
    accuracy: Mapped[float] = mapped_column(Float, default=0.0)
    predictions_count: Mapped[int] = mapped_column(Integer, default=0)
    weight_delta: Mapped[float] = mapped_column(Float, default=0.0)
    accuracy_delta: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
