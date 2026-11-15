"""Self-check that the tracked team table covers the whole league.

Run directly: python scripts/test_team_coverage.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.league_analytics import (  # noqa: E402
    ESPN_TEAM_CODES,
    SCHEDULE_TEAM_ALIASES,
    TEAM_BY_ABBR,
    TEAM_BY_ID,
    TRACKED_TEAMS,
    fallback_standings,
    normalize_team_abbr,
    seed_net_rating,
    seed_points,
)


def test_all_thirty_franchises_are_tracked() -> None:
    assert len(TRACKED_TEAMS) == len(TEAM_BY_ID) == len(TEAM_BY_ABBR) == 30
    for conference in ("Eastern", "Western"):
        seeds = sorted(team["seed"] for team in TRACKED_TEAMS if team["conference"] == conference)
        assert seeds == list(range(1, 16)), (conference, seeds)


def test_records_are_a_complete_82_game_season() -> None:
    assert all(team["wins"] + team["losses"] == 82 for team in TRACKED_TEAMS)
    # Every game has one winner, so league-wide wins must equal losses.
    assert sum(team["wins"] for team in TRACKED_TEAMS) == sum(team["losses"] for team in TRACKED_TEAMS) == 1230


def test_team_ids_match_the_bundled_nba_list() -> None:
    from nba_api.stats.static import teams as nba_static_teams

    official = {int(entry["id"]): entry["abbreviation"] for entry in nba_static_teams.get_teams()}
    assert {team["team_id"]: team["abbr"] for team in TRACKED_TEAMS} == official


def test_espn_codes_round_trip_to_nba_abbreviations() -> None:
    for abbr, code in ESPN_TEAM_CODES.items():
        assert abbr in TEAM_BY_ABBR
        assert normalize_team_abbr(code) == abbr
    assert set(SCHEDULE_TEAM_ALIASES.values()) <= set(TEAM_BY_ABBR)


def test_fallbacks_stay_sane_for_lottery_ranks() -> None:
    nets = [seed_net_rating(seed) for seed in range(1, 16)]
    points = [seed_points(seed) for seed in range(1, 16)]
    assert nets == sorted(nets, reverse=True) and points == sorted(points, reverse=True)
    assert nets[-1] >= -12.0 and points[-1] >= 95.0

    standings = fallback_standings()
    assert len(standings["east"]) == len(standings["west"]) == 15
    assert [row["rank"] for row in standings["east"]] == list(range(1, 16))
    assert standings["west"][14]["playoff_status"] == "Out"
    assert not standings["west"][14]["in_playoff_field"]


if __name__ == "__main__":
    test_all_thirty_franchises_are_tracked()
    test_records_are_a_complete_82_game_season()
    test_team_ids_match_the_bundled_nba_list()
    test_espn_codes_round_trip_to_nba_abbreviations()
    test_fallbacks_stay_sane_for_lottery_ranks()
    print("team coverage OK")
