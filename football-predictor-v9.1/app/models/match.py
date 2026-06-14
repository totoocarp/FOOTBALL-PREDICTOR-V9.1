"""Match and prediction models."""

from datetime import datetime
from typing import Optional
from sqlalchemy import String, Float, Integer, DateTime, Boolean, Text, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Match(Base):
    __tablename__ = "matches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    external_id: Mapped[Optional[str]] = mapped_column(String(50), unique=True, index=True)
    competition_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("competitions.id"))
    home_team_id: Mapped[int] = mapped_column(Integer, ForeignKey("teams.id"), index=True)
    away_team_id: Mapped[int] = mapped_column(Integer, ForeignKey("teams.id"), index=True)
    match_date: Mapped[Optional[datetime]] = mapped_column(DateTime, index=True)
    season: Mapped[Optional[str]] = mapped_column(String(20))
    matchday: Mapped[Optional[int]] = mapped_column(Integer)
    venue: Mapped[Optional[str]] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(30), default="SCHEDULED")  # SCHEDULED, LIVE, FINISHED, POSTPONED
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    result: Mapped[Optional["MatchResult"]] = relationship("MatchResult", back_populates="match", uselist=False)
    predictions: Mapped[list["MatchPrediction"]] = relationship("MatchPrediction", back_populates="match")

    def __repr__(self) -> str:
        return f"<Match {self.id}: {self.home_team_id} vs {self.away_team_id}>"


class MatchResult(Base):
    __tablename__ = "match_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    match_id: Mapped[int] = mapped_column(Integer, ForeignKey("matches.id"), unique=True, index=True)
    home_score: Mapped[int] = mapped_column(Integer)
    away_score: Mapped[int] = mapped_column(Integer)
    home_score_ht: Mapped[Optional[int]] = mapped_column(Integer)
    away_score_ht: Mapped[Optional[int]] = mapped_column(Integer)
    home_xg: Mapped[Optional[float]] = mapped_column(Float)
    away_xg: Mapped[Optional[float]] = mapped_column(Float)
    winner: Mapped[str] = mapped_column(String(10))  # HOME, AWAY, DRAW
    btts: Mapped[bool] = mapped_column(Boolean)
    total_goals: Mapped[int] = mapped_column(Integer)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    match: Mapped["Match"] = relationship("Match", back_populates="result")


class MatchPrediction(Base):
    __tablename__ = "match_predictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    match_id: Mapped[int] = mapped_column(Integer, ForeignKey("matches.id"), index=True)
    model_version: Mapped[str] = mapped_column(String(20), default="9.0.0")
    prediction_type: Mapped[str] = mapped_column(String(30), default="full_model")
    variable_name: Mapped[Optional[str]] = mapped_column(String(50))

    # Probabilities
    home_win_prob: Mapped[float] = mapped_column(Float)
    draw_prob: Mapped[float] = mapped_column(Float)
    away_win_prob: Mapped[float] = mapped_column(Float)

    # Goals
    home_goals_expected: Mapped[float] = mapped_column(Float)
    away_goals_expected: Mapped[float] = mapped_column(Float)

    # Most likely scoreline
    most_likely_score: Mapped[Optional[str]] = mapped_column(String(10))

    # Extra markets
    btts_prob: Mapped[float] = mapped_column(Float, default=0.5)
    over_25_prob: Mapped[float] = mapped_column(Float, default=0.5)
    over_35_prob: Mapped[float] = mapped_column(Float, default=0.3)
    penalties_prob: Mapped[float] = mapped_column(Float, default=0.0)
    extra_time_prob: Mapped[float] = mapped_column(Float, default=0.0)

    # Scoreline distribution (JSON dict: "1-0": 0.12, ...)
    score_distribution: Mapped[Optional[dict]] = mapped_column(JSON)

    # Confidence
    confidence_score: Mapped[float] = mapped_column(Float, default=0.5)
    simulations_run: Mapped[int] = mapped_column(Integer, default=20000)

    # Outcome tracking
    was_correct_1x2: Mapped[Optional[bool]] = mapped_column(Boolean)
    was_correct_score: Mapped[Optional[bool]] = mapped_column(Boolean)
    was_correct_btts: Mapped[Optional[bool]] = mapped_column(Boolean)
    was_correct_ou25: Mapped[Optional[bool]] = mapped_column(Boolean)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    match: Mapped["Match"] = relationship("Match", back_populates="predictions")
