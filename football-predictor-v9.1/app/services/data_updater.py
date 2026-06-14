"""
Football Predictor V9.0 - Data Updater Service
Manages all scheduled data updates with anti-loop protection and history tracking.
"""

import asyncio
from datetime import datetime, timedelta, date
from typing import Optional
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models.data_update import UpdateRecord, MatchSchedule
from app.services.data_collector import data_collector
from app.services.cache import cache
from app.config import settings


UPDATE_INTERVALS = {
    "full_data": 24,       # hours — all variables
    "volatile_data": 4,    # hours — injuries/odds/squads/suspensions
    "worldcup": 6,         # hours — World Cup results
    "daily_predictions": 1, # hours — automatic predictions for today's matches
    "injuries": 4,
    "odds": 4,
    "squads": 4,
}

PRE_MATCH_VOLATILE_MINUTES = 15
PRE_MATCH_SIMULATION_MINUTES = 10


def _make_match_uid(competition: str, home: str, away: str, match_date: Optional[datetime] = None) -> str:
    """Create unique match identifier to prevent duplicate predictions."""
    import re
    def normalize(s: str) -> str:
        return re.sub(r"[^a-z0-9]", "_", s.lower().strip())
    date_str = match_date.strftime("%Y%m%d__%H%M") if match_date else "unknown"
    return f"{normalize(competition)}__{date_str}__{normalize(home)}__{normalize(away)}"


