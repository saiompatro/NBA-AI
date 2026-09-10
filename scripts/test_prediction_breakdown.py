"""Self-check for the "why this pick" margin waterfall on the pre-game prediction.

Run directly: python scripts/test_prediction_breakdown.py
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

from app.services.league_analytics import margin_breakdown_rows


def main() -> None:
    rows = margin_breakdown_rows(
        home_abbr="CLE", away_abbr="DET",
        net_edge=3.0, hca=2.5,
        home_injury_pts=1.0, away_injury_pts=2.0,
        rest_edge=0.5, form_edge=0.8, split_edge=-0.3, ff_edge=1.2,
    )

    # Every input becomes exactly one labeled, home-signed row.
    labels = [row["label"] for row in rows]
    assert labels == [
        "Team net rating", "Home court", "Availability",
        "Rest / schedule", "Recent form", "Home/road split", "Four factors",
    ]

    # The rows must sum to the same total `game_prediction` computes from these inputs
    # (net_edge + hca - home_injury_pts + away_injury_pts + rest_edge + form_edge + split_edge + ff_edge).
    expected_total = 3.0 + 2.5 - 1.0 + 2.0 + 0.5 + 0.8 - 0.3 + 1.2
    total = sum(row["points"] for row in rows)
    assert abs(total - expected_total) < 1e-9, f"rows must sum to the expected margin, got {total} vs {expected_total}"

    # Availability is the one row that recombines two raw inputs (away hurts home
    # less than home being hurt): the sign flips when the injury burden flips.
    availability = next(row for row in rows if row["label"] == "Availability")
    assert availability["points"] > 0, "an injury edge favoring the home team should be positive"

    flipped = margin_breakdown_rows(
        home_abbr="CLE", away_abbr="DET",
        net_edge=0, hca=0, home_injury_pts=2.0, away_injury_pts=1.0,
        rest_edge=0, form_edge=0, split_edge=0, ff_edge=0,
    )
    flipped_availability = next(row for row in flipped if row["label"] == "Availability")
    assert flipped_availability["points"] < 0, "an injury edge favoring the away team should be negative"

    # Every input at zero (a dead-even matchup with no home court) yields an all-zero
    # breakdown that still sums to zero.
    neutral = margin_breakdown_rows(
        home_abbr="CLE", away_abbr="DET",
        net_edge=0, hca=0, home_injury_pts=0, away_injury_pts=0,
        rest_edge=0, form_edge=0, split_edge=0, ff_edge=0,
    )
    assert all(row["points"] == 0 for row in neutral)

    # Signs flip when home/away are swapped for every non-zero edge (the breakdown
    # stays home-relative, not winner-relative).
    swapped = margin_breakdown_rows(
        home_abbr="DET", away_abbr="CLE",
        net_edge=-3.0, hca=2.5,
        home_injury_pts=2.0, away_injury_pts=1.0,
        rest_edge=-0.5, form_edge=-0.8, split_edge=0.3, ff_edge=-1.2,
    )
    for original, flip in zip(rows, swapped):
        if original["label"] == "Home court":
            continue  # home-court is a fixed constant, not a team-relative edge
        assert abs(original["points"] + flip["points"]) < 1e-9, original["label"]

    print("OK: margin breakdown rows are labeled, sum to the expected margin, sign-correct, and home-relative")


if __name__ == "__main__":
    main()
