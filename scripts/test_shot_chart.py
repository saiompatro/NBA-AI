"""Self-check for shot-chart payload shaping and zone aggregation.

Run directly: python scripts/test_shot_chart.py
"""
from __future__ import annotations

import sys
import types
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

for name, path in (("app", _ROOT / "app"), ("app.services", _ROOT / "app" / "services")):
    if name not in sys.modules:
        stub = types.ModuleType(name)
        stub.__path__ = [str(path)]
        sys.modules[name] = stub

# league_analytics imports pandas/nba_api at module scope purely for the live NBA Stats
# path; this check only exercises the pure transforms, so stub them out rather than
# requiring the full ML dependency set to be installed.
if "pandas" not in sys.modules:
    _pandas = types.ModuleType("pandas")
    _pandas.DataFrame = object
    sys.modules["pandas"] = _pandas
for _name in ("nba_api", "nba_api.stats", "nba_api.stats.library", "nba_api.stats.library.http"):
    if _name not in sys.modules:
        _mod = types.ModuleType(_name)
        _mod.__path__ = []
        sys.modules[_name] = _mod
sys.modules["nba_api.stats.library.http"].NBAStatsHTTP = type("NBAStatsHTTP", (), {"headers": {}})

from app.services.league_analytics import (
    SHOT_ZONE_ORDER,
    shot_chart_params,
    shot_chart_payload,
    shot_zone_summary,
)


def _row(**overrides: object) -> dict[str, object]:
    base = {
        "LOC_X": "0",
        "LOC_Y": "0",
        "SHOT_MADE_FLAG": "1",
        "SHOT_TYPE": "2PT Field Goal",
        "SHOT_ZONE_BASIC": "Restricted Area",
        "SHOT_DISTANCE": "0",
        "PERIOD": "1",
        "ACTION_TYPE": "Layup Shot",
        "GAME_DATE": "20260101",
    }
    base.update(overrides)
    return base


def main() -> None:
    # 1. Empty input is safe (the no-network case).
    payload = shot_chart_payload([], "")
    assert payload["shots"] == []
    assert payload["zones"] == []
    assert payload["summary"]["attempts"] == 0
    assert payload["summary"]["fg_pct"] == 0
    assert payload["truncated"] is False

    # 2. Per-shot key contract, on one fabricated row (strings, as NBA Stats sends them).
    single = shot_chart_payload([_row(SHOT_TYPE="3PT Field Goal")], "Regular Season")
    shot = single["shots"][0]
    assert set(shot.keys()) == {"x", "y", "made", "shot_type", "zone", "distance", "period", "action", "date"}
    assert shot["made"] is True
    assert shot["shot_type"] == 3

    two = shot_chart_payload([_row(SHOT_TYPE="2PT Field Goal")], "Regular Season")
    assert two["shots"][0]["shot_type"] == 2

    # 3. Junk rows are dropped, not fatal.
    junk_then_good = shot_chart_payload([_row(LOC_X=None), _row(LOC_X="")], "Regular Season")
    assert junk_then_good["shots"] == []
    mixed = shot_chart_payload([_row(LOC_X=None), _row()], "Regular Season")
    assert len(mixed["shots"]) == 1

    # 4. Zone math: 3 attempts / 1 make in "Restricted Area".
    rows = [
        _row(SHOT_MADE_FLAG="1"),
        _row(SHOT_MADE_FLAG="0"),
        _row(SHOT_MADE_FLAG="0"),
    ]
    zones = shot_zone_summary(shot_chart_payload(rows, "Regular Season")["shots"])
    assert zones == [{"zone": "Restricted Area", "attempts": 3, "makes": 1, "fg_pct": 33.3}]

    # 5. Zone ordering follows SHOT_ZONE_ORDER regardless of input order.
    out_of_order = [
        _row(SHOT_ZONE_BASIC="Above the Break 3", SHOT_TYPE="3PT Field Goal"),
        _row(SHOT_ZONE_BASIC="Restricted Area"),
    ]
    ordered_zones = shot_chart_payload(out_of_order, "Regular Season")["zones"]
    assert ordered_zones[0]["zone"] == "Restricted Area"
    assert ordered_zones[1]["zone"] == "Above the Break 3"

    # 6. Truncation: 700 fabricated rows.
    many = [_row() for _ in range(700)]
    big_payload = shot_chart_payload(many, "Regular Season")
    assert len(big_payload["shots"]) == 600
    assert big_payload["truncated"] is True
    assert sum(z["attempts"] for z in big_payload["zones"]) == 700
    assert big_payload["summary"]["attempts"] == 700

    # 7. Params dict.
    p = shot_chart_params(2544, "2025-26", "Playoffs")
    assert p["ContextMeasure"] == "FGA"
    assert p["PlayerID"] == 2544
    assert p["TeamID"] == 0
    assert p["GameID"] == ""
    assert p["LeagueID"] == "00"
    assert p["SeasonType"] == "Playoffs"
    assert len(p) >= 30

    print("OK: shot chart payload keys, zone aggregation/order, truncation, and request params are correct")


if __name__ == "__main__":
    main()
