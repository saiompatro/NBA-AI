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
    "back injury",
    "back spasms",
    "back soreness",
    "back tightness",
]

# Headlines about a player coming back mention the same body parts.
_RETURN_PHRASES = [
    "returns",
    "return to",
    "set to return",
    "cleared to play",
    "back in the lineup",
    "available to play",
    "upgraded to available",
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
    if any(phrase in lower for phrase in _RETURN_PHRASES):
        return False
    return any(phrase in lower for phrase in _INJURY_PHRASES)


class InjuryNewsWatch:
    """Polls news feeds every 60s during live games and caches relevant alerts."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._alerts: list[dict[str, Any]] = []
        self._last_fetch: float = 0.0
        self._last_terms: tuple[str, ...] = ()

    def refresh(
        self,
        team_terms: list[str],
        player_terms: list[str],
        refresh_key: str = "cached",
        max_age_minutes: int = 120,
    ) -> None:
        """Fetch news and extract injury/ejection alerts relevant to current game."""
        import time

        now = time.monotonic()
        terms_key = tuple(team_terms)
        with self._lock:
            # Throttle repeat polls for one game, but never let a different
            # matchup inherit the previous matchup's alerts.
            if terms_key == self._last_terms and now - self._last_fetch < 55:
                return
            self._last_fetch = now
            self._last_terms = terms_key

        all_articles = fetch_general_pool(refresh_key)
        query = " ".join(team_terms[:2])
        if query:
            all_articles = all_articles + fetch_google_news(query, refresh_key)

        alerts: list[dict[str, Any]] = []
        all_terms = team_terms + player_terms
        for article in all_articles:
            if not _article_is_fresh(article, max_age_minutes):
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
            self._last_terms = ()
