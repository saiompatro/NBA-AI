"""Self-check for the head-to-head matchup-history pregame adjustment.

Run directly: python scripts/test_head_to_head.py
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

from app.services.league_analytics import (
    _H2H_CAP,
    _H2H_FULL_WEIGHT_GAMES,
    _H2H_MIN_GAMES,
    LeagueAnalyticsService,
    current_season,
    h2h_margin_edge,
    h2h_summary,
)


GAME_LOG_COLUMNS = ["GAME_ID", "GAME_DATE", "TEAM_ID", "TEAM_ABBREVIATION", "MATCHUP", "WL", "PTS"]


def _game_rows(game_id: str, date: str, home_abbr: str, away_abbr: str, home_pts: int, away_pts: int) -> list[list]:
    """One row per side of a game, matching the real leaguegamelog shape."""
    home_wl = "W" if home_pts > away_pts else "L"
    away_wl = "L" if home_pts > away_pts else "W"
    return [
        [game_id, date, 1, home_abbr, f"{home_abbr} vs. {away_abbr}", home_wl, home_pts],
        [game_id, date, 2, away_abbr, f"{away_abbr} @ {home_abbr}", away_wl, away_pts],
    ]


def main() -> None:
    # --- h2h_margin_edge: pure-function behavior -----------------------------------
    assert h2h_margin_edge(None, 8) == 0.0
    assert h2h_margin_edge(10.0, _H2H_MIN_GAMES - 1) == 0.0, "below the games floor must be zero"
    assert h2h_margin_edge(0.0, 8) == 0.0, "a neutral history should produce a neutral edge"

    assert h2h_margin_edge(6.0, _H2H_FULL_WEIGHT_GAMES) > 0, "a positive avg margin should be a positive edge"
    assert h2h_margin_edge(-6.0, _H2H_FULL_WEIGHT_GAMES) < 0, "a negative avg margin should be a negative edge"

    # Shrinkage: a thinner sample produces a smaller-magnitude edge for the same margin.
    thin = h2h_margin_edge(4.0, 3)
    full = h2h_margin_edge(4.0, _H2H_FULL_WEIGHT_GAMES)
    assert 0 < thin < full, "a thin sample should be shrunk toward zero relative to a full-weight sample"

    # Weight saturates at _H2H_FULL_WEIGHT_GAMES - more games shouldn't add more weight.
    saturated = h2h_margin_edge(4.0, _H2H_FULL_WEIGHT_GAMES + 4)
    assert abs(saturated - full) < 1e-9, "weight must saturate at _H2H_FULL_WEIGHT_GAMES"

    # Extreme margins clamp to the cap in both directions.
    assert h2h_margin_edge(500.0, _H2H_FULL_WEIGHT_GAMES) == _H2H_CAP
    assert h2h_margin_edge(-500.0, _H2H_FULL_WEIGHT_GAMES) == -_H2H_CAP

    # --- h2h_summary: plain-English wording -----------------------------------------
    assert "No recent meetings" in h2h_summary("CLE", "DET", 0, 0, None, 0)

    leader_summary = h2h_summary("CLE", "DET", 4, 3, 2.4, 7)
    assert "CLE" in leader_summary and "won 4" in leader_summary, "must name the correct leader"

    small_sample_summary = h2h_summary("CLE", "DET", 2, 1, 3.0, 3)
    assert "small sample" in small_sample_summary.lower(), "must caveat a thin sample"
    full_sample_summary = h2h_summary("CLE", "DET", 5, 1, 3.0, _H2H_FULL_WEIGHT_GAMES)
    assert "small sample" not in full_sample_summary.lower(), "must not caveat a full-weight sample"

    # --- head_to_head(): end-to-end against a stubbed leaguegamelog fetch ------------
    service = LeagueAnalyticsService()
    season = current_season()

    rows: list[list] = []
    # Two meetings in Cleveland (CLE home), two in Detroit (DET home).
    rows += _game_rows("0022500001", "2026-01-05", "CLE", "DET", 118, 110)
    rows += _game_rows("0022500002", "2026-02-10", "CLE", "DET", 105, 112)
    rows += _game_rows("0022500003", "2026-03-01", "DET", "CLE", 101, 99)
    rows += _game_rows("0022500004", "2026-03-20", "DET", "CLE", 108, 115)
    current_regular_frame = pd.DataFrame(rows, columns=GAME_LOG_COLUMNS)

    def fake_league_game_log(season_arg: str, season_type_arg: str) -> pd.DataFrame:
        if season_arg == season and season_type_arg == "Regular Season":
            return current_regular_frame
        return pd.DataFrame(columns=GAME_LOG_COLUMNS)

    # Instance attribute shadows the class method (bypassing frozen-dataclass __setattr__),
    # so no real network call happens.
    object.__setattr__(service, "_league_game_log", fake_league_game_log)

    result = service.head_to_head("DET", "CLE")
    assert result["ok"] is True
    assert result["games_found"] == 4
    assert result["record"]["home_wins"] + result["record"]["away_wins"] == 4
    assert result["home_court_record"]["games"] == 2

    # Hand-computed mean of (CLE pts - DET pts) across all 4 meetings, both arenas.
    expected_avg = ((118 - 110) + (105 - 112) + (99 - 101) + (115 - 108)) / 4
    assert abs(result["avg_margin_home"] - expected_avg) < 1e-9

    dates = [game["date"] for game in result["games"]]
    assert dates == sorted(dates, reverse=True), "games must be sorted most-recent-first"

    for game in result["games"]:
        for key in (
            "game_id", "date", "season", "season_type", "home", "away",
            "home_pts", "away_pts", "margin", "winner", "at_home", "label",
        ):
            assert key in game, f"missing key {key!r} on a games[] entry"
        assert game["margin"] == game["home_pts"] - game["away_pts"]
        assert game["winner"] in ("CLE", "DET")

    assert result["margin_edge"] == round(h2h_margin_edge(result["avg_margin_home"], result["games_found"]), 2), (
        "response margin_edge must not drift from the pure function"
    )

    # Swapping home/away flips the sign of both the average margin and the edge.
    swapped = service.head_to_head("CLE", "DET")
    assert abs(swapped["avg_margin_home"] + result["avg_margin_home"]) < 1e-9
    assert abs(swapped["margin_edge"] + result["margin_edge"]) < 1e-9 or (
        swapped["margin_edge"] == 0.0 and result["margin_edge"] == 0.0
    )

    # Every combination empty -> a clean, non-raising failure shape.
    object.__setattr__(service, "_league_game_log", lambda *_args: pd.DataFrame(columns=GAME_LOG_COLUMNS))
    empty_result = service.head_to_head("DET", "CLE")
    assert empty_result["ok"] is False
    assert empty_result["margin_edge"] == 0.0
    assert empty_result["games"] == []

    # Unrecognized team abbreviation -> a clean failure, never a raise.
    unknown_result = service.head_to_head("ZZZ", "CLE")
    assert unknown_result["ok"] is False

    print("OK: head-to-head margin edge is shrunk/capped/signed correctly, and head_to_head() reconstructs real meetings without drift or raising")


if __name__ == "__main__":
    main()
