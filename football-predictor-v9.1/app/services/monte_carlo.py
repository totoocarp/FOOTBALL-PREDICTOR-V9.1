"""
Football Predictor V9.0 - Monte Carlo Simulation Engine
20,000 simulations per match using Poisson distribution.
Uses GLOBAL scaling (z-score, percentile) to avoid intra-match normalization explosions.
"""

import numpy as np
from typing import Optional
from dataclasses import dataclass, field
from collections import defaultdict
from loguru import logger
from app.config import settings


@dataclass
class TeamInputs:
    """Normalized inputs for one team."""
    # ELO
    elo_global: float = 1500.0
    elo_12months: float = 1500.0

    # xG
    xg_avg: float = 1.2
    xga_avg: float = 1.2

    # Goals
    goals_per_game: float = 1.2
    goals_conceded: float = 1.2
    points_per_game: float = 1.2

    # Form (0-1)
    form_5: float = 0.5
    form_10: float = 0.5

    # Squad value (millions)
    squad_value: float = 100.0

    # Availability (injured/suspended key players)
    availability: float = 1.0  # 1.0 = full squad, lower = missing players

    # Odds (implied probability)
    odds_prob: float = 0.45

    # Style
    possession: float = 50.0
    shots_on_target: float = 4.0
    clean_sheet_rate: float = 0.30

    # Fatigue (games last 30 days)
    fatigue_factor: float = 1.0  # 1.0 = normal

    # National team specific
    ranking_percentile: float = 0.5  # 0=best, 1=worst

    is_home: bool = True


@dataclass
class SimulationResult:
    """Result of a Monte Carlo simulation run."""
    home_win_prob: float
    draw_prob: float
    away_win_prob: float

    home_goals_expected: float
    away_goals_expected: float

    most_likely_score: str
    score_distribution: dict

    btts_prob: float
    over_15_prob: float
    over_25_prob: float
    over_35_prob: float
    over_45_prob: float
    under_25_prob: float

    home_cs_prob: float
    away_cs_prob: float

    penalties_prob: float = 0.0
    extra_time_prob: float = 0.0

    confidence_score: float = 0.5
    simulations_run: int = 20000

    variable_predictions: dict = field(default_factory=dict)


