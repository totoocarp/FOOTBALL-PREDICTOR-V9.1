"""
Football Predictor V9.0 - Cache Service
Disk-based cache with 24h TTL for API responses.
"""

import json
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional
from loguru import logger
from app.config import settings


class CacheService:
    def __init__(self):
        self.cache_dir = Path(settings.cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl_hours = settings.cache_ttl_hours

    def _key_to_path(self, key: str) -> Path:
        hashed = hashlib.md5(key.encode()).hexdigest()
        return self.cache_dir / f"{hashed}.json"

    def get(self, key: str) -> Optional[Any]:
        path = self._key_to_path(key)
        if not path.exists():
            return None
        try:
            with open(path, "r") as f:
                data = json.load(f)
            expires_at = datetime.fromisoformat(data["expires_at"])
            if datetime.utcnow() > expires_at:
                path.unlink(missing_ok=True)
                return None
            return data["value"]
        except Exception as e:
            logger.warning(f"Cache read error for key {key}: {e}")
            return None

    def set(self, key: str, value: Any, ttl_hours: Optional[int] = None) -> None:
        path = self._key_to_path(key)
        hours = ttl_hours or self.ttl_hours
        try:
            data = {
                "key": key,
                "value": value,
                "created_at": datetime.utcnow().isoformat(),
                "expires_at": (datetime.utcnow() + timedelta(hours=hours)).isoformat(),
            }
            with open(path, "w") as f:
                json.dump(data, f, default=str)
        except Exception as e:
            logger.warning(f"Cache write error for key {key}: {e}")

    def delete(self, key: str) -> None:
        path = self._key_to_path(key)
        path.unlink(missing_ok=True)

    def clear_expired(self) -> int:
        count = 0
        for path in self.cache_dir.glob("*.json"):
            try:
                with open(path, "r") as f:
                    data = json.load(f)
                expires_at = datetime.fromisoformat(data["expires_at"])
                if datetime.utcnow() > expires_at:
                    path.unlink()
                    count += 1
            except Exception:
                path.unlink(missing_ok=True)
                count += 1
        return count

    def clear_all(self) -> int:
        count = 0
        for path in self.cache_dir.glob("*.json"):
            path.unlink(missing_ok=True)
            count += 1
        return count

    def stats(self) -> dict:
        total = 0
        expired = 0
        size_bytes = 0
        for path in self.cache_dir.glob("*.json"):
            total += 1
            size_bytes += path.stat().st_size
            try:
                with open(path, "r") as f:
                    data = json.load(f)
                expires_at = datetime.fromisoformat(data["expires_at"])
                if datetime.utcnow() > expires_at:
                    expired += 1
            except Exception:
                expired += 1
        return {
            "total_entries": total,
            "expired_entries": expired,
            "active_entries": total - expired,
            "total_size_kb": round(size_bytes / 1024, 2),
        }


cache = CacheService()
