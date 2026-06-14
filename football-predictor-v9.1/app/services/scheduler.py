"""
Football Predictor V9.0 - Scheduler (Updated)
Manages all background tasks with proper intervals for volatile vs static data.
"""

from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from loguru import logger
from app.config import settings
from app.services.cache import cache


scheduler = AsyncIOScheduler(timezone="UTC")


async def task_fetch_todays_matches():
    """On startup: fetch today matches and detect not-yet-started ones."""
    from app.services.data_updater import data_updater
    logger.info("Scheduler: fetching today matches...")
    try:
        matches = await data_updater.fetch_todays_matches()
        logger.info(f"Scheduler: found {len(matches)} matches for today")
    except Exception as e:
        logger.error(f"Scheduler fetch_todays_matches failed: {e}")


async def task_update_volatile():
    """Every 4 hours: update injuries, odds, suspensions, squads."""
    from app.services.data_updater import data_updater
    logger.info("Scheduler: updating volatile data (injuries/odds/squads)...")
    try:
        result = await data_updater.update_volatile_data()
        logger.info(f"Scheduler: volatile update result: {result}")
    except Exception as e:
        logger.error(f"Scheduler volatile update failed: {e}")


async def task_check_results():
    """Every 2 hours: check if predicted matches have results."""
    from app.services.data_updater import data_updater
    from app.services.learning_engine import learning_engine
    logger.info("Scheduler: checking for match results...")
    try:
        result = await data_updater.check_for_results()
        if result.get("results_found", 0) > 0:
            await learning_engine.update_results_and_learn()
        logger.info(f"Scheduler: result check done — {result}")
    except Exception as e:
        logger.error(f"Scheduler result check failed: {e}")


async def task_snapshot_weights():
    """Daily: save weight snapshot for Learning History."""
    from app.services.learning_engine import learning_engine
    logger.info("Scheduler: taking daily weight snapshot...")
    try:
        await learning_engine.snapshot_weights()
    except Exception as e:
        logger.error(f"Scheduler weight snapshot failed: {e}")


async def task_clear_expired_cache():
    """Every 6 hours: clean expired cache entries."""
    cleared = cache.clear_expired()
    if cleared:
        logger.info(f"Scheduler: cleared {cleared} expired cache entries")


async def task_update_worldcup():
    """Every 6 hours: update World Cup results."""
    logger.info("Scheduler: checking World Cup results...")
    # Placeholder for real WC results fetch from API
    # Would call football-data.org API for WC 2026 fixtures when available


def setup_scheduler():
    """Configure and start the APScheduler."""

    # Fetch today's matches — run at startup and every hour
    scheduler.add_job(
        task_fetch_todays_matches,
        trigger=IntervalTrigger(hours=1),
        id="fetch_todays_matches",
        name="Fetch Today Matches",
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=120,
    )

    # Update volatile data every 4 hours
    scheduler.add_job(
        task_update_volatile,
        trigger=IntervalTrigger(hours=4),
        id="update_volatile",
        name="Update Volatile Data (Lesiones/Cuotas)",
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=300,
    )

    # Check results every 2 hours
    scheduler.add_job(
        task_check_results,
        trigger=IntervalTrigger(hours=2),
        id="check_results",
        name="Comprobar Resultados",
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=120,
    )

    # Daily weight snapshot
    scheduler.add_job(
        task_snapshot_weights,
        trigger=IntervalTrigger(hours=24),
        id="snapshot_weights",
        name="Guardar Snapshot Pesos",
        replace_existing=True,
        max_instances=1,
    )

    # Clean cache every 6 hours
    scheduler.add_job(
        task_clear_expired_cache,
        trigger=IntervalTrigger(hours=6),
        id="clear_cache",
        name="Limpiar Cache Expirada",
        replace_existing=True,
        max_instances=1,
    )

    # Update World Cup data every 6 hours
    scheduler.add_job(
        task_update_worldcup,
        trigger=IntervalTrigger(hours=6),
        id="update_worldcup",
        name="Actualizar Mundial 2026",
        replace_existing=True,
        max_instances=1,
    )

    scheduler.start()
    logger.info("Scheduler started with 6 background tasks")


def get_scheduler_jobs() -> list[dict]:
    jobs = []
    for job in scheduler.get_jobs():
        next_run = job.next_run_time
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run": next_run.strftime("%H:%M:%S") if next_run else "—",
            "next_run_full": next_run.isoformat() if next_run else None,
            "trigger": str(job.trigger),
        })
    return jobs