class MonteCarloEngine:
    """
    Core Monte Carlo simulation engine.
    Uses Poisson distribution for goal scoring.
    Weights combined from multiple variables.
    """

    # Default weights for each variable (auto-adjusted by learning engine)
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

    # Global reference stats for Z-score normalization
    GLOBAL_ELO_MEAN = 1500.0
    GLOBAL_ELO_STD = 200.0
    GLOBAL_XG_MEAN = 1.35
    GLOBAL_XG_STD = 0.45

    def __init__(self, n_simulations: Optional[int] = None, weights: Optional[dict] = None):
        self.n_simulations = n_simulations or settings.monte_carlo_simulations
        self.weights = {**self.DEFAULT_WEIGHTS, **(weights or {})}
        np.random.seed(None)  # fresh seed each run

    def _normalize_zscore(self, value: float, mean: float, std: float) -> float:
        """Global Z-score normalization."""
        if std == 0:
            return 0.0
        return (value - mean) / std

    def _compute_lambda(self, team: TeamInputs, opponent: TeamInputs) -> float:
        """
        Compute Poisson lambda (expected goals) for team scoring against opponent.
        Uses GLOBAL z-score normalization to avoid intra-match explosions.
        """
        w = self.weights

        # --- ELO component ---
        elo_z = self._normalize_zscore(
            team.elo_global, self.GLOBAL_ELO_MEAN, self.GLOBAL_ELO_STD
        )
        elo_contrib = elo_z * 0.15 * w["elo"]

        # --- xG component ---
        xg_attack = team.xg_avg
        xg_defense = opponent.xga_avg
        xg_combined = (xg_attack + xg_defense) / 2.0
        xg_z = self._normalize_zscore(xg_combined, self.GLOBAL_XG_MEAN, self.GLOBAL_XG_STD)
        xg_contrib = xg_z * 0.20 * w["xg"]

        # --- Form component ---
        form = (team.form_5 * 0.6 + team.form_10 * 0.4) - 0.5
        form_contrib = form * 0.15 * w["form"]

        # --- Market (odds) component ---
        market_edge = team.odds_prob - 0.5
        market_contrib = market_edge * 0.12 * w["market"]

        # --- Ranking component (0=best, 1=worst) ---
        ranking_edge = (opponent.ranking_percentile - team.ranking_percentile)
        ranking_contrib = ranking_edge * 0.18 * w["ranking"]

        # --- Squad-value component (log scaled so rich clubs matter without exploding) ---
        team_value = max(team.squad_value, 1.0)
        opp_value = max(opponent.squad_value, 1.0)
        value_edge = float(np.clip(np.log(team_value / opp_value), -3.0, 3.0))
        squad_contrib = value_edge * 0.10 * w["squad_value"]

        # --- Style component ---
        shot_edge = (team.shots_on_target - opponent.shots_on_target) / 8.0
        possession_edge = (team.possession - opponent.possession) / 100.0
        clean_sheet_penalty = (opponent.clean_sheet_rate - 0.30)
        style_contrib = (shot_edge * 0.12 + possession_edge * 0.05 - clean_sheet_penalty * 0.10) * w["style"]

        # --- Availability penalty ---
        avail_contrib = (team.availability - 1.0) * 0.12 * w["availability"]

        # --- Fatigue penalty ---
        fatigue_contrib = (team.fatigue_factor - 1.0) * 0.08 * w["fatigue"]

        # --- Home advantage ---
        home_bonus = 0.15 if team.is_home else 0.0

        # --- Base lambda ---
        # Use goals per game as a prior, weighted with xg
        base = team.goals_per_game * 0.4 + team.xg_avg * 0.6

        # Total adjustment (additive on base)
        adjustment = (
            elo_contrib + xg_contrib + form_contrib +
            market_contrib + ranking_contrib + squad_contrib + style_contrib +
            avail_contrib + fatigue_contrib + home_bonus
        )

        lam = base + adjustment

        # Clamp to [0.1, 5.0] to prevent Poisson explosion
        return float(np.clip(lam, 0.1, 5.0))

    def simulate(
        self,
        home: TeamInputs,
        away: TeamInputs,
        include_variable_preds: bool = True,
    ) -> SimulationResult:
        """Run full Monte Carlo simulation."""
        home.is_home = True
        away.is_home = False

        lambda_home = self._compute_lambda(home, away)
        lambda_away = self._compute_lambda(away, home)

        # --- Run simulations ---
        rng = np.random.default_rng()
        home_goals_sims = rng.poisson(lambda_home, self.n_simulations).astype(np.int32)
        away_goals_sims = rng.poisson(lambda_away, self.n_simulations).astype(np.int32)

        # --- Outcome probabilities ---
        home_wins = int(np.sum(home_goals_sims > away_goals_sims))
        draws = int(np.sum(home_goals_sims == away_goals_sims))
        away_wins = int(np.sum(home_goals_sims < away_goals_sims))
        n = self.n_simulations

        home_win_prob = round(home_wins / n, 4)
        draw_prob = round(draws / n, 4)
        away_win_prob = round(away_wins / n, 4)

        # --- Goals stats ---
        home_goals_exp = round(float(np.mean(home_goals_sims)), 3)
        away_goals_exp = round(float(np.mean(away_goals_sims)), 3)

        # --- Score distribution (top 20) ---
        score_counter: dict[str, int] = defaultdict(int)
        for hg, ag in zip(home_goals_sims, away_goals_sims):
            if hg <= 7 and ag <= 7:
                score_counter[f"{hg}-{ag}"] += 1
        score_dist = {
            k: round(v / n, 4)
            for k, v in sorted(score_counter.items(), key=lambda x: -x[1])[:25]
        }
        most_likely_score = max(score_dist, key=score_dist.get) if score_dist else "1-1"

        # --- Markets ---
        total_goals = home_goals_sims + away_goals_sims
        btts_sims = (home_goals_sims > 0) & (away_goals_sims > 0)

        btts_prob = round(float(np.mean(btts_sims)), 4)
        over_15 = round(float(np.mean(total_goals > 1)), 4)
        over_25 = round(float(np.mean(total_goals > 2)), 4)
        over_35 = round(float(np.mean(total_goals > 3)), 4)
        over_45 = round(float(np.mean(total_goals > 4)), 4)
        under_25 = round(1.0 - over_25, 4)
        home_cs = round(float(np.mean(away_goals_sims == 0)), 4)
        away_cs = round(float(np.mean(home_goals_sims == 0)), 4)

        # --- Confidence score ---
        max_prob = max(home_win_prob, draw_prob, away_win_prob)
        confidence = round(max_prob * 0.7 + min(home.odds_prob, away.odds_prob) * 0.3, 4)

        # --- Variable predictions (for learning engine) ---
        variable_preds = {}
        if include_variable_preds:
            variable_preds = self._compute_variable_predictions(home, away)

        return SimulationResult(
            home_win_prob=home_win_prob,
            draw_prob=draw_prob,
            away_win_prob=away_win_prob,
            home_goals_expected=home_goals_exp,
            away_goals_expected=away_goals_exp,
            most_likely_score=most_likely_score,
            score_distribution=score_dist,
            btts_prob=btts_prob,
            over_15_prob=over_15,
            over_25_prob=over_25,
            over_35_prob=over_35,
            over_45_prob=over_45,
            under_25_prob=under_25,
            home_cs_prob=home_cs,
            away_cs_prob=away_cs,
            confidence_score=confidence,
            simulations_run=self.n_simulations,
            variable_predictions=variable_preds,
        )

    def _compute_variable_predictions(
        self, home: TeamInputs, away: TeamInputs
    ) -> dict:
        """Compute isolated single-variable predictions for the learning engine."""
        results = {}
        rng = np.random.default_rng()
        n_mini = min(5000, self.n_simulations // 4)

        for variable in ["elo", "xg", "form", "market", "ranking"]:
            lh, la = self._single_variable_lambdas(home, away, variable)
            hg = rng.poisson(lh, n_mini)
            ag = rng.poisson(la, n_mini)
            results[variable] = {
                "home_win_prob": round(float(np.mean(hg > ag)), 4),
                "draw_prob": round(float(np.mean(hg == ag)), 4),
                "away_win_prob": round(float(np.mean(hg < ag)), 4),
                "home_goals_exp": round(float(np.mean(hg)), 3),
                "away_goals_exp": round(float(np.mean(ag)), 3),
            }
        return results

    def _single_variable_lambdas(
        self, home: TeamInputs, away: TeamInputs, variable: str
    ) -> tuple[float, float]:
        """Compute lambda using ONLY one variable (for learning engine)."""
        base_home = home.goals_per_game
        base_away = away.goals_per_game
        home_bonus = 0.15

        if variable == "elo":
            diff = (home.elo_global - away.elo_global) / 400.0
            lh = max(0.1, base_home + diff * 0.3 + home_bonus)
            la = max(0.1, base_away - diff * 0.3)
        elif variable == "xg":
            xg_h = (home.xg_avg + away.xga_avg) / 2.0
            xg_a = (away.xg_avg + home.xga_avg) / 2.0
            lh = max(0.1, xg_h + home_bonus * 0.5)
            la = max(0.1, xg_a)
        elif variable == "form":
            diff = (home.form_5 - away.form_5) * 0.5
            lh = max(0.1, base_home + diff + home_bonus)
            la = max(0.1, base_away - diff)
        elif variable == "market":
            diff = (home.odds_prob - away.odds_prob) * 0.5
            lh = max(0.1, base_home + diff + home_bonus)
            la = max(0.1, base_away - diff)
        elif variable == "ranking":
            # ranking_percentile: 0=best, 1=worst
            diff = (away.ranking_percentile - home.ranking_percentile) * 0.4
            lh = max(0.1, base_home + diff + home_bonus)
            la = max(0.1, base_away - diff)
        else:
            lh = max(0.1, base_home + home_bonus)
            la = max(0.1, base_away)

        return float(np.clip(lh, 0.1, 5.0)), float(np.clip(la, 0.1, 5.0))

    def simulate_knockout(
        self,
        home: TeamInputs,
        away: TeamInputs,
    ) -> dict:
        """
        Simulate a knockout match (including extra time + penalties if draw).
        Returns winner, scores, went_to_penalties.
        """
        result = self.simulate(home, away, include_variable_preds=False)
        rng = np.random.default_rng()

        lh = self._compute_lambda(home, away)
        la = self._compute_lambda(away, home)
        hg = int(rng.poisson(lh))
        ag = int(rng.poisson(la))

        went_to_extra = False
        went_to_penalties = False
        winner = None

        if hg == ag:
            went_to_extra = True
            # Extra time: reduced scoring (30 min = ~25% of 90 min)
            et_lh = lh * 0.25
            et_la = la * 0.25
            et_hg = int(rng.poisson(et_lh))
            et_ag = int(rng.poisson(et_la))
            hg += et_hg
            ag += et_ag

            if hg == ag:
                went_to_penalties = True
                pen_home = rng.binomial(5, 0.75)
                pen_away = rng.binomial(5, 0.75)
                while pen_home == pen_away:
                    pen_home += int(rng.binomial(1, 0.75))
                    pen_away += int(rng.binomial(1, 0.75))
                winner = "home" if pen_home > pen_away else "away"
            else:
                winner = "home" if hg > ag else "away"
        else:
            winner = "home" if hg > ag else "away"

        return {
            "home_goals": hg,
            "away_goals": ag,
            "winner": winner,
            "went_to_extra": went_to_extra,
            "went_to_penalties": went_to_penalties,
        }


def get_engine(weights: Optional[dict] = None) -> MonteCarloEngine:
    return MonteCarloEngine(weights=weights)
