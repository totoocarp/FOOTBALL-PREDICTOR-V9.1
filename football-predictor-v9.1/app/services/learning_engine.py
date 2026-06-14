"""
Football Predictor V9.0 - Learning Engine (Fixed)
Auto-predicts all future matches, tracks accuracy, and adjusts variable weights.
FIXES: Learning page button now actually shows data; weight history tracking added.
"""

import asyncio
from datetime import datetime, date
from typing import Optional
from loguru import logger
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models.match import Match, MatchPrediction, MatchResult
from app.models.learning import LearningPrediction, ModelWeight, ModelStatistics, WeightHistory
from app.services.monte_carlo import MonteCarloEngine, TeamInputs, get_engine
from app.config import settings


VARIABLES = ["xg", "elo", "form", "market", "ranking"]

DEFAULT_WEIGHTS = {
    "elo": 1.8,
    "xg": 2.0,
    "form": 1.4,
    "market": 1.6,
    "ranking": 1.2,
    "squad_value": 0.8,
    "availability": 1.3,
    "style": 0.6,
    "fatigue": 0.5,
}


class LearningEngine:
    def __init__(self):
        self.engine = get_engine()

    async def load_weights(self) -> dict:
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(ModelWeight))
            weights_db = result.scalars().all()
            if not weights_db:
                return DEFAULT_WEIGHTS.copy()
            return {w.variable_name: w.weight for w in weights_db}

    async def save_weights(self, weights: dict) -> None:
        async with AsyncSessionLocal() as session:
            for var_name, weight_val in weights.items():
                existing = await session.execute(
                    select(ModelWeight).where(ModelWeight.variable_name == var_name)
                )
                record = existing.scalar_one_or_none()
                if record:
                    record.weight = weight_val
                    record.last_adjusted = datetime.utcnow()
                else:
                    session.add(ModelWeight(variable_name=var_name, weight=weight_val))
            await session.commit()
        logger.info(f"Saved weights: {weights}")

    async def ensure_default_weights(self) -> None:
        """Seed default weights if the DB is empty (first run)."""
        async with AsyncSessionLocal() as session:
            count = (await session.execute(select(func.count()).select_from(ModelWeight))).scalar()
            if count == 0:
                for var_name, weight_val in DEFAULT_WEIGHTS.items():
                    session.add(ModelWeight(
                        variable_name=var_name,
                        weight=weight_val,
                        accuracy=0.0,
                        predictions_count=0,
                        correct_count=0,
                    ))
                await session.commit()
                logger.info("Seeded default model weights")

    async def get_weights_for_display(self) -> list[dict]:
        """Get weights in display format — always returns data even if empty."""
        await self.ensure_default_weights()
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(ModelWeight).order_by(ModelWeight.accuracy.desc())
            )
            weights = result.scalars().all()
            return [
                {
                    "variable_name": w.variable_name,
                    "weight": round(w.weight, 3),
                    "accuracy": round(w.accuracy, 4),
                    "accuracy_pct": round(w.accuracy * 100, 1),
                    "predictions_count": w.predictions_count,
                    "correct_count": w.correct_count,
                    "last_adjusted": w.last_adjusted.strftime("%Y-%m-%d %H:%M") if w.last_adjusted else "—",
                }
                for w in weights
            ]

    async def get_weight_history(self, days: int = 30) -> list[dict]:
        """Get historical weight snapshots for Learning History section."""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(WeightHistory)
                .order_by(WeightHistory.snapshot_date.desc(), WeightHistory.created_at.desc())
                .limit(days * len(VARIABLES))
            )
            history = result.scalars().all()

        # Group by date
        by_date: dict[str, dict] = {}
        for h in history:
            d = h.snapshot_date
            if d not in by_date:
                by_date[d] = {"date": d, "variables": {}}
            by_date[d]["variables"][h.variable_name] = {
                "weight": round(h.weight, 3),
                "accuracy_pct": round(h.accuracy * 100, 1),
                "weight_delta": round(h.weight_delta, 4),
                "accuracy_delta": round(h.accuracy_delta * 100, 2),
                "predictions_count": h.predictions_count,
            }

        return sorted(by_date.values(), key=lambda x: x["date"], reverse=True)

    async def snapshot_weights(self) -> None:
        """Save current weights as a daily snapshot for Learning History."""
        today = date.today().isoformat()
        async with AsyncSessionLocal() as session:
            weights = (await session.execute(select(ModelWeight))).scalars().all()

            for w in weights:
                # Check if already snapshotted today
                existing = (await session.execute(
                    select(WeightHistory)
                    .where(WeightHistory.snapshot_date == today)
                    .where(WeightHistory.variable_name == w.variable_name)
                )).scalar_one_or_none()

                if existing:
                    continue

                # Find yesterday's snapshot
                prev = (await session.execute(
                    select(WeightHistory)
                    .where(WeightHistory.variable_name == w.variable_name)
                    .order_by(WeightHistory.created_at.desc())
                    .limit(1)
                )).scalar_one_or_none()

                weight_delta = w.weight - prev.weight if prev else 0.0
                acc_delta = w.accuracy - prev.accuracy if prev else 0.0

                session.add(WeightHistory(
                    snapshot_date=today,
                    variable_name=w.variable_name,
                    weight=w.weight,
                    accuracy=w.accuracy,
                    predictions_count=w.predictions_count,
                    weight_delta=weight_delta,
                    accuracy_delta=acc_delta,
                ))

            await session.commit()
            logger.info(f"Weight snapshot saved for {today}")

    async def predict_upcoming_matches(self, matches: list[dict]) -> int:
        weights = await self.load_weights()
        engine = get_engine(weights=weights)
        count = 0

        for match_data in matches:
            try:
                home_inputs = self._build_team_inputs(match_data.get("home_stats", {}), is_home=True)
                away_inputs = self._build_team_inputs(match_data.get("away_stats", {}), is_home=False)
                result = engine.simulate(home_inputs, away_inputs, include_variable_preds=True)

                async with AsyncSessionLocal() as session:
                    pred = MatchPrediction(
                        match_id=match_data["match_id"],
                        model_version="9.0.0",
                        prediction_type="full_model",
                        home_win_prob=result.home_win_prob,
                        draw_prob=result.draw_prob,
                        away_win_prob=result.away_win_prob,
                        home_goals_expected=result.home_goals_expected,
                        away_goals_expected=result.away_goals_expected,
                        most_likely_score=result.most_likely_score,
                        btts_prob=result.btts_prob,
                        over_25_prob=result.over_25_prob,
                        over_35_prob=result.over_35_prob,
                        score_distribution=result.score_distribution,
                        confidence_score=result.confidence_score,
                        simulations_run=result.simulations_run,
                    )
                    session.add(pred)

                    for var_name, var_result in result.variable_predictions.items():
                        lp = LearningPrediction(
                            match_id=match_data["match_id"],
                            variable_name=var_name,
                            home_win_prob=var_result["home_win_prob"],
                            draw_prob=var_result["draw_prob"],
                            away_win_prob=var_result["away_win_prob"],
                            home_goals_expected=var_result["home_goals_exp"],
                            away_goals_expected=var_result["away_goals_exp"],
                        )
                        session.add(lp)

                    await session.commit()
                count += 1
            except Exception as e:
                logger.error(f"Failed to predict match {match_data.get('match_id')}: {e}")

        logger.info(f"Auto-predicted {count} matches")
        return count

    async def update_results_and_learn(self) -> dict:
        """Compare predictions vs real results, update weights and stats."""
        await self.ensure_default_weights()
        updated = 0

        async with AsyncSessionLocal() as session:
            stmt = (
                select(MatchPrediction)
                .join(Match, MatchPrediction.match_id == Match.id)
                .join(MatchResult, Match.id == MatchResult.match_id)
                .where(MatchPrediction.was_correct_1x2.is_(None))
                .where(MatchPrediction.prediction_type == "full_model")
                .limit(100)
            )
            preds = (await session.execute(stmt)).scalars().all()

            for pred in preds:
                match = await session.get(Match, pred.match_id)
                if not match or not match.result:
                    continue
                real = match.result

                predicted_outcome = self._predicted_outcome(pred)
                actual_outcome = real.winner
                pred.was_correct_1x2 = predicted_outcome == actual_outcome
                pred.was_correct_score = (
                    real.home_score == round(pred.home_goals_expected) and
                    real.away_score == round(pred.away_goals_expected)
                )
                actual_btts = real.home_score > 0 and real.away_score > 0
                pred.was_correct_btts = actual_btts == (pred.btts_prob > 0.5)
                actual_total = real.home_score + real.away_score
                pred.was_correct_ou25 = (actual_total > 2) == (pred.over_25_prob > 0.5)
                updated += 1

            await session.commit()

        if updated > 0:
            await self._recalculate_weights()
            await self._update_statistics()
            await self.snapshot_weights()
            logger.info(f"Learning: updated {updated} predictions with real results")

        return {
            "predictions_updated": updated,
            "message": f"Actualizadas {updated} predicciones con resultados reales" if updated else "No hay nuevos resultados que evaluar",
        }

    def _predicted_outcome(self, pred: MatchPrediction) -> str:
        probs = {"HOME": pred.home_win_prob, "DRAW": pred.draw_prob, "AWAY": pred.away_win_prob}
        return max(probs, key=probs.get)

    async def _recalculate_weights(self) -> None:
        async with AsyncSessionLocal() as session:
            stmt = select(LearningPrediction).where(LearningPrediction.was_correct.isnot(None))
            all_lp = (await session.execute(stmt)).scalars().all()
            if not all_lp:
                return

            weights = DEFAULT_WEIGHTS.copy()
            var_stats: dict[str, dict] = {}

            for lp in all_lp:
                v = lp.variable_name
                if v not in var_stats:
                    var_stats[v] = {"correct": 0, "total": 0}
                var_stats[v]["total"] += 1
                if lp.was_correct:
                    var_stats[v]["correct"] += 1

            for var, stats in var_stats.items():
                if stats["total"] < 10:
                    continue
                accuracy = stats["correct"] / stats["total"]
                raw_weight = 0.3 + (accuracy * 2.7)
                weights[var] = round(max(0.3, min(3.0, raw_weight)), 3)

                existing = await session.execute(
                    select(ModelWeight).where(ModelWeight.variable_name == var)
                )
                record = existing.scalar_one_or_none()
                if record:
                    record.weight = weights[var]
                    record.accuracy = round(accuracy, 4)
                    record.predictions_count = stats["total"]
                    record.correct_count = stats["correct"]
                    record.last_adjusted = datetime.utcnow()
                else:
                    session.add(ModelWeight(
                        variable_name=var,
                        weight=weights[var],
                        accuracy=round(accuracy, 4),
                        predictions_count=stats["total"],
                        correct_count=stats["correct"],
                    ))

            await session.commit()
            logger.info(f"Recalculated weights: {weights}")

    async def _update_statistics(self) -> None:
        async with AsyncSessionLocal() as session:
            stmt = select(MatchPrediction).where(MatchPrediction.was_correct_1x2.isnot(None))
            all_preds = (await session.execute(stmt)).scalars().all()
            if not all_preds:
                return

            total = len(all_preds)
            correct_1x2 = sum(1 for p in all_preds if p.was_correct_1x2)
            correct_score = sum(1 for p in all_preds if p.was_correct_score)
            correct_btts = sum(1 for p in all_preds if p.was_correct_btts)
            correct_ou25 = sum(1 for p in all_preds if p.was_correct_ou25)

            stats_to_save = {
                "accuracy_1x2": (round(correct_1x2 / total * 100, 2), "Accuracy 1X2 (%)", "general"),
                "accuracy_exact_score": (round(correct_score / total * 100, 2), "Exact Score Accuracy (%)", "general"),
                "accuracy_btts": (round(correct_btts / total * 100, 2), "BTTS Accuracy (%)", "general"),
                "accuracy_ou25": (round(correct_ou25 / total * 100, 2), "Over/Under 2.5 Accuracy (%)", "general"),
                "total_predictions": (total, "Total Predictions", "general"),
                "correct_1x2": (correct_1x2, "Correct 1X2 Predictions", "general"),
            }

            for stat_key, (stat_value, stat_label, category) in stats_to_save.items():
                existing = await session.execute(
                    select(ModelStatistics).where(ModelStatistics.stat_key == stat_key)
                )
                record = existing.scalar_one_or_none()
                if record:
                    record.stat_value = stat_value
                    record.updated_at = datetime.utcnow()
                else:
                    session.add(ModelStatistics(
                        stat_key=stat_key,
                        stat_value=stat_value,
                        stat_label=stat_label,
                        category=category,
                    ))

            await session.commit()

    def _build_team_inputs(self, stats: dict, is_home: bool = True) -> TeamInputs:
        return TeamInputs(
            elo_global=stats.get("elo_global", 1500.0),
            elo_12months=stats.get("elo_12months", 1500.0),
            xg_avg=stats.get("xg_avg", 1.2),
            xga_avg=stats.get("xga_avg", 1.2),
            goals_per_game=stats.get("goals_per_game", 1.2),
            goals_conceded=stats.get("goals_conceded_per_game", 1.2),
            points_per_game=stats.get("points_per_game", 1.2),
            form_5=stats.get("form_5", 0.5),
            form_10=stats.get("form_10", 0.5),
            squad_value=stats.get("squad_value_total", 100.0),
            availability=max(0.5, 1.0 - stats.get("injuries_key", 0) * 0.05),
            odds_prob=stats.get("odds_home_prob", 0.45),
            possession=stats.get("possession_avg", 50.0),
            shots_on_target=stats.get("shots_on_target_avg", 4.0),
            clean_sheet_rate=stats.get("clean_sheet_rate", 0.30),
            fatigue_factor=max(0.7, 1.0 - stats.get("games_last_30", 4) * 0.02),
            ranking_percentile=stats.get("ranking_percentile", 0.5),
            is_home=is_home,
        )


learning_engine = LearningEngine()
