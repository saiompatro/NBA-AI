"""Self-check for the player shot-chart / zone-shooting-split aggregation.

Run directly: python scripts/test_shot_chart.py
"""
from __future__ import annotations

import sys
import types
from pathlib import Path

import pandas as pd

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

from app.services.league_analytics import LeagueAnalyticsService


_SHOTS = pd.DataFrame(
    [
        # Restricted Area: 3-for-4
        {"LOC_X": 0, "LOC_Y": 10, "SHOT_MADE_FLAG": 1, "SHOT_ZONE_BASIC": "Restricted Area", "SHOT_DISTANCE": 1, "SHOT_TYPE": "2PT Field Goal"},
        {"LOC_X": 5, "LOC_Y": 5, "SHOT_MADE_FLAG": 1, "SHOT_ZONE_BASIC": "Restricted Area", "SHOT_DISTANCE": 1, "SHOT_TYPE": "2PT Field Goal"},
        {"LOC_X": -5, "LOC_Y": 8, "SHOT_MADE_FLAG": 1, "SHOT_ZONE_BASIC": "Restricted Area", "SHOT_DISTANCE": 2, "SHOT_TYPE": "2PT Field Goal"},
        {"LOC_X": 2, "LOC_Y": 6, "SHOT_MADE_FLAG": 0, "SHOT_ZONE_BASIC": "Restricted Area", "SHOT_DISTANCE": 1, "SHOT_TYPE": "2PT Field Goal"},
        # Above the Break 3: 1-for-2
        {"LOC_X": 230, "LOC_Y": 90, "SHOT_MADE_FLAG": 1, "SHOT_ZONE_BASIC": "Above the Break 3", "SHOT_DISTANCE": 26, "SHOT_TYPE": "3PT Field Goal"},
        {"LOC_X": -230, "LOC_Y": 90, "SHOT_MADE_FLAG": 0, "SHOT_ZONE_BASIC": "Above the Break 3", "SHOT_DISTANCE": 26, "SHOT_TYPE": "3PT Field Goal"},
    ]
)
_LEAGUE = pd.DataFrame(
    [
        {"SHOT_ZONE_BASIC": "Restricted Area", "FG_PCT": 0.63},
        {"SHOT_ZONE_BASIC": "Above the Break 3", "FG_PCT": 0.35},
    ]
)


def main() -> None:
    service = LeagueAnalyticsService()

    # Playoffs frame is present -> used directly, no regular-season fallback call.
    LeagueAnalyticsService._shot_chart_frames = lambda self, player_id, season, season_type: (
        (_SHOTS, _LEAGUE) if season_type == "Playoffs" else (pd.DataFrame(), pd.DataFrame())
    )
    result = service.player_shot_chart(201939, "2025-26")

    assert result["season_type"] == "Playoffs"
    assert len(result["shots"]) == 6
    assert result["totals"] == {"fgm": 4, "fga": 6, "fg_pct": round(4 / 6 * 100, 1)}

    zones = {z["zone"]: z for z in result["zones"]}
    ra = zones["Restricted Area"]
    assert ra["fgm"] == 3 and ra["fga"] == 4 and ra["fg_pct"] == 75.0
    assert ra["league_pct"] == 63.0
    assert ra["delta"] == round(75.0 - 63.0, 1), "delta must be player FG% minus league FG% for the zone"

    atb3 = zones["Above the Break 3"]
    assert atb3["fgm"] == 1 and atb3["fga"] == 2 and atb3["fg_pct"] == 50.0
    assert atb3["delta"] == round(50.0 - 35.0, 1)

    # Zone rows are sorted by attempt volume, most-used zone first.
    assert result["zones"][0]["zone"] == "Restricted Area"

    # Coordinates pass through unchanged (needed to plot the dot on the court SVG).
    made = next(s for s in result["shots"] if s["x"] == 5 and s["y"] == 5)
    assert made["made"] is True and made["zone"] == "Restricted Area"

    # No playoff data at all -> falls back to regular season, and empty-empty -> empty result.
    LeagueAnalyticsService._shot_chart_frames = lambda self, player_id, season, season_type: (pd.DataFrame(), pd.DataFrame())
    empty = service.player_shot_chart(999999, "2025-26")
    assert empty == {"season_type": None, "shots": [], "zones": [], "totals": None}

    print("OK: shot chart zone aggregation, league-average deltas, and empty-data fallback are correct")


if __name__ == "__main__":
    main()