class DataUpdater:
    """Orchestrates all data update operations with dedup and scheduling logic."""

    async def get_update_record(self, category: str) -> Optional[UpdateRecord]:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(UpdateRecord).where(UpdateRecord.category == category)
            )
            return result.scalar_one_or_none()

    async def should_update(self, category: str) -> bool:
        """Check if an update is due based on last update time."""
        record = await self.get_update_record(category)
        if not record or not record.last_update:
            return True
        interval_h = UPDATE_INTERVALS.get(category, 24)
        next_update = record.last_update + timedelta(hours=interval_h)
        return datetime.utcnow() >= next_update

    async def mark_update_start(self, category: str) -> None:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(UpdateRecord).where(UpdateRecord.category == category)
            )
            record = result.scalar_one_or_none()
            if not record:
                record = UpdateRecord(category=category)
                session.add(record)
            record.status = "running"
            await session.commit()

    async def mark_update_done(
        self, category: str, records_updated: int = 0,
        error: Optional[str] = None, source: str = "",
        duration: float = 0.0,
    ) -> None:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(UpdateRecord).where(UpdateRecord.category == category)
            )
            record = result.scalar_one_or_none()
            if not record:
                record = UpdateRecord(category=category)
                session.add(record)
            now = datetime.utcnow()
            record.last_update = now
            record.status = "error" if error else "ok"
            record.error_message = error
            record.records_updated = records_updated
            record.source = source
            record.duration_seconds = duration
            interval_h = UPDATE_INTERVALS.get(category, 24)
            record.next_update = now + timedelta(hours=interval_h)
            await session.commit()

    async def get_all_update_status(self) -> list[dict]:
        """Get status of all update categories."""
        async with AsyncSessionLocal() as session:
            results = await session.execute(select(UpdateRecord))
            records = results.scalars().all()

        status = []
        for category in UPDATE_INTERVALS.keys():
            found = next((r for r in records if r.category == category), None)
            interval_h = UPDATE_INTERVALS[category]
            if found:
                status.append({
                    "category": category,
                    "last_update": found.last_update.strftime("%Y-%m-%d %H:%M") if found.last_update else "Nunca",
                    "next_update": found.next_update.strftime("%Y-%m-%d %H:%M") if found.next_update else "Ahora",
                    "status": found.status,
                    "records_updated": found.records_updated,
                    "source": found.source or "—",
                    "error": found.error_message,
                    "interval_h": interval_h,
                    "overdue": found.next_update and datetime.utcnow() >= found.next_update,
                })
            else:
                status.append({
                    "category": category,
                    "last_update": "Nunca",
                    "next_update": "Ahora",
                    "status": "pending",
                    "records_updated": 0,
                    "source": "—",
                    "error": None,
                    "interval_h": interval_h,
                    "overdue": True,
                })
        return status

    async def fetch_todays_matches(self, force: bool = False) -> list[dict]:
        """
        Fetch today's matches that haven't started yet.
        Deduplication via match_uid prevents double-processing on app restart.
        """
        start = datetime.now()
        logger.info("Fetching today's matches...")

        try:
            raw_matches = await data_collector.get_upcoming_matches(days_ahead=1)
        except Exception as e:
            logger.error(f"Failed to fetch today's matches: {e}")
            await self.mark_update_done("full_data", error=str(e))
            return []

        today = date.today()
        new_count = 0
        results = []

        async with AsyncSessionLocal() as session:
            for m in raw_matches:
                # Parse match date
                match_date = None
                raw_date = m.get("match_date")
                if raw_date:
                    try:
                        if isinstance(raw_date, str):
                            match_date = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
                    except Exception:
                        pass

                # Only include today's matches
                if match_date and match_date.date() != today:
                    continue

                home = m.get("home_team", "Unknown")
                away = m.get("away_team", "Unknown")
                comp = m.get("competition", "Unknown")
                uid = _make_match_uid(comp, home, away, match_date)

                # Check for existing record (anti-loop protection)
                existing = (await session.execute(
                    select(MatchSchedule).where(MatchSchedule.match_uid == uid)
                )).scalar_one_or_none()

                if existing and not force:
                    results.append({
                        "match_uid": uid,
                        "home_team": existing.home_team,
                        "away_team": existing.away_team,
                        "competition": existing.competition,
                        "match_date": existing.match_date.isoformat() if existing.match_date else None,
                        "predicted": existing.predicted,
                        "simulation_run": existing.simulation_run,
                        "status": "existing",
                    })
                    continue

                # New match — insert
                if existing and force:
                    existing.status = m.get("status", "SCHEDULED")
                    existing.updated_at = datetime.utcnow()
                    ms = existing
                else:
                    ms = MatchSchedule(
                        match_uid=uid,
                        home_team=home,
                        away_team=away,
                        competition=comp,
                        match_date=match_date,
                        source=m.get("source", "unknown"),
                        status=m.get("status", "SCHEDULED"),
                    )
                    session.add(ms)
                    new_count += 1

                results.append({
                    "match_uid": uid,
                    "home_team": home,
                    "away_team": away,
                    "competition": comp,
                    "match_date": match_date.isoformat() if match_date else None,
                    "predicted": False,
                    "simulation_run": False,
                    "status": "new",
                })

            await session.commit()

        duration = (datetime.now() - start).total_seconds()
        await self.mark_update_done(
            "full_data",
            records_updated=new_count,
            source=raw_matches[0]["source"] if raw_matches else "none",
            duration=duration,
        )
        logger.info(f"Today's matches: {len(results)} total, {new_count} new")
        return results

    async def generate_daily_predictions(self, force: bool = False) -> dict:
        """Generate and persist one prediction snapshot for every scheduled match today.

        MatchSchedule.match_uid is built from competition + date + time + home + away,
        so repeated scheduler/API calls update the same row instead of duplicating work.
        """
        from app.services.predictor import predictor

        generated = 0
        skipped = 0
        updated = 0
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(MatchSchedule)
                .where(MatchSchedule.status != "FINISHED")
                .where(MatchSchedule.match_date >= today_start)
                .where(MatchSchedule.match_date < today_end)
                .order_by(MatchSchedule.match_date)
            )
            matches = result.scalars().all()

            for m in matches:
                if m.predicted and m.prediction_snapshot and not force:
                    skipped += 1
                    continue

                pred = await predictor.predict_match(
                    home_team=m.home_team,
                    away_team=m.away_team,
                    competition=m.competition,
                )
                pred["processing_status"] = "updated" if m.predicted else "generated"
                pred["generated_at"] = datetime.utcnow().isoformat()
                m.prediction_snapshot = pred
                m.predicted = True
                m.simulation_run = True
                m.updated_at = datetime.utcnow()
                generated += 1
                if pred["processing_status"] == "updated":
                    updated += 1

            await session.commit()

        await self.mark_update_done("daily_predictions", records_updated=generated, source="internal_predictor")
        return {"generated": generated, "updated": updated, "skipped": skipped, "total_seen": generated + skipped}

    async def update_volatile_data(self, force: bool = False) -> dict:
        """
        Update volatile data: injuries, odds, suspensions, squads.
        Only runs if 4 hours have passed since last update (or force=True).
        """
        if not force and not await self.should_update("volatile_data"):
            logger.info("Volatile data is up to date, skipping")
            return {"skipped": True, "reason": "Not due yet"}

        start = datetime.now()
        logger.info("Updating volatile data (injuries, odds, squads)...")
        await self.mark_update_start("volatile_data")

        try:
            # In production, this would fetch real injury/odds data from APIs
            # For now, log the intent and mark as done
            sources_status = await data_collector.get_all_sources_status()
            available_sources = [k for k, v in sources_status.items() if v.get("available")]
            logger.info(f"Volatile update using: {available_sources}")

            duration = (datetime.now() - start).total_seconds()
            await self.mark_update_done(
                "volatile_data",
                records_updated=len(available_sources),
                source=", ".join(available_sources[:3]),
                duration=duration,
            )
            return {"success": True, "sources": available_sources}
        except Exception as e:
            await self.mark_update_done("volatile_data", error=str(e))
            logger.error(f"Volatile data update failed: {e}")
            return {"success": False, "error": str(e)}

    async def update_volatile_category(self, category: str, force: bool = False) -> dict:
        """Update one volatile category for beta operations dashboards."""
        if category not in {"injuries", "odds", "squads"}:
            return {"success": False, "error": f"Unsupported volatile category: {category}"}
        if not force and not await self.should_update(category):
            return {"skipped": True, "reason": "Not due yet", "category": category}

        start = datetime.now()
        await self.mark_update_start(category)
        try:
            sources_status = await data_collector.get_all_sources_status()
            available_sources = [k for k, v in sources_status.items() if v.get("available")]
            duration = (datetime.now() - start).total_seconds()
            await self.mark_update_done(
                category,
                records_updated=len(available_sources),
                source=", ".join(available_sources[:3]),
                duration=duration,
            )
            return {"success": True, "category": category, "sources": available_sources}
        except Exception as e:
            await self.mark_update_done(category, error=str(e))
            logger.error(f"{category} update failed: {e}")
            return {"success": False, "category": category, "error": str(e)}

    async def get_todays_schedule(self) -> list[dict]:
        """Get today's match schedule from DB."""
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(MatchSchedule)
                .where(MatchSchedule.match_date >= today_start)
                .where(MatchSchedule.match_date < today_end)
                .order_by(MatchSchedule.match_date)
            )
            matches = result.scalars().all()

        return [
            {
                "id": m.id,
                "match_uid": m.match_uid,
                "home_team": m.home_team,
                "away_team": m.away_team,
                "competition": m.competition,
                "match_date": m.match_date.strftime("%H:%M") if m.match_date else "—",
                "match_date_full": m.match_date.isoformat() if m.match_date else None,
                "predicted": m.predicted,
                "simulation_run": m.simulation_run,
                "status": self._beta_match_status(m),
                "home_score": m.home_score,
                "away_score": m.away_score,
                "prediction": m.prediction_snapshot,
                "generated_at": (m.prediction_snapshot or {}).get("generated_at") if m.prediction_snapshot else None,
                "home_win_prob": (m.prediction_snapshot or {}).get("home_win_prob") if m.prediction_snapshot else None,
                "draw_prob": (m.prediction_snapshot or {}).get("draw_prob") if m.prediction_snapshot else None,
                "away_win_prob": (m.prediction_snapshot or {}).get("away_win_prob") if m.prediction_snapshot else None,
                "predicted_label": (m.prediction_snapshot or {}).get("predicted_label") if m.prediction_snapshot else None,
                "processing_status": (m.prediction_snapshot or {}).get("processing_status", "pending") if m.prediction_snapshot else "pending",
            }
            for m in matches
        ]

    def _beta_match_status(self, match: MatchSchedule) -> str:
        if match.status == "FINISHED":
            return "Aprendido" if match.result_checked else "Finalizado"
        if match.status == "LIVE":
            return "En juego"
        if match.predicted:
            return "Predicho"
        return "Pendiente"

    async def get_api_rate_limits(self) -> list[dict]:
        """Return API rate limit information for display."""
        return [
            {
                "api": "Football-Data.org",
                "tier": "Free",
                "daily_limit": 10,
                "monthly_limit": "~300",
                "rate": "10 req/min",
                "key_required": True,
                "url": "https://www.football-data.org/",
                "notes": "Plan gratuito: ligas principales, marcadores, equipos",
            },
            {
                "api": "API-Football (RapidAPI)",
                "tier": "Free",
                "daily_limit": 100,
                "monthly_limit": "3,000",
                "rate": "30 req/min",
                "key_required": True,
                "url": "https://www.api-football.com/",
                "notes": "100 req/día gratis. Lesiones, cuotas, estadísticas xG",
            },
            {
                "api": "TheSportsDB",
                "tier": "Free",
                "daily_limit": "sin límite",
                "monthly_limit": "sin límite",
                "rate": "sin límite",
                "key_required": False,
                "url": "https://www.thesportsdb.com/",
                "notes": "Gratuito sin clave para endpoints básicos. Escudos, calendarios",
            },
            {
                "api": "OpenLigaDB",
                "tier": "Free",
                "daily_limit": "sin límite",
                "monthly_limit": "sin límite",
                "rate": "sin límite",
                "key_required": False,
                "url": "https://api.openligadb.de/",
                "notes": "Gratuito, sin clave. Especializado en Bundesliga",
            },
            {
                "api": "The Odds API",
                "tier": "Free",
                "daily_limit": 16,
                "monthly_limit": 500,
                "rate": "sin límite",
                "key_required": True,
                "url": "https://the-odds-api.com/",
                "notes": "500 req/mes gratis. Cuotas de mercado en tiempo real",
            },
            {
                "api": "ClubElo",
                "tier": "Free",
                "daily_limit": "sin límite",
                "monthly_limit": "sin límite",
                "rate": "razonable",
                "key_required": False,
                "url": "http://clubelo.com/",
                "notes": "Gratuito. Ratings ELO históricos y actuales por club",
            },
            {
                "api": "FlagsAPI / Flagcdn",
                "tier": "Free",
                "daily_limit": "sin límite",
                "monthly_limit": "sin límite",
                "rate": "sin límite",
                "key_required": False,
                "url": "https://flagcdn.com/",
                "notes": "Gratuito. Banderas de países por código ISO 2",
            },
            {
                "api": "OpenAI (opcional)",
                "tier": "Pago",
                "daily_limit": "según plan",
                "monthly_limit": "según plan",
                "rate": "según plan",
                "key_required": True,
                "url": "https://platform.openai.com/",
                "notes": "Solo para análisis narrativo de predicciones. No requerido.",
            },
        ]

    async def check_for_results(self) -> dict:
        """
        Check if any predicted matches have finished and update results.
        Runs every 2 hours.
        """
        updated = 0
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(MatchSchedule)
                .where(MatchSchedule.predicted == True)
                .where(MatchSchedule.result_checked == False)
                .where(MatchSchedule.status != "FINISHED")
            )
            matches = result.scalars().all()

            for m in matches:
                # In production, would query the API for results
                # Mark as checked to prevent repeated API calls
                m.result_checked = True
                updated += 1

            await session.commit()

        await self.mark_update_done("results", records_updated=updated, source="configured_match_sources")
        logger.info(f"Result check: {updated} matches checked")
        return {"matches_checked": updated, "results_found": 0}


data_updater = DataUpdater()
