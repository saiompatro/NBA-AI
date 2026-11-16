"""Self-check for the league injury report and how predictions use it.

Run directly: python scripts/test_injury_report.py
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest import mock

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services import injury_report, league_analytics  # noqa: E402
from app.services.injury_news_watch import InjuryNewsWatch, _mentions_injury_phrase  # noqa: E402
from app.services.league_analytics import LeagueAnalyticsService, TEAM_BY_ABBR  # noqa: E402


def _item(name: str, status: str, team: dict | None = None, **details) -> dict:
    athlete = {"displayName": name}
    if team:
        athlete["team"] = team
    return {"status": status, "athlete": athlete, "shortComment": f"{name} update", "details": details}


FEED = {
    "injuries": [
        {
            "displayName": "Boston Celtics",
            "injuries": [
                _item("Jayson Tatum", "Out", {"abbreviation": "BOS"}, type="Achilles", side="Right",
                      returnDate="2027-01-10"),
                _item("Sam Hauser", "Day-To-Day", {"abbreviation": "BOS"}, type="Back"),
                _item("Bench Guy", "Out", {"abbreviation": "BOS"}),
            ],
        },
        # No abbreviation on the athlete: the group name has to resolve the team.
        {"displayName": "Golden State Warriors", "injuries": [_item("Stephen Curry", "Questionable")]},
        # ESPN's short code for a team whose NBA abbreviation differs.
        {"displayName": "Whatever", "injuries": [_item("Some Wizard", "Doubtful", {"abbreviation": "WSH"})]},
        {"displayName": "Seattle SuperSonics", "injuries": [_item("Ghost Player", "Out")]},
        "garbage",
    ]
}


def _report_with(payload) -> injury_report.InjuryReport:
    report = injury_report.InjuryReport(resolve_team=league_analytics._resolve_report_team)
    response = mock.Mock()
    response.json.return_value = payload
    with mock.patch.object(injury_report.requests, "get", return_value=response):
        report.refresh()
    return report


def test_feed_is_parsed_per_team_with_status_weights() -> None:
    parsed = injury_report.parse_injuries(FEED, league_analytics._resolve_report_team)
    assert set(parsed) == {"BOS", "GSW", "WAS"}, set(parsed)
    tatum = next(entry for entry in parsed["BOS"] if entry["player"] == "Jayson Tatum")
    assert tatum["weight"] == 1.0 and tatum["injury"] == "Right Achilles" and tatum["return_date"] == "2027-01-10"
    assert parsed["BOS"][-1]["player"] == "Sam Hauser" and parsed["BOS"][-1]["weight"] == 0.4
    assert parsed["GSW"][0]["weight"] == 0.5 and parsed["WAS"][0]["weight"] == 0.75
    assert injury_report.status_weight("Probable") == 0.0
    for junk in (None, [], {"injuries": None}, {"injuries": [{"injuries": [{"athlete": None}]}]}):
        assert injury_report.parse_injuries(junk) == {}


def test_names_match_across_accents_and_suffixes() -> None:
    same = injury_report.normalize_player_name
    assert same("Luka Dončić") == same("Luka Doncic")
    assert same("Jaren Jackson Jr.") == same("jaren jackson")
    assert same("De'Aaron Fox") == same("DeAaron Fox")


def test_failed_fetch_keeps_last_report_and_backs_off() -> None:
    report = _report_with(FEED)
    assert report.available() and len(report.for_team("bos")) == 3
    with mock.patch.object(injury_report.requests, "get", side_effect=requests.ConnectionError) as get:
        assert report.refresh(force=True) is True          # still holding the earlier report
        assert report.refresh() is True and get.call_count == 1  # and not hammering the feed
    empty = injury_report.InjuryReport()
    with mock.patch.object(injury_report.requests, "get", side_effect=requests.ConnectionError):
        assert empty.available() is False and empty.for_team("BOS") == [] and empty.all() == {}
    assert _report_with({"unexpected": True}).available() is False


def test_prediction_points_follow_status_and_games_already_missed() -> None:
    team = {**TEAM_BY_ABBR["BOS"], "wins": 6, "losses": 4}
    players = [
        {"player": "Jayson Tatum", "team": "BOS", "min": 36.0, "impact": 50.0, "gp": 10},
        {"player": "Sam Hauser", "team": "BOS", "min": 24.0, "impact": 20.0, "gp": 5},
        {"player": "Bench Guy", "team": "BOS", "min": 6.0, "impact": 5.0, "gp": 10},
        {"player": "Jayson Tatum", "team": "NYK", "min": 36.0, "impact": 50.0, "gp": 10},
    ]
    with mock.patch.object(league_analytics, "_INJURY_REPORT", _report_with(FEED)):
        service = LeagueAnalyticsService()
        out = service._reported_out_for_team(team, players)
        assert [row["player"] for row in out] == ["Jayson Tatum", "Sam Hauser"], out
        # Tatum: certain absence, played every game. Hauser: 0.4 chance x half the games played.
        assert [row["availability"] for row in out] == [1.0, 0.2], out
        expected = round((50.0 * 1.0 + 20.0 * 0.2) * league_analytics._IMPACT_TO_POINTS, 2)
        assert service._injury_points(out) == expected
        home_out, away_out, source = service._availability(team, TEAM_BY_ABBR["NYK"], players)
        assert source == injury_report.SOURCE_LABEL and len(home_out) == 2 and away_out == []
        listing = service.injuries("WSH")
        assert listing["available"] and [t["abbr"] for t in listing["teams"]] == ["WAS"]
        assert len(service.injuries()["teams"]) == 3 and service.injuries("XXX")["teams"] == []
    # Rows from the news fallback carry no availability and count in full.
    assert LeagueAnalyticsService._injury_points([{"impact": 10.0}]) == round(10 * league_analytics._IMPACT_TO_POINTS, 2)


def test_news_fallback_is_used_when_the_report_is_down() -> None:
    down = injury_report.InjuryReport()
    watch = InjuryNewsWatch()
    article = {"headline": "Boston Celtics star Jayson Tatum ruled out with knee soreness", "description": "", "source": "Wire",
               "published": ""}
    players = [{"player": "Jayson Tatum", "team": "BOS", "min": 36.0, "impact": 50.0}]
    with mock.patch.object(injury_report.requests, "get", side_effect=requests.ConnectionError), \
            mock.patch.object(league_analytics, "_INJURY_REPORT", down), \
            mock.patch.object(league_analytics, "_INJURY_WATCH", watch), \
            mock.patch("app.services.injury_news_watch.fetch_general_pool", return_value=[article]), \
            mock.patch("app.services.injury_news_watch.fetch_google_news", return_value=[]):
        service = LeagueAnalyticsService()
        home_out, away_out, source = service._availability(TEAM_BY_ABBR["BOS"], TEAM_BY_ABBR["NYK"], players)
        assert source == "news headlines" and [p["player"] for p in home_out] == ["Jayson Tatum"] and away_out == []
        # A different matchup straight afterwards must not inherit those alerts.
        with mock.patch("app.services.injury_news_watch.fetch_general_pool", return_value=[]):
            watch.refresh(team_terms=["Los Angeles Lakers", "LAL"], player_terms=[])
        assert watch.alerts() == []


def test_return_headlines_are_not_read_as_injuries() -> None:
    assert _mentions_injury_phrase("Tatum ruled out with ankle sprain")
    assert _mentions_injury_phrase("Embiid exits with back spasms")
    assert not _mentions_injury_phrase("Tatum returns from knee injury tonight")
    assert not _mentions_injury_phrase("Celtics bounce back with comeback win")


if __name__ == "__main__":
    test_feed_is_parsed_per_team_with_status_weights()
    test_names_match_across_accents_and_suffixes()
    test_failed_fetch_keeps_last_report_and_backs_off()
    test_prediction_points_follow_status_and_games_already_missed()
    test_news_fallback_is_used_when_the_report_is_down()
    test_return_headlines_are_not_read_as_injuries()
    print("OK: injury report parsing, caching, prediction weighting and the news fallback behave")
