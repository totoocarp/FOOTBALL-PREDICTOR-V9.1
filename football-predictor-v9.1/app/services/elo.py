"""
Football Predictor V9.0 - ELO Rating System
Standard Elo with K-factor adjustments for football.
"""

import math
from typing import Tuple
from loguru import logger


class EloSystem:
    """
    Football ELO rating system.
    Base: 1500. K varies by importance of match.
    """

    DEFAULT_RATING = 1500.0
    K_FRIENDLY = 20
    K_LEAGUE = 40
    K_CONTINENTAL = 50
    K_WORLD_CUP = 60

    def expected_score(self, rating_a: float, rating_b: float) -> float:
        """Expected score (win probability) for team A against team B."""
        return 1.0 / (1.0 + math.pow(10, (rating_b - rating_a) / 400.0))

    def update_ratings(
        self,
        rating_home: float,
        rating_away: float,
        score_home: int,
        score_away: int,
        k_factor: int = K_LEAGUE,
        home_advantage: float = 100.0,
    ) -> Tuple[float, float]:
        """
        Update ELO ratings after a match.
        Returns (new_home_rating, new_away_rating).
        """
        # Apply home advantage
        adj_home = rating_home + home_advantage

        ea = self.expected_score(adj_home, rating_away)
        eb = 1.0 - ea

        # Actual scores
        if score_home > score_away:
            sa, sb = 1.0, 0.0
        elif score_home < score_away:
            sa, sb = 0.0, 1.0
        else:
            sa, sb = 0.5, 0.5

        # Goal difference multiplier
        goal_diff = abs(score_home - score_away)
        gd_mult = self._goal_diff_multiplier(goal_diff)

        new_home = rating_home + k_factor * gd_mult * (sa - ea)
        new_away = rating_away + k_factor * gd_mult * (sb - eb)

        return round(new_home, 2), round(new_away, 2)

    def _goal_diff_multiplier(self, goal_diff: int) -> float:
        if goal_diff <= 1:
            return 1.0
        elif goal_diff == 2:
            return 1.5
        elif goal_diff == 3:
            return 1.75
        else:
            return 1.75 + (goal_diff - 3) * 0.05

    def win_probability(
        self,
        rating_home: float,
        rating_away: float,
        home_advantage: float = 100.0,
    ) -> Tuple[float, float, float]:
        """
        Returns (home_win_prob, draw_prob, away_win_prob).
        Uses ELO difference to estimate 1X2 probabilities.
        """
        adj_home = rating_home + home_advantage
        raw_home = self.expected_score(adj_home, rating_away)
        raw_away = self.expected_score(rating_away, adj_home)

        # Draw probability estimated from ratings closeness
        diff = abs(adj_home - rating_away)
        draw_base = 0.28 - (diff / 400.0) * 0.12
        draw_prob = max(0.05, min(0.35, draw_base))

        # Normalize
        home_win = raw_home * (1.0 - draw_prob)
        away_win = raw_away * (1.0 - draw_prob)
        total = home_win + draw_prob + away_win

        return (
            round(home_win / total, 4),
            round(draw_prob / total, 4),
            round(away_win / total, 4),
        )

    def expected_goals(
        self,
        rating_home: float,
        rating_away: float,
        home_advantage: float = 100.0,
        base_home_xg: float = 1.35,
        base_away_xg: float = 1.10,
    ) -> Tuple[float, float]:
        """
        Estimate expected goals from ELO ratings.
        Returns (home_xg, away_xg).
        """
        diff = (rating_home + home_advantage) - rating_away
        home_mult = 1.0 + (diff / 400.0) * 0.5
        away_mult = 1.0 - (diff / 400.0) * 0.5

        home_xg = max(0.3, base_home_xg * home_mult)
        away_xg = max(0.3, base_away_xg * away_mult)

        return round(home_xg, 3), round(away_xg, 3)


elo_system = EloSystem()
