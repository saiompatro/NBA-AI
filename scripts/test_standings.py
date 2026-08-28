"""Self-check for league-wide (30-team) standings normalization (leaguestandingsv3).

Run directly: python scripts/test_standings.py
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

from app.services.league_analytics import (
    fallback_standings,
    format_games_back,
    normalize_standings_rows,
    standings_playoff_status,
    standings_streak_label,
)

_EXPECTED_ROW_KEYS = {
    "team_id", "abbr", "team", "slug", "logo", "conference", "division",
    "rank", "division_rank", "wins", "losses", "record", "pct", "gb",
    "conf_record", "home", "road", "last10", "streak", "pts_pg",
    "opp_pts_pg", "diff_pg", "playoff_status", "in_playoff_field",
}

# Real NBA team ids (Boston, New York, Denver, Oklahoma City) so `all_team_meta()`
# resolves them without a network call (it's built from nba_api's bundled static list).
_BOS = 1610612738
_NYK = 1610612752
_DEN = 1610612743
_OKC = 1610612760
_BOGUS_TEAM_ID = 999999999


def _row(**overrides) -> dict:
    base = {
        "TeamID": _BOS,
        "Conference": "East",
        "Division": "Atlantic",
        "PlayoffRank": 2,
        "DivisionRank": 1,
        "WINS": 56,
        "LOSSES": 26,
        "WinPCT": 0.683,
        "Record": "56-26",
        "HOME": "31-10",
        "ROAD": "25-16",
        "L10": "7-3",
        "CurrentStreak": 3,
        "strCurrentStreak": "W 3",
        "ConferenceGamesBack": 4.0,
        "ConferenceRecord": "36-16",
        "ClinchedPlayoffBirth": 0,
        "EliminatedConference": 0,
        "PointsPG": 118.4,
        "OppPointsPG": 112.1,
        "DiffPointsPG": 6.3,
    }
    base.update(overrides)
    return base


def test_streak_label() -> None:
    assert standings_streak_label(3) == "W3", "positive int streak"
    assert standings_streak_label(-2) == "L2", "negative int streak"
    assert standings_streak_label(0, "W 3") == "W3", "zero int falls back to strCurrentStreak, spaces stripped"
    assert standings_streak_label(None, None) == "-", "no usable input must not raise"
    assert standings_streak_label("", "") == "-", "empty strings must not raise"
    assert standings_streak_label("garbage", "also garbage") == "-", "unparseable input must not raise"


def test_playoff_status() -> None:
    assert standings_playoff_status(4, 1, 0) == "Clinched", "clinched flag wins even inside the playoff-rank band"
    assert standings_playoff_status(12, 0, 1) == "Eliminated", "eliminated flag takes priority over rank"
    assert standings_playoff_status(8, 0, 0) == "Play-In", "rank 7-10 is play-in"
    assert standings_playoff_status(3, 0, 0) == "Playoff spot", "rank 1-6 is a playoff spot"
    assert standings_playoff_status(13, 0, 0) == "Out", "rank 11-15 is out"
    assert standings_playoff_status(None, None, None) == "", "missing rank must not raise"
    assert standings_playoff_status("not-a-rank", "N", "N") == "", "garbage rank must not raise"


def test_format_games_back() -> None:
    assert format_games_back(0) == "-"
    assert format_games_back(-3.5) == "-"
    assert format_games_back(4.0) == "4.0"
    assert format_games_back("garbage") == "-"
    assert format_games_back(None) == "-"


def test_normalize_standings_rows() -> None:
    records = [
        _row(TeamID=_BOS, Conference="East", PlayoffRank=2, WinPCT=0.683),
        _row(TeamID=_NYK, Conference="Eastern", PlayoffRank=1, WinPCT=0.720, L10=None),
        _row(TeamID=_DEN, Conference="West", PlayoffRank=3, WinPCT=0.610, WINS="54", LOSSES="28"),
        _row(TeamID=_OKC, Conference="Western", PlayoffRank=1, WinPCT=0.780),
        _row(TeamID=_BOGUS_TEAM_ID, Conference="East", PlayoffRank=5, WinPCT=0.5),
    ]
    grouped = normalize_standings_rows(records)

    assert set(grouped) == {"east", "west"}
    assert len(grouped["east"]) == 2, "unrecognized TeamID must be dropped, not crash"
    assert len(grouped["west"]) == 2

    east_ids = [row["team_id"] for row in grouped["east"]]
    assert east_ids == [_NYK, _BOS], "east must be sorted by PlayoffRank ascending"

    west_ids = [row["team_id"] for row in grouped["west"]]
    assert west_ids == [_OKC, _DEN], "west must be sorted by PlayoffRank ascending"

    for conference_rows in grouped.values():
        for row in conference_rows:
            assert set(row) == _EXPECTED_ROW_KEYS, f"row for {row.get('abbr')} has an unexpected key set"

    bos_row = next(row for row in grouped["east"] if row["team_id"] == _BOS)
    assert bos_row["abbr"] == "BOS", "abbr must resolve via all_team_meta()"
    assert bos_row["team"] == "Boston Celtics"

    nyk_row = next(row for row in grouped["east"] if row["team_id"] == _NYK)
    assert nyk_row["last10"] == "-", "a None L10 must not raise and must fall back to a placeholder"

    den_row = next(row for row in grouped["west"] if row["team_id"] == _DEN)
    assert den_row["wins"] == 54 and den_row["losses"] == 28, "string-typed WINS/LOSSES must coerce cleanly"


def test_fallback_standings() -> None:
    grouped = fallback_standings()
    assert len(grouped["east"]) == 8, "fallback covers exactly the 8 tracked Eastern seeds"
    assert len(grouped["west"]) == 8, "fallback covers exactly the 8 tracked Western seeds"
    for conference_rows in grouped.values():
        for row in conference_rows:
            assert set(row) == _EXPECTED_ROW_KEYS, "fallback rows must match the normalized-row shape exactly"


def main() -> None:
    checks = [
        test_streak_label,
        test_playoff_status,
        test_format_games_back,
        test_normalize_standings_rows,
        test_fallback_standings,
    ]
    failures = []
    for check in checks:
        try:
            check()
        except AssertionError as exc:
            failures.append(f"{check.__name__}: {exc}")

    if failures:
        print("FAIL:")
        for failure in failures:
            print(f"  - {failure}")
        raise SystemExit(1)

    print("OK: standings normalization/fallback covers streak labels, playoff status, "
          "games-back formatting, east/west split + sort, malformed-row tolerance, and "
          "shape parity between the real and fallback code paths")


if __name__ == "__main__":
    main()
