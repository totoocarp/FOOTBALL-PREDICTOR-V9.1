"""
Football Predictor V9.0 - Main Page Routes (Updated)
BUG FIX: Logs page now shows data from SystemLog table (populated via loguru sink).
"""

from datetime import datetime
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from loguru import logger
from sqlalchemy import select, func

from app.database import AsyncSessionLocal
from app.models.team import Team, TeamStats
from app.models.match import Match, MatchPrediction, MatchResult
from app.models.competition import Competition
from app.models.learning import ModelWeight, ModelStatistics
from app.models.worldcup import WorldCupSimulation
from app.models.logs import SystemLog
from app.services.cache import cache
from app.services.data_collector import data_collector
from app.services.learning_engine import learning_engine
from app.services.scheduler import get_scheduler_jobs
from app.services.data_updater import data_updater

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    async with AsyncSessionLocal() as session:
        total_predictions = (await session.execute(
            select(func.count()).select_from(MatchPrediction)
        )).scalar()
        correct_q = await session.execute(
            select(func.count()).select_from(MatchPrediction)
            .where(MatchPrediction.was_correct_1x2 == True)
        )
        correct_predictions = correct_q.scalar()

    accuracy = 0.0
    if total_predictions and total_predictions > 0:
        accuracy = round(correct_predictions / total_predictions * 100, 1)

    sources = await data_collector.get_all_sources_status()
    scheduler_jobs = get_scheduler_jobs()
    update_status = await data_updater.get_all_update_status()

    return templates.TemplateResponse("index.html", {
        "request": request,
        "active_page": "home",
        "total_predictions": total_predictions or 0,
        "correct_predictions": correct_predictions or 0,
        "accuracy": accuracy,
        "sources": sources,
        "scheduler_jobs": scheduler_jobs,
        "update_status": update_status,
    })


@router.get("/predict", response_class=HTMLResponse)
async def predict_page(request: Request):
    return templates.TemplateResponse("predict.html", {
        "request": request,
        "active_page": "predict",
    })


@router.get("/worldcup", response_class=HTMLResponse)
async def worldcup_page(request: Request):
    from app.services.worldcup_predictor import WORLDCUP_2026_TEAMS, TEAM_ELO
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(WorldCupSimulation)
            .order_by(WorldCupSimulation.created_at.desc())
            .limit(1)
        )
        last_simulation = result.scalar_one_or_none()

    groups_data = {}
    for group, teams in WORLDCUP_2026_TEAMS.items():
        groups_data[group] = sorted(
            [{"name": t, "elo": TEAM_ELO.get(t, 1500), "flag": _get_flag_code(t)} for t in teams],
            key=lambda x: x["elo"], reverse=True,
        )

    return templates.TemplateResponse("worldcup.html", {
        "request": request,
        "active_page": "worldcup",
        "last_simulation": last_simulation,
        "groups": groups_data,
    })


@router.get("/ranking", response_class=HTMLResponse)
async def ranking_page(request: Request):
    await learning_engine.ensure_default_weights()
    weights = await learning_engine.get_weights_for_display()
    return templates.TemplateResponse("ranking.html", {
        "request": request,
        "active_page": "ranking",
        "weights": weights,
    })


@router.get("/statistics", response_class=HTMLResponse)
async def statistics_page(request: Request):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(ModelStatistics).order_by(ModelStatistics.category, ModelStatistics.stat_label)
        )
        statistics = result.scalars().all()

    return templates.TemplateResponse("statistics.html", {
        "request": request,
        "active_page": "statistics",
        "statistics": statistics,
    })


@router.get("/learning", response_class=HTMLResponse)
async def learning_page(request: Request):
    await learning_engine.ensure_default_weights()
    weights = await learning_engine.get_weights_for_display()
    history = await learning_engine.get_weight_history(days=30)

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(MatchPrediction)
            .where(MatchPrediction.was_correct_1x2.isnot(None))
            .order_by(MatchPrediction.created_at.desc())
            .limit(20)
        )
        recent_predictions = result.scalars().all()

    return templates.TemplateResponse("learning.html", {
        "request": request,
        "active_page": "learning",
        "weights": weights,
        "weight_history": history,
        "recent_predictions": recent_predictions,
    })


@router.get("/database", response_class=HTMLResponse)
async def database_page(request: Request):
    async with AsyncSessionLocal() as session:
        team_count = (await session.execute(select(func.count()).select_from(Team))).scalar()
        comp_count = (await session.execute(select(func.count()).select_from(Competition))).scalar()
        pred_count = (await session.execute(select(func.count()).select_from(MatchPrediction))).scalar()

    return templates.TemplateResponse("database.html", {
        "request": request,
        "active_page": "database",
        "team_count": team_count or 0,
        "competition_count": comp_count or 0,
        "prediction_count": pred_count or 0,
        "cache_stats": cache.stats(),
    })


