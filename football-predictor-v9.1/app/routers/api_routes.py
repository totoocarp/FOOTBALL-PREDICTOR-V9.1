"""
Football Predictor V9.0 - API Routes (Updated)
Adds: force update endpoints, data validation, learning history, system health, 
World Cup group stats, match schedule with dedup.
"""

from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from loguru import logger
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models.learning import ModelWeight, ModelStatistics, WeightHistory
from app.models.logs import SystemLog
from app.models.worldcup import WorldCupSimulation
from app.services.predictor import predictor
from app.services.worldcup_predictor import worldcup_simulator
from app.services.learning_engine import learning_engine
from app.services.data_updater import data_updater
from app.services.data_validator import data_validator
from app.services.cache import cache
from app.config import settings

router = APIRouter()


# ─────────────────────────────────────────────
# Models
# ─────────────────────────────────────────────
class TeamStats(BaseModel):
    elo_global: Optional[float] = None
    elo_12months: Optional[float] = None
    xg_avg: Optional[float] = None
    xga_avg: Optional[float] = None
    goals_per_game: Optional[float] = None
    goals_conceded_per_game: Optional[float] = None
    points_per_game: Optional[float] = None
    form_5: Optional[float] = None
    form_10: Optional[float] = None
    squad_value_total: Optional[float] = None
    injuries_key: Optional[int] = None
    odds_home_prob: Optional[float] = None
    possession_avg: Optional[float] = None
    shots_on_target_avg: Optional[float] = None
    clean_sheet_rate: Optional[float] = None
    games_last_30: Optional[int] = None
    ranking_percentile: Optional[float] = None


class PredictRequest(BaseModel):
    home_team: str
    away_team: str
    competition: str = "Unknown"
    home_stats: Optional[TeamStats] = None
    away_stats: Optional[TeamStats] = None
    force_refresh: bool = False


class WorldCupRequest(BaseModel):
    groups: Optional[dict] = None
    n_simulations: int = 20000


class AIRequest(BaseModel):
    home_team: str
    away_team: str
    competition: str = "Unknown"
    prediction: Optional[dict] = None


class ValidateRequest(BaseModel):
    team: str
    stats: dict


# ─────────────────────────────────────────────
# Health
# ─────────────────────────────────────────────
@router.get("/health")
async def health():
    return {
        "status": "ok",
        "version": "9.0.0",
        "timestamp": datetime.utcnow().isoformat(),
        "monte_carlo": "active",
    }


# ─────────────────────────────────────────────
# Predictions
# ─────────────────────────────────────────────
@router.post("/predict")
async def predict_match(req: PredictRequest):
    if not req.home_team.strip() or not req.away_team.strip():
        raise HTTPException(400, "home_team and away_team are required")

    home_stats = req.home_stats.model_dump(exclude_none=True) if req.home_stats else None
    away_stats = req.away_stats.model_dump(exclude_none=True) if req.away_stats else None

    try:
        result = await predictor.predict_match(
            home_team=req.home_team.strip(),
            away_team=req.away_team.strip(),
            home_stats=home_stats,
            away_stats=away_stats,
            competition=req.competition,
            force_refresh=req.force_refresh,
        )
        logger.info(f"Prediction: {req.home_team} vs {req.away_team} | {result['most_likely_score']} | conf={result['confidence_score']:.2f}")
        return {"success": True, "data": result}
    except Exception as e:
        logger.error(f"Prediction error: {e}")
        raise HTTPException(500, f"Prediction failed: {str(e)}")


@router.post("/validate-stats")
async def validate_stats(req: ValidateRequest):
    """Validate team stats data quality — returns confidence levels."""
    result = data_validator.validate_team_stats(req.stats, req.team)
    return {"success": True, "data": result}


@router.get("/team-elo/{team_name}")
async def get_team_elo(team_name: str):
    """Look up a team in the built-in club ELO database."""
    from app.services.predictor import lookup_team_stats
    stats = lookup_team_stats(team_name)
    if not stats:
        return {"success": False, "found": False, "team": team_name}
    return {"success": True, "found": True, "team": team_name, "data": stats}


# ─────────────────────────────────────────────
# World Cup
# ─────────────────────────────────────────────
@router.post("/worldcup/simulate")
async def simulate_worldcup(req: WorldCupRequest):
    try:
        from app.services.worldcup_predictor import WorldCupSimulator, WORLDCUP_2026_TEAMS
        groups = req.groups or WORLDCUP_2026_TEAMS
        sim = WorldCupSimulator(n_simulations=req.n_simulations)
        result = await sim.run_simulation(groups)

        async with AsyncSessionLocal() as session:
            wcs = WorldCupSimulation(
                simulations_count=result["simulations_count"],
                most_likely_champion=result["most_likely_champion"],
                most_likely_final=result["most_likely_final"],
                champion_probs=result["champion_probs"],
                finalist_probs=result["finalist_probs"],
                semifinalist_probs=result["semifinalist_probs"],
                quarterfinalist_probs=result["quarterfinalist_probs"],
            )
            session.add(wcs)
            await session.commit()

        logger.info(f"World Cup simulated: champion={result['most_likely_champion']}")
        return {"success": True, "data": result}
    except Exception as e:
        logger.error(f"World Cup simulation error: {e}")
        raise HTTPException(500, f"Simulation failed: {str(e)}")


