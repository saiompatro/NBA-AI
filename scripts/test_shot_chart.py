"""Self-check for the player shot-chart zone aggregation (real shot locations plus
zone FG% vs. league average).

Run directly: python scripts/test_shot_chart.py
Add --live to also hit the real stats.nba.com endpoint for one known player id.
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

from app.services.league_analytics import normalize_shot_location, shot_zone_summary


def _shot(zone: str, made: bool) -> dict:
    return {"SHOT_ZONE_BASIC": zone, "SHOT_ATTEMPTED_FLAG": 1, "SHOT_MADE_FLAG": 1 if made else 0}


def _league(zone: str, fga: int, fgm: int) -> dict:
    return {"SHOT_ZONE_BASIC": zone, "FGA": fga, "FGM": fgm}


def test_normalize_shot_location_stays_in_bounds() -> None:
    assert normalize_shot_location(0, 0) == (0.0, 0.0)
    assert normalize_shot_location(-999, -999) == (-250.0, -47.5), "out-of-bounds x/y must clamp to court edges"
    assert normalize_shot_location(999, 999) == (250.0, 422.5)


def test_zone_summary_aggregates_makes_and_attempts() -> None:
    shots = [_shot("Restricted Area", True), _shot("Restricted Area", True), _shot("Restricted Area", False)]
    league = [_league("Restricted Area", 100, 65)]
    zones = shot_zone_summary(shots, league)
    assert len(zones) == 1
    zone = zones[0]
    assert zone["zone"] == "Restricted Area"
    assert zone["fga"] == 3 and zone["fgm"] == 2
    assert zone["fg_pct"] == round(100 * 2 / 3, 1)
    assert zone["league_fg_pct"] == 65.0
    assert zone["share"] == 100.0, "a single-zone shot log is 100% of that player's attempts"


def test_zone_summary_merges_corner_three_sides() -> None:
    shots = [_shot("Left Corner 3", True), _shot("Right Corner 3", False)]
    league = [_league("Left Corner 3", 50, 20), _league("Right Corner 3", 50, 20)]
    zones = shot_zone_summary(shots, league)
    assert len(zones) == 1 and zones[0]["zone"] == "Corner 3", "left/right corner 3 must merge into one zone"
    assert zones[0]["fga"] == 2 and zones[0]["fgm"] == 1


def test_zone_summary_delta_reflects_over_or_under_performance() -> None:
    shots = [_shot("Mid-Range", True), _shot("Mid-Range", True)]
    league = [_league("Mid-Range", 100, 40)]
    zone = shot_zone_summary(shots, league)[0]
    assert zone["fg_pct"] == 100.0
    assert zone["delta"] == round(100.0 - 40.0, 1), "delta is player FG% minus league FG% in the same zone"


def test_zone_summary_ignores_unattempted_zones_and_unknown_labels() -> None:
    shots = [_shot("Backcourt", True)]
    assert shot_zone_summary(shots, []) == [], "zones outside SHOT_ZONE_LABELS must not appear"
    assert shot_zone_summary([], []) == [], "empty input must return an empty list, not crash"


def main() -> None:
    test_normalize_shot_location_stays_in_bounds()
    test_zone_summary_aggregates_makes_and_attempts()
    test_zone_summary_merges_corner_three_sides()
    test_zone_summary_delta_reflects_over_or_under_performance()
    test_zone_summary_ignores_unattempted_zones_and_unknown_labels()
    print("OK: shot-chart zone aggregation is internally consistent")

    if "--live" in sys.argv:
        from app.services.league_analytics import LeagueAnalyticsService, current_season

        service = LeagueAnalyticsService()
        result = service.player_shot_chart(2544, current_season())  # LeBron James
        print(f"live check: ok={result['ok']} season_type={result['season_type']} "
              f"fga={result['totals']['fga']} zones={len(result['zones'])}")


if __name__ == "__main__":
    main()
