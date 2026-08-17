"""Self-check for shot-chart aggregation (court points + per-zone FG% vs league).

Run directly: python scripts/test_shot_chart.py
"""
from __future__ import annotations

import sys
import types
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

import pandas as pd

from app.services.league_analytics import summarize_shot_chart


def _shot(loc_x, loc_y, made, shot_type="2PT Field Goal", zone="Mid-Range", distance=15):
    return {
        "LOC_X": loc_x,
        "LOC_Y": loc_y,
        "SHOT_MADE_FLAG": 1 if made else 0,
        "SHOT_ATTEMPTED_FLAG": 1,
        "SHOT_TYPE": shot_type,
        "SHOT_ZONE_BASIC": zone,
        "SHOT_DISTANCE": distance,
    }


def main() -> None:
    empty = summarize_shot_chart(pd.DataFrame(), pd.DataFrame())
    assert empty == {"total_fga": 0, "total_fgm": 0, "fg_pct": 0.0, "shots": [], "zones": []}

    rows = [
        _shot(-10, 5, True, zone="Restricted Area"),
        _shot(10, 5, False, zone="Restricted Area"),
        _shot(200, 100, True, "3PT Field Goal", zone="Left Corner 3", distance=23),
        _shot(0, 450, True, zone="Backcourt"),  # beyond the LOC_Y<=400 cutoff, must be dropped
    ]
    league_rows = [
        {"SHOT_ZONE_BASIC": "Restricted Area", "FGA": 1000, "FGM": 620},
        {"SHOT_ZONE_BASIC": "Left Corner 3", "FGA": 200, "FGM": 76},
    ]
    result = summarize_shot_chart(pd.DataFrame(rows), pd.DataFrame(league_rows))

    assert len(result["shots"]) == 3, "the LOC_Y>400 backcourt heave must be dropped"
    assert result["total_fga"] == 3 and result["total_fgm"] == 2
    assert result["fg_pct"] == round(2 / 3 * 100, 1)

    three = next(shot for shot in result["shots"] if shot["value"] == 3)
    assert three["made"] is True and three["distance"] == 23

    zones = {zone["zone"]: zone for zone in result["zones"]}
    assert zones["Restricted Area"]["fga"] == 2 and zones["Restricted Area"]["fgm"] == 1
    assert zones["Restricted Area"]["fg_pct"] == 50.0
    assert zones["Restricted Area"]["league_fg_pct"] == 62.0
    assert zones["Restricted Area"]["diff"] == round(50.0 - 62.0, 1)

    assert zones["Left Corner 3"]["fg_pct"] == 100.0
    assert zones["Left Corner 3"]["league_fg_pct"] == 38.0

    # 600-shot cap keeps only the most recent (tail) attempts.
    many_rows = [_shot(0, i % 300, i % 2 == 0) for i in range(650)]
    capped = summarize_shot_chart(pd.DataFrame(many_rows), pd.DataFrame())
    assert len(capped["shots"]) == 600, "shot list must be capped at 600, keeping the most recent"

    print("OK: shot-chart aggregation (zone FG%, league diff, backcourt filter, 600 cap) is internally consistent")


if __name__ == "__main__":
    main()