@router.get("/worldcup/groups")
async def get_worldcup_groups():
    """Return World Cup 2026 group data with ELO ratings and fixture results."""
    from app.services.worldcup_predictor import WORLDCUP_2026_TEAMS, TEAM_ELO, WORLDCUP_2026_FIXTURE
    groups_with_elo = {}
    for group, teams in WORLDCUP_2026_TEAMS.items():
        groups_with_elo[group] = [
            {
                "name": team,
                "elo": TEAM_ELO.get(team, 1500),
                "flag_code": _get_flag_code(team),
            }
            for team in sorted(teams, key=lambda t: TEAM_ELO.get(t, 1500), reverse=True)
        ]
    return {"success": True, "groups": groups_with_elo, "fixtures": WORLDCUP_2026_FIXTURE}


@router.post("/worldcup/ai-analysis")
async def worldcup_ai_analysis(data: dict):
    from app.services.ai_assistant import ai_assistant
    result = await ai_assistant.analyze_worldcup(data)
    return result


# ─────────────────────────────────────────────
# Learning
# ─────────────────────────────────────────────
@router.post("/learning/update")
async def trigger_learning_update():
    try:
        result = await learning_engine.update_results_and_learn()
        return {"success": True, "data": result}
    except Exception as e:
        logger.error(f"Learning update error: {e}")
        raise HTTPException(500, str(e))


@router.get("/learning/weights")
async def get_weights():
    weights = await learning_engine.get_weights_for_display()
    return {"success": True, "data": weights}


@router.get("/learning/history")
async def get_weight_history(days: int = 30):
    history = await learning_engine.get_weight_history(days)
    return {"success": True, "data": history}


@router.post("/learning/snapshot")
async def take_weight_snapshot():
    await learning_engine.snapshot_weights()
    return {"success": True, "message": "Snapshot guardado"}


# ─────────────────────────────────────────────
# Data Updates
# ─────────────────────────────────────────────
@router.get("/updates/status")
async def get_update_status():
    status = await data_updater.get_all_update_status()
    return {"success": True, "data": status}


@router.post("/updates/fetch-matches")
async def force_fetch_matches():
    try:
        matches = await data_updater.fetch_todays_matches(force=True)
        return {"success": True, "data": matches, "count": len(matches)}
    except Exception as e:
        logger.error(f"Force fetch matches error: {e}")
        raise HTTPException(500, str(e))


@router.post("/updates/generate-predictions")
async def generate_daily_predictions(force: bool = False):
    try:
        result = await data_updater.generate_daily_predictions(force=force)
        return {"success": True, "data": result}
    except Exception as e:
        logger.error(f"Generate daily predictions error: {e}")
        raise HTTPException(500, str(e))


@router.post("/updates/injuries")
async def force_update_injuries():
    result = await data_updater.update_volatile_category("injuries", force=True)
    return {"success": True, "data": result}


@router.post("/updates/odds")
async def force_update_odds():
    result = await data_updater.update_volatile_category("odds", force=True)
    return {"success": True, "data": result}


@router.post("/updates/results")
async def force_update_results():
    result = await data_updater.check_for_results()
    return {"success": True, "data": result}


@router.post("/updates/volatile")
async def force_update_volatile():
    try:
        result = await data_updater.update_volatile_data(force=True)
        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/updates/schedule")
async def get_todays_schedule():
    matches = await data_updater.get_todays_schedule()
    return {"success": True, "data": matches, "count": len(matches)}


@router.get("/updates/rate-limits")
async def get_api_rate_limits():
    limits = await data_updater.get_api_rate_limits()
    return {"success": True, "data": limits}


@router.post("/updates/check-results")
async def check_results():
    result = await data_updater.check_for_results()
    return {"success": True, "data": result}


# ─────────────────────────────────────────────
# AI
# ─────────────────────────────────────────────
@router.post("/ai/analyze")
async def ai_analyze(req: AIRequest):
    from app.services.ai_assistant import ai_assistant
    result = await ai_assistant.analyze_prediction(
        req.home_team, req.away_team, req.competition, req.prediction or {}
    )
    return result


# ─────────────────────────────────────────────
# Cache
# ─────────────────────────────────────────────
@router.post("/cache/clear")
async def clear_cache():
    count = cache.clear_all()
    return {"success": True, "message": f"Cache limpiada: {count} entradas eliminadas"}


@router.get("/cache/stats")
async def get_cache_stats():
    return {"success": True, "data": cache.stats()}


