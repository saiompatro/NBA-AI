"""Self-check for the shot chart / shot-zone efficiency profile (court coordinate
mapping, zone summarization, and the plain-English blurb).

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

from app.services.league_analytics import (
    _SHOT_ZONE_ORDER,
    court_point,
    shot_chart_blurb,
    shot_zone_summary,
)


def test_court_point() -> None:
    # The rim sits at LOC_X=0, LOC_Y=0.
    assert court_point(0, 0) == (250.0, 422.5)

    # The baseline (LOC_Y=-47.5) maps to the bottom of the viewBox.
    assert court_point(0, -47.5) == (250.0, 470.0)

    # Half court (LOC_Y=422.5) maps to the top of the viewBox.
    assert court_point(0, 422.5) == (250.0, 0.0)

    # Sidelines map to the left/right edges.
    assert court_point(-250, 0) == (0.0, 422.5)
    assert court_point(250, 0) == (500.0, 422.5)

    # A backcourt heave clamps inside the viewBox instead of escaping it.
    x, y = court_point(-400, 600)
    assert 0.0 <= x <= 500.0
    assert 0.0 <= y <= 470.0

    # y is inverted: farther from the hoop means a *smaller* y (closer to the top).
    near_x, near_y = court_point(0, 50)
    far_x, far_y = court_point(0, 300)
    assert far_y < near_y, "a shot farther from the hoop should have a smaller y"


def test_shot_zone_summary() -> None:
    assert shot_zone_summary([], []) == []

    shots = [
        {"zone": "Restricted Area", "made": True},
        {"zone": "Restricted Area", "made": True},
        {"zone": "Restricted Area", "made": True},
        {"zone": "Restricted Area", "made": False},
        {"zone": "Backcourt", "made": True},
    ]
    league_rows = [
        {"SHOT_ZONE_BASIC": "Restricted Area", "FGM": 100, "FGA": 1000},
        {"SHOT_ZONE_BASIC": "Restricted Area", "FGM": 8, "FGA": 10},
    ]
    zones = shot_zone_summary(shots, league_rows)

    # Backcourt is excluded entirely - both from the output and the frequency denominator.
    assert [zone["zone"] for zone in zones] == ["Restricted Area"]
    row = zones[0]
    assert row["fga"] == 4
    assert row["fgm"] == 3
    assert row["fg_pct"] == 75.0
    # Frequency is out of the *qualifying* shots only (4), not the raw list (5).
    assert row["freq"] == 100.0

    # League averages aggregate attempt-weighted: (100+8)/(1000+10) ~= 10.7%, not the
    # ~45% a naive mean of the two rows' percentages would give.
    assert abs(row["league_pct"] - 10.69) < 0.05
    assert row["diff"] == round(75.0 - row["league_pct"], 1)
    assert row["diff"] > 0, "beating the league rate should give a positive diff"

    # Rows come back in the canonical zone order and omit zero-attempt zones.
    ordered_shots = [{"zone": zone, "made": True} for zone in reversed(_SHOT_ZONE_ORDER)]
    ordered = shot_zone_summary(ordered_shots, [])
    assert [zone["zone"] for zone in ordered] == _SHOT_ZONE_ORDER

    # fga == 0 never raises / never divides by zero.
    below = shot_zone_summary(
        [{"zone": "Mid-Range", "made": False}] * 3,
        [{"SHOT_ZONE_BASIC": "Mid-Range", "FGM": 500, "FGA": 1000}],
    )
    assert below[0]["fg_pct"] == 0.0
    assert below[0]["diff"] < 0, "trailing the league rate should give a negative diff"


def test_shot_chart_blurb() -> None:
    assert shot_chart_blurb([], {}) == ""

    # Names the best zone and says "above" when the player beats league average.
    zones = [
        {"zone": "Restricted Area", "fga": 40, "fg_pct": 68.9, "diff": 4.7},
        {"zone": "Mid-Range", "fga": 20, "fg_pct": 38.0, "diff": -2.0},
    ]
    blurb = shot_chart_blurb(zones, {})
    assert "Restricted Area" in blurb
    assert "above" in blurb

    # Says "below" when the player trails everywhere.
    losing_zones = [
        {"zone": "Restricted Area", "fga": 40, "fg_pct": 50.0, "diff": -3.0},
        {"zone": "Mid-Range", "fga": 20, "fg_pct": 30.0, "diff": -8.0},
    ]
    blurb = shot_chart_blurb(losing_zones, {})
    assert "Restricted Area" in blurb  # least-bad zone, still the "best"
    assert "below" in blurb

    # A tiny-sample zone with an absurd diff is not named as the best zone.
    with_tiny_sample = [
        {"zone": "Left Corner 3", "fga": 1, "fg_pct": 100.0, "diff": 55.0},
        {"zone": "Restricted Area", "fga": 40, "fg_pct": 68.9, "diff": 4.7},
    ]
    blurb = shot_chart_blurb(with_tiny_sample, {})
    assert "Left Corner 3" not in blurb
    assert "Restricted Area" in blurb


def main() -> None:
    test_court_point()
    test_shot_zone_summary()
    test_shot_chart_blurb()
    print(
        "OK: shot chart court-point mapping is correctly inverted and clamped, zone "
        "summary aggregates league averages attempt-weighted and excludes backcourt "
        "heaves, and the blurb ignores tiny-sample zones"
    )


if __name__ == "__main__":
    main()
