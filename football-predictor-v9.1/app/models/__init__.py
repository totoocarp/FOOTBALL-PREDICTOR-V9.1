"""
Football Predictor V9.0 - Models
Import all models here so SQLAlchemy creates all tables.
"""

from app.models.team import Team, TeamStats
from app.models.match import Match, MatchPrediction, MatchResult
from app.models.player import Player, PlayerStats
from app.models.competition import Competition, Season
from app.models.learning import LearningPrediction, ModelWeight, ModelStatistics, WeightHistory
from app.models.worldcup import WorldCupGroup, WorldCupTeam, WorldCupSimulation, WorldCupResult
from app.models.logs import SystemLog
from app.models.data_update import UpdateRecord, MatchSchedule

all_models = [
    Team, TeamStats, Match, MatchPrediction, MatchResult,
    Player, PlayerStats, Competition, Season,
    LearningPrediction, ModelWeight, ModelStatistics, WeightHistory,
    WorldCupGroup, WorldCupTeam, WorldCupSimulation, WorldCupResult,
    SystemLog,
    UpdateRecord, MatchSchedule,
]