# ─────────────────────────────────────────────
# System Health
# ─────────────────────────────────────────────
@router.get("/system/health")
async def system_health():
    from app.models.team import Team, TeamStats
    from app.models.match import Match, MatchPrediction
    from app.models.worldcup import WorldCupSimulation

    async with AsyncSessionLocal() as session:
        prediction_count = (await session.execute(select(func.count()).select_from(MatchPrediction))).scalar()
        log_count = (await session.execute(select(func.count()).select_from(SystemLog))).scalar()
        weight_count = (await session.execute(select(func.count()).select_from(ModelWeight))).scalar()
        wc_count = (await session.execute(select(func.count()).select_from(WorldCupSimulation))).scalar()

    update_status = await data_updater.get_all_update_status()
    errors = [s for s in update_status if s["status"] == "error"]

    from app.services.scheduler import get_scheduler_jobs
    jobs = get_scheduler_jobs()

    return {
        "success": True,
        "data": {
            "status": "healthy" if not errors else "degraded",
            "version": "9.0.0",
            "timestamp": datetime.utcnow().isoformat(),
            "db": {
                "predictions": prediction_count,
                "logs": log_count,
                "weights": weight_count,
                "wc_simulations": wc_count,
            },
            "cache": cache.stats(),
            "updates": update_status,
            "scheduler_jobs": jobs,
            "errors": errors,
            "ai_available": settings.has_ai,
            "ai_provider": "openai" if settings.has_openai else ("anthropic" if settings.has_anthropic else "none"),
            "apis": {
                "football_data": bool(settings.football_data_api_key),
                "api_football": bool(settings.api_football_key),
                "odds_api": bool(settings.odds_api_key),
                "openai": settings.has_openai,
                "anthropic": settings.has_anthropic,
            },
        },
    }


@router.get("/system/info")
async def system_info():
    """Return system configuration info (no secrets)."""
    return {
        "version": "9.0.0",
        "model": "Monte Carlo 20K",
        "n_simulations": 20000,
        "variables": ["elo", "xg", "form", "market", "squad_value", "availability", "ranking", "fatigue"],
        "features": [
            "Monte Carlo simulation (20.000 runs)",
            "Club ELO database (~200 clubs)",
            "Variable weight learning",
            "World Cup 2026 simulation (WC format: 12 groups, 32-team knockout)",
            "Data validation with confidence levels",
            "Anti-loop match deduplication",
            "Learning history tracking",
            "Optional AI narrative analysis",
            "API rate limits display",
        ],
        "apis_configured": {
            "football_data": bool(settings.football_data_api_key),
            "api_football": bool(settings.api_football_key),
            "odds_api": bool(settings.odds_api_key),
        },
    }


# ─────────────────────────────────────────────
# Logs
# ─────────────────────────────────────────────
@router.get("/logs")
async def get_logs(level: Optional[str] = None, limit: int = 200):
    async with AsyncSessionLocal() as session:
        stmt = select(SystemLog).order_by(SystemLog.created_at.desc())
        if level:
            stmt = stmt.where(SystemLog.level == level.upper())
        stmt = stmt.limit(limit)
        result = await session.execute(stmt)
        logs = result.scalars().all()
    return {
        "success": True,
        "data": [
            {
                "id": l.id,
                "level": l.level,
                "module": l.module,
                "message": l.message,
                "created_at": l.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            }
            for l in logs
        ],
    }


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────
_FLAG_CODES = {
    "Argentina": "ar", "France": "fr", "Brazil": "br", "England": "gb-eng",
    "Spain": "es", "Belgium": "be", "Portugal": "pt", "Netherlands": "nl",
    "Germany": "de", "Italy": "it", "Croatia": "hr", "Denmark": "dk",
    "Uruguay": "uy", "Morocco": "ma", "USA": "us", "Mexico": "mx",
    "Colombia": "co", "Switzerland": "ch", "Japan": "jp", "Senegal": "sn",
    "South Korea": "kr", "Ecuador": "ec", "Poland": "pl", "Ivory Coast": "ci",
    "Serbia": "rs", "Chile": "cl", "Egypt": "eg", "Iran": "ir", "IR Iran": "ir",
    "Australia": "au", "Peru": "pe", "Nigeria": "ng", "Cameroon": "cm",
    "Saudi Arabia": "sa", "Qatar": "qa", "Canada": "ca", "Algeria": "dz",
    "Ghana": "gh", "Bolivia": "bo", "Costa Rica": "cr", "Romania": "ro",
    "Greece": "gr", "Iraq": "iq", "Panama": "pa", "Paraguay": "py",
    "Bahrain": "bh", "New Zealand": "nz", "Jamaica": "jm", "Slovenia": "si",
    "South Africa": "za", "Sweden": "se", "Ukraine": "ua", "Tunisia": "tn",
    "Venezuela": "ve", "Turkey": "tr", "Scotland": "gb-sct", "Wales": "gb-wls",
    "Ireland": "ie", "Czech Republic": "cz", "Slovakia": "sk", "Hungary": "hu",
    "Austria": "at", "Israel": "il", "Kosovo": "xk", "Albania": "al",
    "North Macedonia": "mk", "Montenegro": "me", "Bosnia": "ba",
    "Zimbabwe": "zw", "DR Congo": "cd", "Ethiopia": "et",
}


def _get_flag_code(team_name: str) -> str:
    return _FLAG_CODES.get(team_name, "un")
