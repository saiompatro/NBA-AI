from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any

from app.services.news_sources import (
    fetch_general_pool,
    fetch_google_news,
    article_relevance,
)


_INJURY_PHRASES = [
    "out for game",
    "will not return",
    "ruled out",
    "left game",
    "x-ray",
    "x ray",
    "ejected",
    "ejection",
    "concussion",
    "ankle",
    "knee",
    "hamstring",
    "wrist",
    "back",
]


def _article_is_fresh(article: dict[str, Any], max_age_minutes: int = 120) -> bool:
    published = article.get("published") or ""
    if not published:
        return True
    try:
        dt = datetime.fromisoformat(published.replace("Z", "+00:00"))
        age = (datetime.now(timezone.utc) - dt).total_seconds() / 60
        return age <= max_age_minutes
    except (ValueError, TypeError):
        return True


def _mentions_injury_phrase(text: str) -> bool:
    lower = text.lower()
    return any(phrase in lower for phrase in _INJURY_PHRASES)


class InjuryNewsWatch:
    """Polls news feeds every 60s during live games and caches relevant alerts."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._alerts: list[dict[str, Any]] = []
        self._last_fetch: float = 0.0

    def refresh(
        self,
        team_terms: list[str],
        player_terms: list[str],
        refresh_key: str = "cached",
    ) -> None:
        """Fetch news and extract injury/ejection alerts relevant to current game."""
        import time

        now = time.monotonic()
        with self._lock:
            if now - self._last_fetch < 55:
                return
            self._last_fetch = now

        all_articles = fetch_general_pool(refresh_key)
        query = " ".join(team_terms[:2])
        if query:
            all_articles = all_articles + fetch_google_news(query, refresh_key)

        alerts: list[dict[str, Any]] = []
        all_terms = team_terms + player_terms
        for article in all_articles:
            if not _article_is_fresh(article):
                continue
            relevance = article_relevance(article, all_terms)
            if relevance == 0:
                continue
            haystack = f"{article.get('headline', '')} {article.get('description', '')}"
            if not _mentions_injury_phrase(haystack):
                continue
            alerts.append(
                {
                    "headline": article.get("headline", ""),
                    "source": article.get("source", ""),
                    "published": article.get("published", ""),
                    "url": article.get("url", ""),
                    "relevance": relevance,
                }
            )

        alerts.sort(key=lambda a: -a["relevance"])
        with self._lock:
            self._alerts = alerts[:10]

    def alerts(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._alerts)

    def clear(self) -> None:
        with self._lock:
            self._alerts = []
            self._last_fetch = 0.0
