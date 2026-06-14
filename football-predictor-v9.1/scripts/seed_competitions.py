"""
Football Predictor V9.0 - Seed Script
Populates initial competitions and default model weights.
"""

import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import init_db, AsyncSessionLocal
from app.models.competition import Competition
from app.models.learning import ModelWeight
from sqlalchemy import select


COMPETITIONS = [
    {"name": "Premier League", "short_code": "PL", "country": "England", "external_id": "PL", "priority": 1},
    {"name": "La Liga", "short_code": "PD", "country": "Spain", "external_id": "PD", "priority": 1},
    {"name": "Bundesliga", "short_code": "BL1", "country": "Germany", "external_id": "BL1", "priority": 1},
    {"name": "Serie A", "short_code": "SA", "country": "Italy", "external_id": "SA", "priority": 1},
    {"name": "Ligue 1", "short_code": "FL1", "country": "France", "external_id": "FL1", "priority": 2},
    {"name": "UEFA Champions League", "short_code": "CL", "country": "Europe", "external_id": "CL", "priority": 1},
    {"name": "UEFA Europa League", "short_code": "EL", "country": "Europe", "external_id": "EL", "priority": 2},
    {"name": "FIFA World Cup 2026", "short_code": "WC26", "country": "International", "external_id": "WC2026", "priority": 1, "type": "INTERNATIONAL"},
    {"name": "Copa América", "short_code": "CA", "country": "Americas", "external_id": "CA", "priority": 2, "type": "INTERNATIONAL"},
    {"name": "UEFA Euro", "short_code": "EC", "country": "Europe", "external_id": "EC", "priority": 2, "type": "INTERNATIONAL"},
]

DEFAULT_WEIGHTS = [
    {"variable_name": "elo", "weight": 1.8},
    {"variable_name": "xg", "weight": 2.0},
    {"variable_name": "form", "weight": 1.4},
    {"variable_name": "market", "weight": 1.6},
    {"variable_name": "ranking", "weight": 1.2},
    {"variable_name": "squad_value", "weight": 0.8},
    {"variable_name": "availability", "weight": 1.3},
    {"variable_name": "style", "weight": 0.6},
    {"variable_name": "fatigue", "weight": 0.5},
]


async def seed():
    print("Initializing database...")
    await init_db()

    async with AsyncSessionLocal() as session:
        # Seed competitions
        for comp_data in COMPETITIONS:
            existing = await session.execute(
                select(Competition).where(Competition.external_id == comp_data["external_id"])
            )
            if not existing.scalar_one_or_none():
                comp = Competition(**comp_data)
                session.add(comp)
                print(f"  + Competition: {comp_data['name']}")

        # Seed default weights
        for w_data in DEFAULT_WEIGHTS:
            existing = await session.execute(
                select(ModelWeight).where(ModelWeight.variable_name == w_data["variable_name"])
            )
            if not existing.scalar_one_or_none():
                weight = ModelWeight(**w_data)
                session.add(weight)
                print(f"  + Weight: {w_data['variable_name']} = {w_data['weight']}")

        await session.commit()
        print("\nSeeding complete!")


if __name__ == "__main__":
    asyncio.run(seed())
