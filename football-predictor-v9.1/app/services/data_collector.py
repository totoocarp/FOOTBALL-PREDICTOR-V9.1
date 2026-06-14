"""
Football Predictor V9.0 - Data Collector
Fetches data from multiple free APIs with automatic fallback.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Optional, Any
import httpx
from loguru import logger
from app.config import settings
from app.services.cache import cache


class APIClient:
    """Base async HTTP client with retry and rate limiting."""

    def __init__(self, base_url: str, headers: dict = None, timeout: float = 15.0):
        self.base_url = base_url
        self.headers = headers or {}
        self.timeout = timeout

    async def get(self, endpoint: str, params: dict = None, cache_key: str = None, cache_ttl: int = None) -> Optional[Any]:
        if cache_key:
            cached = cache.get(cache_key)
            if cached is not None:
                return cached

        url = f"{self.base_url}{endpoint}"
        for attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                    response = await client.get(url, headers=self.headers, params=params)
                    response.raise_for_status()
                    data = response.json()
                    if cache_key:
                        cache.set(cache_key, data, cache_ttl)
                    return data
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:
                    await asyncio.sleep(2 ** attempt)
                    continue
                logger.warning(f"HTTP {e.response.status_code} from {url}: {e}")
                return None
            except Exception as e:
                if attempt < 2:
                    await asyncio.sleep(1)
                    continue
                logger.error(f"Request failed for {url}: {e}")
                return None
        return None


class FootballDataClient(APIClient):
    """football-data.org client (free tier: 10 req/min)."""
    BASE_URL = "https://api.football-data.org/v4"

    def __init__(self):
        super().__init__(
            self.BASE_URL,
            headers={"X-Auth-Token": settings.football_data_api_key}
        )

    async def get_competitions(self) -> Optional[list]:
        if not settings.has_football_data_key:
            return None
        data = await self.get("/competitions", cache_key="fd_competitions", cache_ttl=24)
        if data and "competitions" in data:
            return data["competitions"]
        return None

    async def get_matches(self, competition_code: str, date_from: str = None, date_to: str = None) -> Optional[list]:
        if not settings.has_football_data_key:
            return None
        params = {}
        if date_from:
            params["dateFrom"] = date_from
        if date_to:
            params["dateTo"] = date_to
        cache_key = f"fd_matches_{competition_code}_{date_from}_{date_to}"
        data = await self.get(f"/competitions/{competition_code}/matches", params=params, cache_key=cache_key, cache_ttl=1)
        if data and "matches" in data:
            return data["matches"]
        return None

    async def get_standings(self, competition_code: str) -> Optional[dict]:
        if not settings.has_football_data_key:
            return None
        cache_key = f"fd_standings_{competition_code}"
        data = await self.get(f"/competitions/{competition_code}/standings", cache_key=cache_key, cache_ttl=6)
        return data

    async def get_upcoming_matches(self, days_ahead: int = 7) -> Optional[list]:
        if not settings.has_football_data_key:
            return None
        date_from = datetime.now().strftime("%Y-%m-%d")
        date_to = (datetime.now() + timedelta(days=days_ahead)).strftime("%Y-%m-%d")
        params = {"dateFrom": date_from, "dateTo": date_to, "status": "SCHEDULED"}
        cache_key = f"fd_upcoming_{date_from}_{date_to}"
        data = await self.get("/matches", params=params, cache_key=cache_key, cache_ttl=1)
        if data and "matches" in data:
            return data["matches"]
        return None


class TheSportsDBClient(APIClient):
    """TheSportsDB client (free, no key needed for basic endpoints)."""
    BASE_URL = "https://www.thesportsdb.com/api/v1/json/3"

    def __init__(self):
        super().__init__(self.BASE_URL)

    async def search_team(self, team_name: str) -> Optional[dict]:
        cache_key = f"tsdb_team_{team_name.lower().replace(' ', '_')}"
        data = await self.get("/searchteams.php", params={"t": team_name}, cache_key=cache_key, cache_ttl=48)
        if data and data.get("teams"):
            return data["teams"][0]
        return None

    async def get_league_events(self, league_id: str, season: str) -> Optional[list]:
        cache_key = f"tsdb_events_{league_id}_{season}"
        data = await self.get("/eventsseason.php", params={"id": league_id, "s": season}, cache_key=cache_key, cache_ttl=6)
        if data and data.get("events"):
            return data["events"]
        return None

    async def get_next_events(self, league_id: str, count: int = 10) -> Optional[list]:
        cache_key = f"tsdb_next_{league_id}"
        data = await self.get("/eventsnextleague.php", params={"id": league_id}, cache_key=cache_key, cache_ttl=2)
        if data and data.get("events"):
            return data["events"][:count]
        return None


class OpenLigaDBClient(APIClient):
    """OpenLigaDB client (free, no key, Bundesliga + more)."""
    BASE_URL = "https://api.openligadb.de"

    def __init__(self):
        super().__init__(self.BASE_URL)

    async def get_current_matchday(self, league: str = "bl1", season: str = "2024") -> Optional[list]:
        cache_key = f"ol_matchday_{league}_{season}"
        data = await self.get(f"/getmatchdata/{league}/{season}", cache_key=cache_key, cache_ttl=1)
        return data

    async def get_table(self, league: str = "bl1", season: str = "2024") -> Optional[list]:
        cache_key = f"ol_table_{league}_{season}"
        data = await self.get(f"/getbltable/{league}/{season}", cache_key=cache_key, cache_ttl=6)
        return data


class APIFootballClient(APIClient):
    """API-Football client (free tier: 100 req/day)."""
    BASE_URL = "https://v3.football.api-sports.io"

    def __init__(self):
        super().__init__(
            self.BASE_URL,
            headers={
                "x-rapidapi-key": settings.api_football_key,
                "x-rapidapi-host": settings.api_football_host,
            }
        )

    async def get_fixtures(self, date: str = None, league: int = None, season: int = None) -> Optional[list]:
        if not settings.has_api_football_key:
            return None
        params = {}
        if date:
            params["date"] = date
        if league:
            params["league"] = league
        if season:
            params["season"] = season
        cache_key = f"af_fixtures_{date}_{league}_{season}"
        data = await self.get("/fixtures", params=params, cache_key=cache_key, cache_ttl=1)
        if data and "response" in data:
            return data["response"]
        return None

    async def get_standings(self, league: int, season: int) -> Optional[list]:
        if not settings.has_api_football_key:
            return None
        cache_key = f"af_standings_{league}_{season}"
        data = await self.get("/standings", params={"league": league, "season": season}, cache_key=cache_key, cache_ttl=6)
        if data and "response" in data:
            return data["response"]
        return None

    async def get_injuries(self, fixture_id: int) -> Optional[list]:
        if not settings.has_api_football_key:
            return None
        cache_key = f"af_injuries_{fixture_id}"
        data = await self.get("/injuries", params={"fixture": fixture_id}, cache_key=cache_key, cache_ttl=2)
        if data and "response" in data:
            return data["response"]
        return None


class OddsAPIClient(APIClient):
    """The Odds API client (free tier: 500 req/month)."""
    BASE_URL = "https://api.the-odds-api.com/v4"

    def __init__(self):
        super().__init__(self.BASE_URL)

    async def get_odds(self, sport: str = "soccer_epl") -> Optional[list]:
        if not settings.has_odds_api:
            return None
        params = {
            "apiKey": settings.odds_api_key,
            "regions": "eu",
            "markets": "h2h",
            "oddsFormat": "decimal",
        }
        cache_key = f"odds_{sport}"
        data = await self.get(f"/sports/{sport}/odds", params=params, cache_key=cache_key, cache_ttl=1)
        return data


class DataCollector:
    """
    Orchestrates data collection from all sources with automatic fallback.
    Priority: Football-Data → API-Football → TheSportsDB → OpenLigaDB
    """

    def __init__(self):
        self.football_data = FootballDataClient()
        self.api_football = APIFootballClient()
        self.thesportsdb = TheSportsDBClient()
        self.openligadb = OpenLigaDBClient()
        self.odds_api = OddsAPIClient()

    async def get_upcoming_matches(self, days_ahead: int = 7) -> list[dict]:
        """Get upcoming matches from best available source."""
        matches = []

        # Try Football-Data first
        fd_matches = await self.football_data.get_upcoming_matches(days_ahead)
        if fd_matches:
            for m in fd_matches[:50]:
                matches.append({
                    "source": "football-data",
                    "external_id": f"fd_{m.get('id')}",
                    "home_team": m.get("homeTeam", {}).get("name", "Unknown"),
                    "away_team": m.get("awayTeam", {}).get("name", "Unknown"),
                    "competition": m.get("competition", {}).get("name", "Unknown"),
                    "match_date": m.get("utcDate"),
                    "status": m.get("status", "SCHEDULED"),
                })
            logger.info(f"Fetched {len(matches)} upcoming matches from Football-Data")
            return matches

        # Fallback: TheSportsDB
        for league_id in ["4328", "4335", "4332"]:  # EPL, La Liga, Bundesliga
            events = await self.thesportsdb.get_next_events(league_id)
            if events:
                for e in events:
                    matches.append({
                        "source": "thesportsdb",
                        "external_id": f"tsdb_{e.get('idEvent')}",
                        "home_team": e.get("strHomeTeam", "Unknown"),
                        "away_team": e.get("strAwayTeam", "Unknown"),
                        "competition": e.get("strLeague", "Unknown"),
                        "match_date": e.get("dateEvent"),
                        "status": "SCHEDULED",
                    })

        if matches:
            logger.info(f"Fetched {len(matches)} upcoming matches from TheSportsDB")
        return matches

    async def get_recent_results(self, competition_code: str = "PL", days_back: int = 7) -> list[dict]:
        """Get recent finished matches."""
        date_from = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
        date_to = datetime.now().strftime("%Y-%m-%d")
        matches = await self.football_data.get_matches(competition_code, date_from, date_to)
        if not matches:
            return []
        return [m for m in matches if m.get("status") == "FINISHED"]

    async def get_all_sources_status(self) -> dict:
        """Check which API sources are available."""
        status = {
            "football_data": {
                "available": settings.has_football_data_key,
                "has_key": settings.has_football_data_key,
                "note": "Requires free API key from football-data.org",
            },
            "api_football": {
                "available": settings.has_api_football_key,
                "has_key": settings.has_api_football_key,
                "note": "Requires free API key from api-football.com (100 req/day)",
            },
            "thesportsdb": {
                "available": True,
                "has_key": True,
                "note": "Free, no key required for basic endpoints",
            },
            "openligadb": {
                "available": True,
                "has_key": True,
                "note": "Free, no key required, Bundesliga specialized",
            },
            "odds_api": {
                "available": settings.has_odds_api,
                "has_key": settings.has_odds_api,
                "note": "Requires free API key from the-odds-api.com (500 req/month)",
            },
            "ai_assistant": {
                "available": settings.has_ai,
                "has_openai": settings.has_openai,
                "has_anthropic": settings.has_anthropic,
                "note": "Optional: OpenAI or Anthropic key for AI analysis",
            },
        }
        return status


data_collector = DataCollector()
