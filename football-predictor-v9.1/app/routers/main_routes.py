"""
Football Predictor V9.0 - Main Page Routes (Updated)
BUG FIX: Logs page now shows data from SystemLog table (populated via loguru sink).
"""

from datetime import datetime
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from loguru import logger
from sqlalchemy import select, func

from app.database import AsyncSessionLocal
from app.models.team import Team, TeamStats
from app.models.match import Match, MatchPrediction, MatchResult
from app.models.competition import Competition
from app.models.learning import ModelWeight, ModelStatistics, LearningPrediction, WeightHistory
from app.models.worldcup import WorldCupSimulation
from app.models.logs import SystemLog
from app.models.data_update import MatchSchedule
from app.services.cache import cache
from app.services.data_collector import data_collector
from app.services.learning_engine import learning_engine
from app.services.scheduler import get_scheduler_jobs
from app.services.data_updater import data_updater

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/")
async def index(request: Request):
    """Beta entrypoint: public home is disabled; learning is the product center."""
    return RedirectResponse(url="/learning", status_code=307)


async def _disabled_public_module(module_name: str):
    """Keep future modules out of the beta web surface without deleting internals."""
    raise HTTPException(
        status_code=404,
        detail=f"{module_name} está oculto durante la Beta. Usa Aprendizaje, Data Updates, Estadísticas o System Health.",
    )


@router.get("/predict", response_class=HTMLResponse)
async def predict_page(request: Request):
    await _disabled_public_module("Predictor manual")


@router.get("/worldcup", response_class=HTMLResponse)
async def worldcup_page(request: Request):
    await _disabled_public_module("Mundial 2026")


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
        pending_learning = (await session.execute(
            select(func.count()).select_from(MatchSchedule)
            .where(MatchSchedule.predicted == True)
            .where(MatchSchedule.result_checked == False)
        )).scalar()
        learned_total = (await session.execute(
            select(func.count()).select_from(MatchPrediction)
            .where(MatchPrediction.was_correct_1x2.isnot(None))
        )).scalar()
        learned_today = (await session.execute(
            select(func.count()).select_from(MatchPrediction)
            .where(MatchPrediction.was_correct_1x2.isnot(None))
            .where(func.date(MatchPrediction.created_at) == datetime.utcnow().date().isoformat())
        )).scalar()
        recent_changes = (await session.execute(
            select(WeightHistory)
            .order_by(WeightHistory.created_at.desc())
            .limit(30)
        )).scalars().all()

    return templates.TemplateResponse("learning.html", {
        "request": request,
        "active_page": "learning",
        "weights": weights,
        "weight_history": history,
        "recent_predictions": recent_predictions,
        "learning_summary": {
            "pending_learning": pending_learning or 0,
            "learned_today": learned_today or 0,
            "learned_total": learned_total or 0,
            "active_variables": len(weights),
        },
        "recent_changes": recent_changes,
    })


@router.get("/database", response_class=HTMLResponse)
async def database_page(request: Request):
    async with AsyncSessionLocal() as session:
        pred_count = (await session.execute(select(func.count()).select_from(MatchPrediction))).scalar()
        result_count = (await session.execute(select(func.count()).select_from(MatchResult))).scalar()
        pending_count = (await session.execute(
            select(func.count()).select_from(MatchSchedule).where(MatchSchedule.predicted == False)
        )).scalar()
        learned_count = (await session.execute(
            select(func.count()).select_from(MatchPrediction).where(MatchPrediction.was_correct_1x2.isnot(None))
        )).scalar()
        variable_count = (await session.execute(select(func.count()).select_from(ModelWeight))).scalar()
        latest_schedule = (await session.execute(
            select(MatchSchedule).order_by(MatchSchedule.updated_at.desc()).limit(10)
        )).scalars().all()

    return templates.TemplateResponse("database.html", {
        "request": request,
        "active_page": "database",
        "prediction_count": pred_count or 0,
        "result_count": result_count or 0,
        "pending_count": pending_count or 0,
        "learned_count": learned_count or 0,
        "variable_count": variable_count or 0,
        "latest_schedule": latest_schedule,
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
        stored_matches = (await session.execute(select(func.count()).select_from(MatchSchedule))).scalar()
        full_predictions = (await session.execute(select(func.count()).select_from(MatchPrediction))).scalar()
        learning_predictions = (await session.execute(select(func.count()).select_from(LearningPrediction))).scalar()
        correct_predictions = (await session.execute(
            select(func.count()).select_from(MatchPrediction).where(MatchPrediction.was_correct_1x2 == True)
        )).scalar()
        evaluated_predictions = (await session.execute(
            select(func.count()).select_from(MatchPrediction).where(MatchPrediction.was_correct_1x2.isnot(None))
        )).scalar()
        log_count = (await session.execute(select(func.count()).select_from(SystemLog))).scalar()
        weight_count = (await session.execute(select(func.count()).select_from(ModelWeight))).scalar()
        last_error = (await session.execute(
            select(SystemLog).where(SystemLog.level == "ERROR").order_by(SystemLog.created_at.desc()).limit(1)
        )).scalar_one_or_none()

    from app.config import settings
    import os
    db_path = settings.database_url.replace("sqlite+aiosqlite:///", "")
    db_size_mb = round(os.path.getsize(db_path) / (1024 * 1024), 2) if os.path.exists(db_path) else 0.0
    accuracy = round((correct_predictions or 0) / evaluated_predictions * 100, 1) if evaluated_predictions else None
    return templates.TemplateResponse("system_health.html", {
        "request": request,
        "active_page": "system_health",
        "update_status": update_status,
        "scheduler_jobs": jobs,
        "db_stats": {
            "stored_matches": stored_matches or 0,
            "full_predictions": full_predictions or 0,
            "learning_predictions": learning_predictions or 0,
            "accuracy": accuracy,
            "logs": log_count or 0,
            "weights": weight_count or 0,
            "last_error": last_error.message if last_error else "Sin errores registrados",
            "db_size_mb": db_size_mb,
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
    await _disabled_public_module("Panel IA")


@router.get("/config", response_class=HTMLResponse)
async def config_page(request: Request):
    await _disabled_public_module("Configuración")


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
