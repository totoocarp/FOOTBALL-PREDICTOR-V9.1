"""
Football Predictor V9.0 - Data Validator Service
Validates data quality and assigns HIGH/MEDIUM/LOW confidence levels.
"""

from datetime import datetime, timedelta
from typing import Any, Optional
from loguru import logger


VALIDATION_RANGES = {
    "elo_global": (800, 2200),
    "elo_12months": (800, 2200),
    "xg_avg": (0.1, 5.0),
    "xga_avg": (0.1, 5.0),
    "goals_per_game": (0.0, 5.0),
    "goals_conceded_per_game": (0.0, 5.0),
    "points_per_game": (0.0, 3.0),
    "form_5": (0.0, 1.0),
    "form_10": (0.0, 1.0),
    "squad_value_total": (0.0, 5000.0),
    "injuries_key": (0, 11),
    "odds_home_prob": (0.05, 0.95),
    "possession_avg": (20.0, 80.0),
    "shots_on_target_avg": (0.0, 15.0),
    "clean_sheet_rate": (0.0, 1.0),
    "games_last_30": (0, 15),
    "ranking_percentile": (0.0, 1.0),
}

# Max acceptable difference between two sources for HIGH confidence
MAX_DIFF_RATIOS = {
    "xg_avg": 0.25,   # 25% difference max for HIGH
    "elo_global": 0.05,
    "form_5": 0.20,
    "goals_per_game": 0.25,
}

MAX_DATA_AGE_HOURS = {
    "elo_global": 24,
    "xg_avg": 24,
    "form_5": 6,
    "odds_home_prob": 4,
    "injuries_key": 4,
}


class DataValidator:
    """Validates data fields and assigns confidence levels."""

    def validate_field(
        self,
        field: str,
        value: Any,
        source_a: Optional[Any] = None,
        source_b: Optional[Any] = None,
        last_updated: Optional[datetime] = None,
        source_name: str = "unknown",
    ) -> dict:
        """
        Validate a single field and return confidence level + details.
        Returns: {valid, confidence, issues, value, source}
        """
        issues = []
        confidence = "HIGH"

        # 1. Null check
        if value is None:
            return {
                "valid": False,
                "confidence": "LOW",
                "issues": ["Valor nulo"],
                "value": None,
                "source": source_name,
            }

        # 2. Type check and conversion
        try:
            numeric_val = float(value)
        except (TypeError, ValueError):
            return {
                "valid": False,
                "confidence": "LOW",
                "issues": [f"Valor no numérico: {value}"],
                "value": value,
                "source": source_name,
            }

        # 3. Range check
        if field in VALIDATION_RANGES:
            lo, hi = VALIDATION_RANGES[field]
            if not (lo <= numeric_val <= hi):
                issues.append(f"Fuera de rango [{lo}, {hi}]: {numeric_val}")
                confidence = "LOW"

        # 4. Cross-source consistency check
        if source_a is not None and source_b is not None:
            try:
                a = float(source_a)
                b = float(source_b)
                if a != 0 and b != 0:
                    diff_ratio = abs(a - b) / max(abs(a), abs(b))
                    max_ratio = MAX_DIFF_RATIOS.get(field, 0.30)
                    if diff_ratio > max_ratio:
                        issues.append(f"Inconsistencia entre fuentes: A={a:.2f} vs B={b:.2f} ({diff_ratio*100:.1f}%)")
                        confidence = "LOW"
                    elif diff_ratio > max_ratio * 0.5:
                        issues.append(f"Diferencia moderada: A={a:.2f} vs B={b:.2f}")
                        if confidence == "HIGH":
                            confidence = "MEDIUM"
            except (TypeError, ValueError):
                pass

        # 5. Age check
        if last_updated is not None and field in MAX_DATA_AGE_HOURS:
            max_age_h = MAX_DATA_AGE_HOURS[field]
            age_h = (datetime.utcnow() - last_updated).total_seconds() / 3600
            if age_h > max_age_h * 2:
                issues.append(f"Dato muy desactualizado: {age_h:.1f}h (máx recomendado: {max_age_h}h)")
                confidence = "LOW"
            elif age_h > max_age_h:
                issues.append(f"Dato desactualizado: {age_h:.1f}h")
                if confidence == "HIGH":
                    confidence = "MEDIUM"

        return {
            "valid": len([i for i in issues if "rango" in i or "nulo" in i or "numérico" in i]) == 0,
            "confidence": confidence,
            "issues": issues,
            "value": numeric_val,
            "source": source_name,
        }

    def validate_team_stats(self, stats: dict, team_name: str = "") -> dict:
        """Validate all fields in a team stats dict."""
        results = {}
        summary = {"HIGH": 0, "MEDIUM": 0, "LOW": 0, "invalid": 0}
        source = stats.get("_source", "unknown")

        for field, (lo, hi) in VALIDATION_RANGES.items():
            val = stats.get(field)
            result = self.validate_field(field, val, source_name=source)
            results[field] = result
            if not result["valid"]:
                summary["invalid"] += 1
            summary[result["confidence"]] += 1

        total = max(sum(summary.values()) - summary["invalid"], 1)
        confidence_pct = {
            "HIGH": round(summary["HIGH"] / total * 100, 1),
            "MEDIUM": round(summary["MEDIUM"] / total * 100, 1),
            "LOW": round(summary["LOW"] / total * 100, 1),
        }

        return {
            "team": team_name,
            "source": source,
            "fields": results,
            "summary": summary,
            "confidence_pct": confidence_pct,
            "overall_confidence": "HIGH" if summary["HIGH"] > summary["LOW"] * 2 else (
                "LOW" if summary["LOW"] > summary["HIGH"] else "MEDIUM"
            ),
        }

    def validate_xg_sources(self, xg_source_a: float, xg_source_b: float, team: str) -> dict:
        """Specific validation for xG from two sources — example from spec."""
        diff = abs(xg_source_a - xg_source_b)
        max_diff = 0.5  # if diff > 0.5 then LOW confidence

        if diff <= 0.2:
            confidence = "HIGH"
        elif diff <= 0.5:
            confidence = "MEDIUM"
        else:
            confidence = "LOW"

        return {
            "team": team,
            "metric": "xG",
            "source_a": xg_source_a,
            "source_b": xg_source_b,
            "difference": round(diff, 3),
            "confidence": confidence,
            "message": f"xG {team}: API A={xg_source_a:.2f} / API B={xg_source_b:.2f} → Confianza: {confidence}",
        }


data_validator = DataValidator()
