"""Team models."""

from datetime import datetime
from typing import Optional
from sqlalchemy import String, Float, Integer, DateTime, Boolean, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    external_id: Mapped[Optional[str]] = mapped_column(String(50), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    short_name: Mapped[Optional[str]] = mapped_column(String(10))
    country: Mapped[Optional[str]] = mapped_column(String(100))
    logo_url: Mapped[Optional[str]] = mapped_column(String(500))
    is_national: Mapped[bool] = mapped_column(Boolean, default=False)
    fifa_ranking: Mapped[Optional[int]] = mapped_column(Integer)
    founded: Mapped[Optional[int]] = mapped_column(Integer)
    stadium: Mapped[Optional[str]] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    stats: Mapped[Optional["TeamStats"]] = relationship("TeamStats", back_populates="team", uselist=False)

    def __repr__(self) -> str:
        return f"<Team {self.name}>"


class TeamStats(Base):
    __tablename__ = "team_stats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    team_id: Mapped[int] = mapped_column(Integer, ForeignKey("teams.id"), unique=True, index=True)

    # ELO
    elo_global: Mapped[float] = mapped_column(Float, default=1500.0)
    elo_12months: Mapped[float] = mapped_column(Float, default=1500.0)

    # xG stats
    xg_avg: Mapped[float] = mapped_column(Float, default=1.2)
    xga_avg: Mapped[float] = mapped_column(Float, default=1.2)
    xg_diff: Mapped[float] = mapped_column(Float, default=0.0)

    # Goals
    goals_per_game: Mapped[float] = mapped_column(Float, default=1.2)
    goals_conceded_per_game: Mapped[float] = mapped_column(Float, default=1.2)
    points_per_game: Mapped[float] = mapped_column(Float, default=1.2)

    # Home/Away
    home_win_rate: Mapped[float] = mapped_column(Float, default=0.45)
    away_win_rate: Mapped[float] = mapped_column(Float, default=0.30)

    # Form (W=3, D=1, L=0 encoded as float 0-1)
    form_5: Mapped[float] = mapped_column(Float, default=0.5)
    form_10: Mapped[float] = mapped_column(Float, default=0.5)

    # Squad value (millions EUR)
    squad_value_total: Mapped[float] = mapped_column(Float, default=0.0)
    squad_value_xi: Mapped[float] = mapped_column(Float, default=0.0)

    # Injuries/suspensions count
    injuries_key: Mapped[int] = mapped_column(Integer, default=0)
    suspensions: Mapped[int] = mapped_column(Integer, default=0)

    # Betting odds (implied probability home win)
    odds_home_prob: Mapped[float] = mapped_column(Float, default=0.45)

    # Play style
    possession_avg: Mapped[float] = mapped_column(Float, default=50.0)
    shots_on_target_avg: Mapped[float] = mapped_column(Float, default=4.0)
    clean_sheet_rate: Mapped[float] = mapped_column(Float, default=0.30)

    # Schedule/fatigue (games last 30 days)
    games_last_30: Mapped[int] = mapped_column(Integer, default=4)

    # National team specific
    intl_experience_avg: Mapped[float] = mapped_column(Float, default=30.0)
    world_cup_participations: Mapped[int] = mapped_column(Integer, default=0)
    top5_league_players: Mapped[int] = mapped_column(Integer, default=0)
    ucl_players: Mapped[int] = mapped_column(Integer, default=0)

    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    team: Mapped["Team"] = relationship("Team", back_populates="stats")
