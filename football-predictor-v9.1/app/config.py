"""
Football Predictor V9.0 - Configuration
"""

import os
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    # Server
    host: str = Field(default="0.0.0.0", env="HOST")
    port: int = Field(default=8000, env="PORT")
    debug: bool = Field(default=False, env="DEBUG")
    secret_key: str = Field(default="change-me-in-production", env="SECRET_KEY")

    # Database
    database_url: str = Field(
        default="sqlite+aiosqlite:///./database/predictor.db",
        env="DATABASE_URL"
    )

    # Football APIs
    football_data_api_key: str = Field(default="", env="FOOTBALL_DATA_API_KEY")
    api_football_key: str = Field(default="", env="API_FOOTBALL_KEY")
    api_football_host: str = Field(default="v3.football.api-sports.io", env="API_FOOTBALL_HOST")
    thesportsdb_api_key: str = Field(default="1", env="THESPORTSDB_API_KEY")
    odds_api_key: str = Field(default="", env="ODDS_API_KEY")

    # AI (optional)
    openai_api_key: str = Field(default="", env="OPENAI_API_KEY")
    anthropic_api_key: str = Field(default="", env="ANTHROPIC_API_KEY")
    ai_model: str = Field(default="gpt-4o-mini", env="AI_MODEL")

    # Cache
    cache_ttl_hours: int = Field(default=24, env="CACHE_TTL_HOURS")
    cache_dir: str = Field(default="database/cache", env="CACHE_DIR")

    # Simulation
    monte_carlo_simulations: int = Field(default=20000, env="MONTE_CARLO_SIMULATIONS")
    scheduler_interval_minutes: int = Field(default=10, env="SCHEDULER_INTERVAL_MINUTES")

    # Paths
    base_dir: Path = Path(__file__).parent.parent
    database_dir: Path = base_dir / "database"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

    @property
    def is_sqlite(self) -> bool:
        return "sqlite" in self.database_url

    @property
    def has_football_data_key(self) -> bool:
        return bool(self.football_data_api_key)

    @property
    def has_api_football_key(self) -> bool:
        return bool(self.api_football_key)

    @property
    def has_openai(self) -> bool:
        return bool(self.openai_api_key)

    @property
    def has_anthropic(self) -> bool:
        return bool(self.anthropic_api_key)

    @property
    def has_ai(self) -> bool:
        return self.has_openai or self.has_anthropic

    @property
    def has_odds_api(self) -> bool:
        return bool(self.odds_api_key)


settings = Settings()
