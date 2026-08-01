"""Self-check for LeagueAnalyticsService rest-day / back-to-back detection.

Run directly: python scripts/test_rest_days.py
"""
from __future__ import annotations

import sys
import types
from datetime import date
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

# Stub out the `app`/`app.services` packages before importing league_analytics so this
# check doesn't drag in app/__init__.py -> app.main -> torch (unrelated to this logic
# and not always installable/loadable in every environment).
for name, path in (("app", _ROOT / "app"), ("app.services", _ROOT / "app" / "services")):
    if name not in sys.modules:
        stub = types.ModuleType(name)
        stub.__path__ = [str(path)]
        sys.modules[name] = stub

from app.services.league_analytics import LeagueAnalyticsService, _REST_DAYS_CAP


def _event(abbr: str) -> dict:
    return {"competitions": [{"competitors": [
        {"team": {"abbreviation": abbr}},
        {"team": {"abbreviation": "ZZZ"}},
    ]}]}


def main() -> None:
    service = LeagueAnalyticsService()
    schedule = {
        date(2026, 7, 31): [_event("BOS")],  # played yesterday
        date(2026, 7, 30): [_event("NYK")],  # played 2 days ago
        date(2026, 7, 21): [_event("MIA")],  # played 11 days ago -> should cap
    }
    # Instance attribute shadows the class method (bypassing frozen-dataclass __setattr__),
    # so no real network call happens.
    object.__setattr__(service, "_espn_scoreboard", lambda game_date: schedule.get(game_date, []))

    game_date = date(2026, 8, 1)
    assert service._rest_days("BOS", game_date) == 0, "played yesterday must be a back-to-back"
    assert service._rest_days("NYK", game_date) == 1, "played 2 days ago must be 1 day of rest"
    assert service._rest_days("MIA", game_date) == _REST_DAYS_CAP, "long layoffs must cap at _REST_DAYS_CAP"
    assert service._rest_days("LAL", game_date) == _REST_DAYS_CAP, "unknown schedule must default to fully rested"

    print("OK: rest days compute back-to-backs, real gaps, and cap/default correctly")


if __name__ == "__main__":
    main()