@router.get("/logs", response_class=HTMLResponse)
async def logs_page(request: Request):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(SystemLog).order_by(SystemLog.created_at.desc()).limit(300)
        )
        logs = result.scalars().all()

    return templates.TemplateResponse("logs.html", {
        "request": request,
        "active_page": "logs",
        "logs": logs,
    })


@router.get("/data-updates", response_class=HTMLResponse)
async def data_updates_page(request: Request):
    update_status = await data_updater.get_all_update_status()
    todays_schedule = await data_updater.get_todays_schedule()
    rate_limits = await data_updater.get_api_rate_limits()

    return templates.TemplateResponse("data_updates.html", {
        "request": request,
        "active_page": "data_updates",
        "update_status": update_status,
        "todays_schedule": todays_schedule,
        "rate_limits": rate_limits,
        "now": datetime.now().strftime("%Y-%m-%d %H:%M"),
    })


@router.get("/system-health", response_class=HTMLResponse)
async def system_health_page(request: Request):
    from app.services.scheduler import get_scheduler_jobs
    update_status = await data_updater.get_all_update_status()
    jobs = get_scheduler_jobs()

    async with AsyncSessionLocal() as session:
        pred_count = (await session.execute(select(func.count()).select_from(MatchPrediction))).scalar()
        log_count = (await session.execute(select(func.count()).select_from(SystemLog))).scalar()
        weight_count = (await session.execute(select(func.count()).select_from(ModelWeight))).scalar()
        wc_count = (await session.execute(select(func.count()).select_from(WorldCupSimulation))).scalar()

    from app.config import settings
    return templates.TemplateResponse("system_health.html", {
        "request": request,
        "active_page": "system_health",
        "update_status": update_status,
        "scheduler_jobs": jobs,
        "db_stats": {
            "predictions": pred_count or 0,
            "logs": log_count or 0,
            "weights": weight_count or 0,
            "wc_simulations": wc_count or 0,
        },
        "cache": cache.stats(),
        "apis": {
            "football_data": bool(settings.football_data_api_key),
            "api_football": bool(settings.api_football_key),
            "odds_api": bool(settings.odds_api_key),
            "openai": settings.has_openai,
            "anthropic": settings.has_anthropic,
        },
        "now": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    })


@router.get("/ai", response_class=HTMLResponse)
async def ai_page(request: Request):
    from app.config import settings
    return templates.TemplateResponse("ai.html", {
        "request": request,
        "active_page": "ai",
        "has_ai": settings.has_ai,
        "ai_provider": "openai" if settings.has_openai else ("anthropic" if settings.has_anthropic else None),
    })


@router.get("/config", response_class=HTMLResponse)
async def config_page(request: Request):
    from app.config import settings
    return templates.TemplateResponse("config.html", {
        "request": request,
        "active_page": "config",
        "settings": {
            "has_football_data": bool(settings.football_data_api_key),
            "has_api_football": bool(settings.api_football_key),
            "has_odds_api": bool(settings.odds_api_key),
            "has_ai": settings.has_ai,
            "database_url": settings.database_url,
        },
    })


_FLAG_CODES = {
    "Argentina": "ar", "France": "fr", "Brazil": "br", "England": "gb-eng",
    "Spain": "es", "Belgium": "be", "Portugal": "pt", "Netherlands": "nl",
    "Germany": "de", "Croatia": "hr", "Denmark": "dk", "Uruguay": "uy",
    "Morocco": "ma", "USA": "us", "Mexico": "mx", "Colombia": "co",
    "Switzerland": "ch", "Japan": "jp", "Senegal": "sn", "South Korea": "kr",
    "Ecuador": "ec", "Poland": "pl", "Ivory Coast": "ci", "Serbia": "rs",
    "Chile": "cl", "Egypt": "eg", "Iran": "ir", "IR Iran": "ir",
    "Australia": "au", "Peru": "pe", "Nigeria": "ng", "Cameroon": "cm",
    "Saudi Arabia": "sa", "Qatar": "qa", "Canada": "ca", "Algeria": "dz",
    "Ghana": "gh", "Bolivia": "bo", "Costa Rica": "cr", "Paraguay": "py",
    "Bahrain": "bh", "New Zealand": "nz", "Jamaica": "jm", "Slovenia": "si",
    "South Africa": "za", "Sweden": "se", "Ukraine": "ua", "Tunisia": "tn",
}


def _get_flag_code(team: str) -> str:
    return _FLAG_CODES.get(team, "un")
