"""League-wide injury report from ESPN's public injuries feed.

The pre-game model used to learn about absences only by scanning news
headlines for a player's last name next to words like "knee".  That misses
anyone who was ruled out more than a couple of hours ago (season-long
injuries, multi-week absences) and cannot tell "out" from "questionable".
This module reads the structured report instead: one request covers all 30
teams and carries a status for every listed player.
"""
from __future__ import annotations

import re
import threading
import time
import unicodedata
from typing import Any, Callable

import requests
import urllib3


urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

INJURIES_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/injuries"
SOURCE_LABEL = "ESPN injury report"

# Share of a player's usual contribution the team is expected to lose, by
# listed status.  "Out" is certain; the others are discounted by how often
# players with that tag end up sitting.
_STATUS_WEIGHTS: list[tuple[str, float]] = [
    ("out", 1.0),
    ("suspen", 1.0),
    ("doubtful", 0.75),
    ("questionable", 0.5),
    ("day-to-day", 0.4),
    ("gtd", 0.4),
    ("probable", 0.0),
]
_UNKNOWN_STATUS_WEIGHT = 0.4

_REFRESH_SECONDS = 600        # the report changes a few times a day
_RETRY_SECONDS = 60           # wait this long after a failed fetch
_STALE_SECONDS = 6 * 3600     # stop trusting a report we could not renew

_NAME_SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v"}


def normalize_player_name(name: str) -> str:
    """Fold a player name so "Luka Dončić" and "Luka Doncic Jr." compare equal."""
    folded = unicodedata.normalize("NFKD", str(name or ""))
    folded = "".join(ch for ch in folded if not unicodedata.combining(ch)).lower()
    words = re.sub(r"[^a-z0-9 ]+", " ", folded.replace("'", "").replace(".", "")).split()
    while words and words[-1] in _NAME_SUFFIXES:
        words.pop()
    return " ".join(words)


def status_weight(status: str) -> float:
    lower = str(status or "").lower().replace("day to day", "day-to-day")
    for marker, weight in _STATUS_WEIGHTS:
        if marker in lower:
            return weight
    return _UNKNOWN_STATUS_WEIGHT


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def parse_injuries(
    payload: Any, resolve_team: Callable[[str, str], str] | None = None
) -> dict[str, list[dict[str, Any]]]:
    """Turn the raw feed into {team abbreviation: [injury entries]}.

    `resolve_team(abbreviation, display_name)` maps ESPN's team labels onto
    the app's abbreviations; entries whose team cannot be resolved are dropped.
    """
    report: dict[str, list[dict[str, Any]]] = {}
    groups = payload.get("injuries") if isinstance(payload, dict) else None
    for group in groups or []:
        if not isinstance(group, dict):
            continue
        group_name = _text(group.get("displayName"))
        for item in group.get("injuries") or []:
            if not isinstance(item, dict):
                continue
            athlete = item.get("athlete") if isinstance(item.get("athlete"), dict) else {}
            player = _text(athlete.get("displayName")) or " ".join(
                part for part in (_text(athlete.get("firstName")), _text(athlete.get("lastName"))) if part
            )
            if not player:
                continue
            team_info = athlete.get("team") if isinstance(athlete.get("team"), dict) else {}
            raw_abbr = _text(team_info.get("abbreviation")).upper()
            team_name = _text(team_info.get("displayName")) or group_name
            team = resolve_team(raw_abbr, team_name) if resolve_team else raw_abbr
            if not team:
                continue

            details = item.get("details") if isinstance(item.get("details"), dict) else {}
            fantasy = details.get("fantasyStatus") if isinstance(details.get("fantasyStatus"), dict) else {}
            kind = item.get("type") if isinstance(item.get("type"), dict) else {}
            status = (
                _text(item.get("status"))
                or _text(fantasy.get("description"))
                or _text(kind.get("description"))
            )
            injury = " ".join(
                part for part in (_text(details.get("side")), _text(details.get("type"))) if part
            )
            report.setdefault(team, []).append(
                {
                    "player": player,
                    "team": team,
                    "status": status or "Unknown",
                    "weight": status_weight(status),
                    "injury": injury,
                    "comment": _text(item.get("shortComment")) or _text(item.get("longComment")),
                    "date": _text(item.get("date")),
                    "return_date": _text(details.get("returnDate")),
                }
            )
    for entries in report.values():
        entries.sort(key=lambda entry: (-entry["weight"], entry["player"]))
    return report


class InjuryReport:
    """Cached copy of the league injury report, refreshed at most every 10 minutes."""

    def __init__(
        self,
        resolve_team: Callable[[str, str], str] | None = None,
        timeout: float = 5,
    ) -> None:
        self._resolve_team = resolve_team
        self._timeout = timeout
        self._lock = threading.Lock()
        self._report: dict[str, list[dict[str, Any]]] = {}
        self._fetched_at: float | None = None   # last successful fetch
        self._attempted_at: float | None = None  # last attempt, successful or not

    def _fetch(self) -> dict[str, list[dict[str, Any]]] | None:
        try:
            response = requests.get(INJURIES_URL, timeout=self._timeout, verify=False)
            response.raise_for_status()
            payload = response.json()
        except Exception:
            return None
        if not isinstance(payload, dict) or not isinstance(payload.get("injuries"), list):
            return None
        return parse_injuries(payload, self._resolve_team)

    def refresh(self, force: bool = False) -> bool:
        """Renew the report if it is due. Returns whether usable data is held."""
        now = time.monotonic()
        with self._lock:
            fresh = self._fetched_at is not None and now - self._fetched_at < _REFRESH_SECONDS
            backing_off = self._attempted_at is not None and now - self._attempted_at < _RETRY_SECONDS
            if (fresh or backing_off) and not force:
                return self._usable(now)
            self._attempted_at = now
        report = self._fetch()
        with self._lock:
            if report is not None:
                self._report = report
                self._fetched_at = time.monotonic()
            return self._usable(time.monotonic())

    def _usable(self, now: float) -> bool:
        return self._fetched_at is not None and now - self._fetched_at < _STALE_SECONDS

    def available(self) -> bool:
        return self.refresh()

    def for_team(self, team_abbr: str) -> list[dict[str, Any]]:
        if not self.refresh():
            return []
        with self._lock:
            return [dict(entry) for entry in self._report.get(str(team_abbr or "").upper(), [])]

    def all(self) -> dict[str, list[dict[str, Any]]]:
        if not self.refresh():
            return {}
        with self._lock:
            return {team: [dict(entry) for entry in entries] for team, entries in self._report.items()}

    def clear(self) -> None:
        with self._lock:
            self._report = {}
            self._fetched_at = None
            self._attempted_at = None
