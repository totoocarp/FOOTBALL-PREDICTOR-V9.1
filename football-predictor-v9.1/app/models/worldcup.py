"""World Cup 2026 models."""

from datetime import datetime
from typing import Optional
from sqlalchemy import String, Float, Integer, DateTime, Boolean, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


WORLDCUP_2026_GROUPS = {
    "A": ["Qatar", "Ecuador", "Senegal", "Netherlands"],  # placeholder until draw
    "B": ["England", "Iran", "USA", "Wales"],
    "C": ["Argentina", "Saudi Arabia", "Mexico", "Poland"],
    "D": ["France", "Australia", "Denmark", "Tunisia"],
    "E": ["Spain", "Costa Rica", "Germany", "Japan"],
    "F": ["Belgium", "Canada", "Morocco", "Croatia"],
    "G": ["Brazil", "Serbia", "Switzerland", "Cameroon"],
    "H": ["Portugal", "Ghana", "Uruguay", "South Korea"],
    # World Cup 2026 has 48 teams - 12 groups of 4
    "I": ["Italy", "Colombia", "Greece", "Venezuela"],
    "J": ["Netherlands", "Algeria", "Chile", "Romania"],
    "K": ["Egypt", "Ivory Coast", "Mexico", "Jamaica"],
    "L": ["India", "South Africa", "Norway", "Honduras"],
}


class WorldCupGroup(Base):
    __tablename__ = "worldcup_groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    year: Mapped[int] = mapped_column(Integer, default=2026)
    group_name: Mapped[str] = mapped_column(String(5))
    teams: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class WorldCupTeam(Base):
    __tablename__ = "worldcup_teams"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    year: Mapped[int] = mapped_column(Integer, default=2026)
    team_name: Mapped[str] = mapped_column(String(200))
    team_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("teams.id"))
    group_name: Mapped[Optional[str]] = mapped_column(String(5))
    seeding: Mapped[Optional[int]] = mapped_column(Integer)
    qualified: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class WorldCupSimulation(Base):
    __tablename__ = "worldcup_simulations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    year: Mapped[int] = mapped_column(Integer, default=2026)
    simulations_count: Mapped[int] = mapped_column(Integer, default=20000)

    # Results as probabilities (0-100)
    champion_probs: Mapped[dict] = mapped_column(JSON)
    finalist_probs: Mapped[dict] = mapped_column(JSON)
    semifinalist_probs: Mapped[dict] = mapped_column(JSON)
    quarterfinalist_probs: Mapped[dict] = mapped_column(JSON)
    r16_probs: Mapped[dict] = mapped_column(JSON)
    group_advance_probs: Mapped[dict] = mapped_column(JSON)

    most_likely_champion: Mapped[Optional[str]] = mapped_column(String(200))
    most_likely_final: Mapped[Optional[str]] = mapped_column(String(200))

    duration_seconds: Mapped[Optional[float]] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class WorldCupResult(Base):
    """Stores group stage and knockout results."""
    __tablename__ = "worldcup_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    simulation_id: Mapped[int] = mapped_column(Integer, ForeignKey("worldcup_simulations.id"), index=True)
    round: Mapped[str] = mapped_column(String(30))  # GROUP, R16, QF, SF, FINAL, 3RD
    home_team: Mapped[str] = mapped_column(String(200))
    away_team: Mapped[str] = mapped_column(String(200))
    home_goals: Mapped[int] = mapped_column(Integer)
    away_goals: Mapped[int] = mapped_column(Integer)
    winner: Mapped[Optional[str]] = mapped_column(String(200))
    went_to_penalties: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
