from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from math import exp
from pathlib import Path
from typing import Any

import pandas as pd
import requests
import urllib3
from nba_api.stats.library.http import NBAStatsHTTP

from app.services import news_sources
from app.services.injury_news_watch import InjuryNewsWatch


urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


# ---------------------------------------------------------------------------
# Pre-game ("normal") prediction calibration
# ---------------------------------------------------------------------------
# The pre-game model maps team strength to a win probability via:
#     expected_home_margin = (home_net - away_net) + home_court_advantage
#                            - home_injury_points + away_injury_points
#     P(home win)          = sigmoid(expected_home_margin / scale)
#
# `home_court_advantage` and `scale` are *fit against real game results* by
# scripts/calibrate_pregame.py and written to data/pregame_calibration.json.
# The defaults below are standard basketball-analytics values so the model
# still works sensibly before calibration has ever been run.
_CALIBRATION_PATH = Path("data/pregame_calibration.json")
_DEFAULT_CALIBRATION = {"home_court_advantage": 2.8, "scale": 11.5}

# Injury adjustment: convert a player's season IMPACT score into points of
# game margin, capped so a single team can never swing more than a few points.
_IMPACT_TO_POINTS = 0.12       # a ~30-impact star out ≈ 3.6 pts of margin
_INJURY_POINTS_CAP = 7.0       # hard cap on total margin swing per team
_INJURY_MIN_MINUTES = 18.0     # only rotation players move the needle

# Shared, news-driven injury watcher reused across pre-game predictions.
# (LeagueAnalyticsService is a frozen dataclass, so this lives at module scope.)
_INJURY_WATCH = InjuryNewsWatch()

# Rest / schedule-fatigue adjustment. Public win-probability models (FiveThirtyEight's
# NBA Elo, Inpredictable) price in rest advantage and back-to-backs; ours didn't, even
# though the ESPN scoreboard we already poll for `upcoming_games` is enough to derive it.
_REST_LOOKBACK_DAYS = 6     # how many days back to search for a team's last game
_REST_DAYS_CAP = 3          # rest beyond this stops helping (diminishing returns)
_REST_POINTS_PER_DAY = 0.5  # each extra day of rest edge is worth ~0.5 pts of margin
_BACK_TO_BACK_PENALTY = 1.5  # extra fatigue penalty for 0 days rest (2nd night of a b2b)

# Recent-form (momentum) adjustment. `last10` was already computed and shown to users
# as a "why we picked this team" factor, but it never actually moved the probability -
# only season-long net rating did. Public models (538, Vegas-implied) weight recent
# form on top of season strength since hot/cold streaks and lineup changes drift away
# from the full-season number. Keep the swing small and capped: this is a nudge on top
# of net rating, not a replacement for it.
_FORM_POINTS_PER_WIN = 0.3  # each extra win (out of 10) above/below the opponent's
_FORM_POINTS_CAP = 2.0      # hard cap on total margin swing from recent form

# Home/road split adjustment. We priced the blended season net rating identically for
# both sides, but teams play differently at home vs. on the road (Inpredictable and
# NBA.com Stats both lead with location-split ratings for this reason). Blend a slice
# of the home-only/road-only net rating on top of the season number instead of
# replacing it, since splits are noisier (smaller sample) than the full-season figure.
_HOME_ROAD_SPLIT_WEIGHT = 0.35  # how much of the location-split delta feeds the margin
_HOME_ROAD_SPLIT_CAP = 4.0      # hard cap on total margin swing from the split

# Four-factors adjustment. `_advanced_team_stats` already pulls eFG% and TOV% (two of
# Dean Oliver's Four Factors) for the team-profile pages, but game_prediction ignored
# them and leaned on net rating alone. Cleaning the Glass and NBA.com Advanced Stats
# both lead with these per-possession efficiency splits because they isolate *how* a
# team scores/protects the ball - a dimension season net rating blurs together. Keep
# the swing small: this refines the pick, it doesn't replace net rating.
_FOUR_FACTORS_EFG_WEIGHT = 0.4  # each 1pt of eFG% edge is worth ~0.4 pts of margin
_FOUR_FACTORS_TOV_WEIGHT = 0.5  # each 1pt of TOV% edge (lower is better) is worth ~0.5 pts
_FOUR_FACTORS_CAP = 3.0         # hard cap on total margin swing from shooting/ballhandling

# Clutch-time (last 5 min, score within 5 pts) team performance. NBA.com Stats' own
# "Clutch" tab and Cleaning the Glass both lead with this split because a team's
# full-game net rating can hide who actually closes games out - our team profiles
# had every other per-possession cut (four factors, home/road) but not this one.
_CLUTCH_TIME = "Last 5 Minutes"
_CLUTCH_POINT_DIFF = "5"


@lru_cache(maxsize=1)
def load_pregame_calibration() -> dict[str, float]:
    """Load fitted home-court / scale constants, falling back to defaults."""
    try:
        data = json.loads(_CALIBRATION_PATH.read_text())
        scale = float(data.get("scale", _DEFAULT_CALIBRATION["scale"]))
        return {
            "home_court_advantage": float(
                data.get("home_court_advantage", _DEFAULT_CALIBRATION["home_court_advantage"])
            ),
            "scale": scale if scale > 0 else _DEFAULT_CALIBRATION["scale"],
        }
    except Exception:
        return dict(_DEFAULT_CALIBRATION)


POSITIVE_WORDS = {
    "win",
    "wins",
    "advance",
    "advances",
    "return",
    "dominant",
    "surge",
    "clutch",
    "healthy",
    "star",
    "breakout",
    "historic",
    "leads",
}
NEGATIVE_WORDS = {
    "injury",
    "injured",
    "out",
    "loss",
    "lose",
    "doubt",
    "questionable",
    "suspended",
    "struggle",
    "concern",
    "eliminated",
}

PLAYOFF_SEEDS_2026 = [
    {"conference": "Eastern", "seed": 1, "team": "Detroit Pistons", "abbr": "DET", "team_id": 1610612765, "wins": 60, "losses": 22, "primary": "#1d428a", "secondary": "#c8102e"},
    {"conference": "Eastern", "seed": 2, "team": "Boston Celtics", "abbr": "BOS", "team_id": 1610612738, "wins": 56, "losses": 26, "primary": "#007a33", "secondary": "#ba9653"},
    {"conference": "Eastern", "seed": 3, "team": "New York Knicks", "abbr": "NYK", "team_id": 1610612752, "wins": 53, "losses": 29, "primary": "#006bb6", "secondary": "#f58426"},
    {"conference": "Eastern", "seed": 4, "team": "Cleveland Cavaliers", "abbr": "CLE", "team_id": 1610612739, "wins": 52, "losses": 30, "primary": "#6f263d", "secondary": "#ffb81c"},
    {"conference": "Eastern", "seed": 5, "team": "Toronto Raptors", "abbr": "TOR", "team_id": 1610612761, "wins": 46, "losses": 36, "primary": "#ce1141", "secondary": "#000000"},
    {"conference": "Eastern", "seed": 6, "team": "Atlanta Hawks", "abbr": "ATL", "team_id": 1610612737, "wins": 46, "losses": 36, "primary": "#e03a3e", "secondary": "#c1d32f"},
    {"conference": "Eastern", "seed": 7, "team": "Philadelphia 76ers", "abbr": "PHI", "team_id": 1610612755, "wins": 45, "losses": 37, "primary": "#006bb6", "secondary": "#ed174c"},
    {"conference": "Eastern", "seed": 8, "team": "Orlando Magic", "abbr": "ORL", "team_id": 1610612753, "wins": 45, "losses": 37, "primary": "#0077c0", "secondary": "#c4ced4"},
    {"conference": "Western", "seed": 1, "team": "Oklahoma City Thunder", "abbr": "OKC", "team_id": 1610612760, "wins": 64, "losses": 18, "primary": "#007ac1", "secondary": "#ef3b24"},
    {"conference": "Western", "seed": 2, "team": "San Antonio Spurs", "abbr": "SAS", "team_id": 1610612759, "wins": 62, "losses": 20, "primary": "#c4ced4", "secondary": "#000000"},
    {"conference": "Western", "seed": 3, "team": "Denver Nuggets", "abbr": "DEN", "team_id": 1610612743, "wins": 54, "losses": 28, "primary": "#0e2240", "secondary": "#fec524"},
    {"conference": "Western", "seed": 4, "team": "Los Angeles Lakers", "abbr": "LAL", "team_id": 1610612747, "wins": 53, "losses": 29, "primary": "#552583", "secondary": "#fdb927"},
    {"conference": "Western", "seed": 5, "team": "Houston Rockets", "abbr": "HOU", "team_id": 1610612745, "wins": 52, "losses": 30, "primary": "#ce1141", "secondary": "#000000"},
    {"conference": "Western", "seed": 6, "team": "Minnesota Timberwolves", "abbr": "MIN", "team_id": 1610612750, "wins": 49, "losses": 33, "primary": "#0c2340", "secondary": "#78be20"},
    {"conference": "Western", "seed": 7, "team": "Portland Trail Blazers", "abbr": "POR", "team_id": 1610612757, "wins": 42, "losses": 40, "primary": "#e03a3e", "secondary": "#000000"},
    {"conference": "Western", "seed": 8, "team": "Phoenix Suns", "abbr": "PHX", "team_id": 1610612756, "wins": 45, "losses": 37, "primary": "#1d1160", "secondary": "#e56020"},
]

TEAM_BY_ID = {team["team_id"]: team for team in PLAYOFF_SEEDS_2026}
TEAM_BY_ABBR = {team["abbr"]: team for team in PLAYOFF_SEEDS_2026}
ESPN_TEAM_CODES = {"NYK": "ny", "SAS": "sa", "PHX": "phx"}
SCHEDULE_TEAM_ALIASES = {"NY": "NYK", "SA": "SAS"}


@dataclass(frozen=True)
class LeagueAnalyticsService:
    timeout: int = 5

    def model_performance(self) -> dict[str, Any]:
        """Backtest transparency for the pre-game model (a la 538/Inpredictable).

        `scripts/calibrate_pregame.py` already fits home-court-advantage/scale
        against real results and writes accuracy + log loss to
        `data/pregame_calibration.json` — it just never made it past the
        per-prediction `calibration` field into a page a user can check without
        running a matchup first.
        """
        try:
            data = json.loads(_CALIBRATION_PATH.read_text())
        except Exception:
            data = {}
        return {
            "calibrated": bool(data),
            "accuracy": data.get("fit_accuracy"),
            "log_loss": data.get("fit_log_loss"),
            "games_backtested": data.get("games_used"),
            "seasons": data.get("seasons", []),
            "fit_at": data.get("fit_at"),
            "home_court_advantage": data.get("home_court_advantage", _DEFAULT_CALIBRATION["home_court_advantage"]),
            "scale": data.get("scale", _DEFAULT_CALIBRATION["scale"]),
            "baseline_home_win_rate": 0.54,
            "inputs": [
                "team net rating",
                "injuries (news + play-by-play)",
                "rest / back-to-back fatigue",
                "recent form (last-10)",
                "home/road net rating split",
                "four factors (eFG%, TOV%)",
                "news sentiment (context only, not scored)",
            ],
        }

    def overview(self) -> dict[str, Any]:
        season = current_season()
        news = self._aggregated_news()
        players = self.playoff_players(season, news)
        teams = self.playoff_teams(season, news)
        return {
            "season": season,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "playoff_table": fallback_playoff_table(),
            "upcoming_games": self.upcoming_games(),
            "players": players,
            "top_players": sorted(players, key=lambda row: row.get("impact", 0), reverse=True)[:12],
            "teams": teams,
            "team_form": teams,
            "leaders": self.leaders_from_players(players),
            "sentiment": self.sentiment_summary(news),
            "sources": [
                "nba_api live scoreboard/play-by-play",
                "NBA Stats API scoreboardv3",
                "NBA Stats API leaguedashplayerstats",
                "NBA Stats API leaguedashteamstats",
                "ESPN public scoreboard/news API",
                "Yahoo Sports NBA RSS",
                "CBS Sports NBA RSS",
                "Bleacher Report NBA RSS",
                "Google News (multi-publisher) RSS",
                "Reddit r/nba JSON",
            ],
        }

    def playoff_teams(self, season: str, news: list[dict[str, Any]]) -> list[dict[str, Any]]:
        frame = self._stats_frame(
            "leaguedashteamstats",
            common_dash_params(season, "Playoffs", "PerGame"),
            "LeagueDashTeamStats",
        )
        stats_by_id: dict[int, dict[str, Any]] = {}
        if not frame.empty:
            for column in ["TEAM_ID", "W", "L", "PTS", "REB", "AST", "PLUS_MINUS", "FG_PCT", "STL", "BLK", "TOV"]:
                if column in frame:
                    frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0)
            stats_by_id = {int(row["TEAM_ID"]): row for row in frame.to_dict("records") if int(row.get("TEAM_ID", 0)) in TEAM_BY_ID}

        advanced_by_id = self._advanced_team_stats(season)
        clutch_by_id = self._clutch_team_stats(season)

        rows = []
        for team in PLAYOFF_SEEDS_2026:
            stats = stats_by_id.get(int(team["team_id"]), {})
            wins = int(team["wins"])
            losses = int(team["losses"])
            playoff_wins = int(stats.get("W", 0))
            playoff_losses = int(stats.get("L", 0))
            plus_minus = round(float(stats.get("PLUS_MINUS", seed_net_rating(team["seed"]))), 1)
            sentiment = self._sentiment_for_terms(news, [team["team"], team["abbr"]], plus_minus)
            adv = advanced_by_id.get(int(team["team_id"]))
            fallback_adv = advanced_fallback(plus_minus)
            clutch = clutch_by_id.get(int(team["team_id"]))
            fallback_clutch = clutch_fallback(plus_minus)
            rows.append(
                {
                    **team,
                    "slug": slugify(team["team"]),
                    "logo": team_logo_url(int(team["team_id"])),
                    "record": f"{wins}-{losses}",
                    "pct": round(wins / max(wins + losses, 1), 3),
                    "gb": games_back(team, PLAYOFF_SEEDS_2026),
                    "playoff_record": f"{playoff_wins}-{playoff_losses}" if stats else "0-0",
                    "pts": round(float(stats.get("PTS", seed_points(team["seed"]))), 1),
                    "reb": round(float(stats.get("REB", 42.0 - team["seed"] * 0.2)), 1),
                    "ast": round(float(stats.get("AST", 24.0 - team["seed"] * 0.1)), 1),
                    "net": plus_minus,
                    "fg_pct": round(float(stats.get("FG_PCT", 0.46)) * 100, 1),
                    "stl": round(float(stats.get("STL", 7.2)), 1),
                    "blk": round(float(stats.get("BLK", 4.5)), 1),
                    "tov": round(float(stats.get("TOV", 13.0)), 1),
                    "off_rtg": round(float(adv["OFF_RATING"]), 1) if adv else fallback_adv["off_rtg"],
                    "def_rtg": round(float(adv["DEF_RATING"]), 1) if adv else fallback_adv["def_rtg"],
                    "pace": round(float(adv["PACE"]), 1) if adv else fallback_adv["pace"],
                    "efg_pct": round(float(adv["EFG_PCT"]) * 100, 1) if adv else fallback_adv["efg_pct"],
                    "ts_pct": round(float(adv["TS_PCT"]) * 100, 1) if adv else fallback_adv["ts_pct"],
                    "tov_pct": round(float(adv["TM_TOV_PCT"]) * 100, 1) if adv else fallback_adv["tov_pct"],
                    "clutch_record": f"{int(clutch['W'])}-{int(clutch['L'])}" if clutch else fallback_clutch["clutch_record"],
                    "clutch_net": round(float(clutch["PLUS_MINUS"]), 1) if clutch else fallback_clutch["clutch_net"],
                    "last10": simulated_last10(playoff_wins, playoff_losses),
                    "streak": streak_from_net(plus_minus),
                    "sentiment": sentiment,
                }
            )
        return rows

    def _advanced_team_stats(self, season: str) -> dict[int, dict[str, Any]]:
        """Off/def rating, pace, and four-factors efficiency (NBA Stats MeasureType=Advanced).

        Same data source we already poll for box stats - competing dashboards (NBA.com
        Stats, Cleaning the Glass) lead with these per-possession numbers instead of raw
        per-game counting stats, which is what we had until now.
        """
        params = common_dash_params(season, "Playoffs", "PerGame")
        params["MeasureType"] = "Advanced"
        frame = self._stats_frame("leaguedashteamstats", params, "LeagueDashTeamStats")
        if frame.empty:
            return {}
        for column in ["TEAM_ID", "OFF_RATING", "DEF_RATING", "PACE", "EFG_PCT", "TS_PCT", "TM_TOV_PCT"]:
            if column in frame:
                frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0)
        return {int(row["TEAM_ID"]): row for row in frame.to_dict("records") if int(row.get("TEAM_ID", 0)) in TEAM_BY_ID}

    @lru_cache(maxsize=4)
    def _clutch_team_stats(self, season: str) -> dict[int, dict[str, Any]]:
        """Clutch-time (last 5 min, score within 5 pts) record and net rating per team.

        Dedicated NBA Stats endpoint (leaguedashteamclutch) for the same split NBA.com's
        own "Clutch" tab shows - see the `_CLUTCH_TIME` comment above for why it's worth
        having next to the season-long advanced stats.
        """
        params = common_dash_params(season, "Playoffs", "PerGame")
        params["AheadBehind"] = "Ahead or Behind"
        params["ClutchTime"] = _CLUTCH_TIME
        params["PointDiff"] = _CLUTCH_POINT_DIFF
        frame = self._stats_frame("leaguedashteamclutch", params, "LeagueDashTeamClutch")
        if frame.empty:
            return {}
        for column in ["TEAM_ID", "W", "L", "PLUS_MINUS"]:
            if column in frame:
                frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0)
        return {int(row["TEAM_ID"]): row for row in frame.to_dict("records") if int(row.get("TEAM_ID", 0)) in TEAM_BY_ID}

    def power_rankings(self, season: str, news: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """League-wide power ranking across all 16 tracked playoff teams.

        Competing sites (ESPN, NBA.com, The Ringer) publish power rankings that
        blend net rating with recent form instead of sorting by raw record -
        we already compute both per team in playoff_teams(), so this combines
        them into one ordered list and flags teams over/under-ranked relative
        to their record.
        """
        teams = self.playoff_teams(season, news)
        record_order = sorted(teams, key=lambda row: row["pct"], reverse=True)
        record_rank = {row["abbr"]: i + 1 for i, row in enumerate(record_order)}

        scored = []
        for team in teams:
            form_pct = self._form_wins(team.get("last10", "5-5")) / 10
            power_score = round(team["net"] + (form_pct - 0.5) * 6, 2)
            scored.append((power_score, form_pct, team))
        scored.sort(key=lambda row: row[0], reverse=True)

        rows = []
        for rank, (power_score, form_pct, team) in enumerate(scored, start=1):
            movement = record_rank[team["abbr"]] - rank
            rows.append(
                {
                    **team,
                    "rank": rank,
                    "power_score": power_score,
                    "record_rank": record_rank[team["abbr"]],
                    "movement": movement,
                    "blurb": power_ranking_blurb(team, form_pct, movement),
                }
            )
        return rows

    @lru_cache(maxsize=4)
    def _home_road_net_ratings(self, season: str) -> dict[str, dict[int, float]]:
        """Home-only and road-only net (PLUS_MINUS) rating per team, via the NBA Stats
        `Location` filter on the same leaguedashteamstats endpoint we already poll."""
        splits: dict[str, dict[int, float]] = {"home": {}, "road": {}}
        for key, location in (("home", "Home"), ("road", "Road")):
            params = common_dash_params(season, "Playoffs", "PerGame")
            params["Location"] = location
            frame = self._stats_frame("leaguedashteamstats", params, "LeagueDashTeamStats")
            if frame.empty or "PLUS_MINUS" not in frame:
                continue
            frame["PLUS_MINUS"] = pd.to_numeric(frame["PLUS_MINUS"], errors="coerce").fillna(0)
            for row in frame.to_dict("records"):
                team_id = int(row.get("TEAM_ID", 0))
                if team_id in TEAM_BY_ID:
                    splits[key][team_id] = float(row["PLUS_MINUS"])
        return splits

    def playoff_players(self, season: str, news: list[dict[str, Any]]) -> list[dict[str, Any]]:
        frame = self._stats_frame(
            "leaguedashplayerstats",
            common_dash_params(season, "Playoffs", "PerGame"),
            "LeagueDashPlayerStats",
        )
        if frame.empty:
            return self._espn_rotation_players(news) or fallback_players()

        numeric = ["PLAYER_ID", "TEAM_ID", "PTS", "REB", "AST", "STL", "BLK", "PLUS_MINUS", "FG_PCT", "FG3_PCT", "FT_PCT", "GP", "MIN", "TOV"]
        for column in numeric:
            if column in frame:
                frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0)
        frame = frame[frame["TEAM_ID"].isin(TEAM_BY_ID.keys())].copy()
        if frame.empty:
            return self._espn_rotation_players(news) or fallback_players()
        frame["IMPACT"] = (
            frame.get("PTS", 0) * 1.0
            + frame.get("REB", 0) * 1.05
            + frame.get("AST", 0) * 1.25
            + frame.get("STL", 0) * 2.0
            + frame.get("BLK", 0) * 1.8
            + frame.get("PLUS_MINUS", 0) * 0.4
        )

        rows = []
        for team_id, group in frame.groupby("TEAM_ID"):
            team = TEAM_BY_ID[int(team_id)]
            rotation = group.sort_values(["MIN", "GP", "PTS"], ascending=False).reset_index(drop=True)
            for index, item in enumerate(rotation.to_dict("records")):
                name = item.get("PLAYER_NAME", "Player")
                plus_minus = float(item.get("PLUS_MINUS", 0))
                rows.append(
                    {
                        "id": int(item.get("PLAYER_ID", 0)),
                        "slug": slugify(str(name)),
                        "player": name,
                        "team": team["abbr"],
                        "team_name": team["team"],
                        "team_id": int(team["team_id"]),
                        "team_slug": slugify(team["team"]),
                        "role": "Starting 5" if index < 5 else "Bench",
                        "rotation_rank": index + 1,
                        "headshot": player_headshot_url(int(item.get("PLAYER_ID", 0))),
                        "gp": int(item.get("GP", 0)),
                        "min": round(float(item.get("MIN", 0)), 1),
                        "pts": round(float(item.get("PTS", 0)), 1),
                        "reb": round(float(item.get("REB", 0)), 1),
                        "ast": round(float(item.get("AST", 0)), 1),
                        "stl": round(float(item.get("STL", 0)), 1),
                        "blk": round(float(item.get("BLK", 0)), 1),
                        "fg_pct": round(float(item.get("FG_PCT", 0)) * 100, 1),
                        "fg3_pct": round(float(item.get("FG3_PCT", 0)) * 100, 1),
                        "ft_pct": round(float(item.get("FT_PCT", 0)) * 100, 1),
                        "plus_minus": round(plus_minus, 1),
                        "impact": round(float(item.get("IMPACT", 0)), 1),
                        "trend": player_trend(float(item.get("PTS", 0)), float(item.get("PLUS_MINUS", 0))),
                        "sentiment": self._sentiment_for_terms(news, [str(name), team["abbr"], team["team"]], plus_minus),
                    }
                )
        return rows

    def _espn_rotation_players(self, news: list[dict[str, Any]]) -> list[dict[str, Any]]:
        rows = []
        session = requests.Session()
        for team in PLAYOFF_SEEDS_2026:
            code = ESPN_TEAM_CODES.get(team["abbr"], team["abbr"].lower())
            try:
                response = session.get(
                    f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/{code}/roster",
                    timeout=self.timeout,
                    verify=False,
                )
                response.raise_for_status()
                athletes = response.json().get("athletes", [])
            except Exception:
                athletes = []
            for index, athlete in enumerate(athletes):
                name = athlete.get("displayName") or athlete.get("fullName") or "Player"
                rank = index + 1
                stats = synthetic_player_stats(team["seed"], rank)
                plus_minus = stats["plus_minus"]
                rows.append(
                    {
                        "id": int(athlete.get("id") or abs(hash(f"{team['abbr']}-{name}")) % 10000000),
                        "slug": slugify(str(name)),
                        "player": name,
                        "team": team["abbr"],
                        "team_name": team["team"],
                        "team_id": int(team["team_id"]),
                        "team_slug": slugify(team["team"]),
                        "role": "Starting 5" if index < 5 else "Bench",
                        "rotation_rank": rank,
                        "headshot": (athlete.get("headshot") or {}).get("href") or player_headshot_url(0),
                        "gp": 0,
                        "min": stats["min"],
                        "pts": stats["pts"],
                        "reb": stats["reb"],
                        "ast": stats["ast"],
                        "stl": stats["stl"],
                        "blk": stats["blk"],
                        "fg_pct": stats["fg_pct"],
                        "fg3_pct": stats["fg3_pct"],
                        "ft_pct": stats["ft_pct"],
                        "plus_minus": plus_minus,
                        "impact": stats["impact"],
                        "trend": player_trend(stats["pts"], plus_minus),
                        "sentiment": self._sentiment_for_terms(news, [str(name), team["abbr"], team["team"]], plus_minus),
                    }
                )
        return rows

    def leaders(self, season: str, news: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
        players = self.playoff_players(season, news)
        return self.leaders_from_players(players)

    def leaders_from_players(self, players: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
        return {
            "pts": sorted(players, key=lambda row: row.get("pts", 0), reverse=True)[:5],
            "reb": sorted(players, key=lambda row: row.get("reb", 0), reverse=True)[:5],
            "ast": sorted(players, key=lambda row: row.get("ast", 0), reverse=True)[:5],
            "stl": sorted(players, key=lambda row: row.get("stl", 0), reverse=True)[:5],
            "blk": sorted(players, key=lambda row: row.get("blk", 0), reverse=True)[:5],
        }

    def playoff_table(self, season: str) -> list[dict[str, Any]]:
        computed = self._scoreboardv3_playoff_table()
        if computed:
            return computed

        east = self._stats_frame("playoffpicture", {"LeagueID": "00", "SeasonID": season_id(season)}, "EastConfPlayoffPicture")
        west = self._stats_frame("playoffpicture", {"LeagueID": "00", "SeasonID": season_id(season)}, "WestConfPlayoffPicture")
        rows: list[dict[str, Any]] = []
        for frame in [east, west]:
            if frame.empty:
                continue
            for item in frame.to_dict("records"):
                high = str(item.get("HIGH_SEED_TEAM", "High seed"))
                low = str(item.get("LOW_SEED_TEAM", "Low seed"))
                high_wins = int(item.get("HIGH_SEED_SERIES_W") or 0)
                high_losses = int(item.get("HIGH_SEED_SERIES_L") or 0)
                rows.append(
                    {
                        "conference": item.get("CONFERENCE", ""),
                        "matchup": f"{item.get('HIGH_SEED_RANK', '')} {high} vs {item.get('LOW_SEED_RANK', '')} {low}",
                        "series": f"{high} {high_wins}-{high_losses}",
                        "leader": high if high_wins >= high_losses else low,
                        "remaining": int(item.get("HIGH_SEED_SERIES_REMAINING_G") or 0),
                        # playoffpicture doesn't expose which round a series is in;
                        # ponytail: single bucket here, upgrade if NBA Stats adds a round field.
                        "round": "Playoffs",
                    }
                )
        return rows[:12] or fallback_playoff_table()

    def _scoreboardv3_playoff_table(self) -> list[dict[str, Any]]:
        games = self._recent_scoreboardv3_games()
        latest_by_series: dict[str, dict[str, Any]] = {}
        for game in games:
            if int(game.get("gameStatus") or 0) != 3:
                continue
            game_id = str(game.get("gameId", ""))
            if not game_id.startswith("004"):
                continue
            series_id = game_id[:-1]
            current = latest_by_series.get(series_id)
            if current is None or str(game.get("gameTimeUTC", "")) > str(current.get("gameTimeUTC", "")):
                latest_by_series[series_id] = game

        rows = [self._series_row_from_scoreboard(game) for game in latest_by_series.values()]
        rows = [row for row in rows if row]
        return sorted(rows, key=lambda row: (row["sort_round"], row["conference"], row["matchup"]))[:16]

    def _series_row_from_scoreboard(self, game: dict[str, Any]) -> dict[str, Any] | None:
        home = game.get("homeTeam") or {}
        away = game.get("awayTeam") or {}
        if not home or not away:
            return None

        home_name = f"{home.get('teamCity', '')} {home.get('teamName', '')}".strip()
        away_name = f"{away.get('teamCity', '')} {away.get('teamName', '')}".strip()
        home_wins = int(home.get("wins") or 0)
        home_losses = int(home.get("losses") or 0)
        away_wins = int(away.get("wins") or 0)
        away_losses = int(away.get("losses") or 0)

        if home_wins >= away_wins:
            leader = home_name
            series = f"{home.get('teamTricode', home_name)} {home_wins}-{home_losses}"
        else:
            leader = away_name
            series = f"{away.get('teamTricode', away_name)} {away_wins}-{away_losses}"

        label = str(game.get("gameLabel") or "")
        sort_round = playoff_round_sort(label)
        return {
            "conference": game.get("seriesConference") or ("East" if "East" in label else "West" if "West" in label else ""),
            "matchup": f"{away_name} vs {home_name}",
            "series": game.get("seriesText") or series,
            "leader": leader,
            "remaining": 0 if max(home_wins, away_wins) >= 4 else max(0, 4 - max(home_wins, away_wins)),
            "last_game": game.get("gameTimeUTC", ""),
            "sort_round": sort_round,
            "round": playoff_round_label(sort_round),
        }

    @lru_cache(maxsize=1)
    def _recent_scoreboardv3_games(self) -> list[dict[str, Any]]:
        games: list[dict[str, Any]] = []
        today = date.today()
        start = today - timedelta(days=35)
        session = requests.Session()
        for offset in range((today - start).days + 1):
            game_date = start + timedelta(days=offset)
            try:
                response = session.get(
                    "https://stats.nba.com/stats/scoreboardv3",
                    params={"GameDate": game_date.isoformat(), "LeagueID": "00"},
                    headers=NBAStatsHTTP.headers,
                    timeout=self.timeout,
                    verify=False,
                )
                response.raise_for_status()
                games.extend(response.json().get("scoreboard", {}).get("games", []))
            except Exception:
                continue
        return games

    def upcoming_games(self) -> list[dict[str, Any]]:
        games: list[dict[str, Any]] = []
        today = date.today()
        for offset in range(0, 8):
            events = self._espn_scoreboard(today + timedelta(days=offset))
            for event in events:
                competitions = event.get("competitions") or []
                if not competitions:
                    continue
                competitors = competitions[0].get("competitors", [])
                away = next((team for team in competitors if team.get("homeAway") == "away"), {})
                home = next((team for team in competitors if team.get("homeAway") == "home"), {})
                games.append(
                    {
                        "date": event.get("date", ""),
                        "matchup": event.get("shortName") or event.get("name", ""),
                        "away": away.get("team", {}).get("abbreviation", ""),
                        "home": home.get("team", {}).get("abbreviation", ""),
                        "status": event.get("status", {}).get("type", {}).get("shortDetail", "Scheduled"),
                    }
                )
            if len(games) >= 8:
                break
        return games[:8] or fallback_upcoming_games()

    def _out_players_for_team(
        self, team_abbr: str, players: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Rotation players on `team_abbr` currently flagged out by injury news."""
        alerts = _INJURY_WATCH.alerts()
        if not alerts:
            return []
        headlines = " ".join(str(alert.get("headline", "")).lower() for alert in alerts)
        out: list[dict[str, Any]] = []
        for player in players:
            if player.get("team") != team_abbr:
                continue
            if float(player.get("min", 0) or 0) < _INJURY_MIN_MINUTES:
                continue
            parts = str(player.get("player", "")).split()
            last_name = parts[-1].lower() if parts else ""
            if len(last_name) >= 4 and last_name in headlines:
                out.append(player)
        return out

    @staticmethod
    def _injury_points(out_players: list[dict[str, Any]]) -> float:
        """Convert a list of out players into points-of-margin lost (capped)."""
        total = sum(float(player.get("impact", 0) or 0) for player in out_players)
        return round(min(_INJURY_POINTS_CAP, total * _IMPACT_TO_POINTS), 2)

    def _last_game_date(self, team_abbr: str, before: date) -> date | None:
        """Most recent date `team_abbr` played, searching backward from (not
        including) `before` on the public ESPN scoreboard."""
        for offset in range(1, _REST_LOOKBACK_DAYS + 1):
            day = before - timedelta(days=offset)
            for event in self._espn_scoreboard(day):
                competitions = event.get("competitions") or []
                if not competitions:
                    continue
                for competitor in competitions[0].get("competitors", []):
                    abbr = normalize_team_abbr(competitor.get("team", {}).get("abbreviation", ""))
                    if abbr == team_abbr:
                        return day
        return None

    def _rest_days(self, team_abbr: str, game_date: date) -> int:
        """Days of rest before `game_date` (0 = back-to-back). Unknown -> fully rested,
        since a missing schedule shouldn't manufacture a fatigue penalty."""
        last_game = self._last_game_date(team_abbr, game_date)
        if last_game is None:
            return _REST_DAYS_CAP
        return max(0, min(_REST_DAYS_CAP, (game_date - last_game).days - 1))

    def game_prediction(self, away_abbr: str, home_abbr: str) -> dict[str, Any]:
        away_code = normalize_team_abbr(away_abbr)
        home_code = normalize_team_abbr(home_abbr)
        away_seed = TEAM_BY_ABBR.get(away_code)
        home_seed = TEAM_BY_ABBR.get(home_code)
        if not away_seed or not home_seed:
            return {
                "ok": False,
                "message": "That matchup is not available in the playoff model yet.",
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }

        season = current_season()
        news = self._aggregated_news()
        teams = {team["abbr"]: team for team in self.playoff_teams(season, news)}
        away = teams.get(away_seed["abbr"], away_seed)
        home = teams.get(home_seed["abbr"], home_seed)

        calibration = load_pregame_calibration()
        hca = calibration["home_court_advantage"]
        scale = calibration["scale"]

        home_net = float(home.get("net", seed_net_rating(int(home["seed"]))))
        away_net = float(away.get("net", seed_net_rating(int(away["seed"]))))

        # Injury adjustment (best-effort, news-driven). Reuses the shared
        # InjuryNewsWatch and the per-player IMPACT score from playoff_players.
        home_out: list[dict[str, Any]] = []
        away_out: list[dict[str, Any]] = []
        home_injury_pts = 0.0
        away_injury_pts = 0.0
        try:
            players = self.playoff_players(season, news)
            roster_names = [
                p["player"] for p in players if p.get("team") in (home["abbr"], away["abbr"])
            ]
            _INJURY_WATCH.refresh(
                team_terms=[home["team"], home["abbr"], away["team"], away["abbr"]],
                player_terms=roster_names[:20],
            )
            home_out = self._out_players_for_team(home["abbr"], players)
            away_out = self._out_players_for_team(away["abbr"], players)
            home_injury_pts = self._injury_points(home_out)
            away_injury_pts = self._injury_points(away_out)
        except Exception:
            pass

        game_date = date.today()
        home_rest = self._rest_days(home["abbr"], game_date)
        away_rest = self._rest_days(away["abbr"], game_date)
        rest_edge = (home_rest - away_rest) * _REST_POINTS_PER_DAY
        if home_rest == 0:
            rest_edge -= _BACK_TO_BACK_PENALTY
        if away_rest == 0:
            rest_edge += _BACK_TO_BACK_PENALTY

        form_edge = form_margin_edge(home.get("last10", "5-5"), away.get("last10", "5-5"))

        try:
            splits = self._home_road_net_ratings(season)
        except Exception:
            splits = {"home": {}, "road": {}}
        home_split_net = splits.get("home", {}).get(int(home["team_id"]))
        away_split_net = splits.get("road", {}).get(int(away["team_id"]))
        split_edge = home_road_split_edge(home_split_net, away_split_net, home_net, away_net)

        ff_edge = four_factors_edge(
            float(home.get("efg_pct", 0)), float(away.get("efg_pct", 0)),
            float(home.get("tov_pct", 0)), float(away.get("tov_pct", 0)),
        )

        expected_home_margin = (
            (home_net - away_net) + hca - home_injury_pts + away_injury_pts
            + rest_edge + form_edge + split_edge + ff_edge
        )
        home_probability = 1 / (1 + exp(-expected_home_margin / scale))
        home_probability = max(0.02, min(0.98, home_probability))
        away_probability = 1 - home_probability

        # Honest signal about whether we ran on real stats or seed fallbacks.
        def _is_real(team: dict[str, Any]) -> bool:
            return abs(float(team.get("net", 0)) - seed_net_rating(int(team["seed"]))) > 1e-6

        data_quality = "live_stats" if (_is_real(home) or _is_real(away)) else "seed_fallback"

        winner = home if home_probability >= away_probability else away
        loser = away if winner["abbr"] == home["abbr"] else home
        confidence = max(home_probability, away_probability)

        winner_strength = float(winner.get("net", 0))
        loser_strength = float(loser.get("net", 0))
        scoring_gap = float(winner.get("pts", 0)) - float(loser.get("pts", 0))
        form_gap = self._form_wins(winner.get("last10", "0-0")) - self._form_wins(loser.get("last10", "0-0"))
        winner_sentiment = winner.get("sentiment") or {"label": "Neutral", "score": 0}
        loser_sentiment = loser.get("sentiment") or {"label": "Neutral", "score": 0}
        sentiment_gap = float(winner_sentiment.get("score", 0)) - float(loser_sentiment.get("score", 0))

        summary_parts = [
            f"The {winner['team']} get the edge because their overall team rating is stronger in this matchup.",
        ]
        if abs(winner_strength - loser_strength) >= 1:
            summary_parts.append("They have the better recent point margin, which usually travels well late in games.")
        if scoring_gap >= 1:
            summary_parts.append(f"The scoring profile also leans toward {winner['abbr']}, especially if the pace stays normal.")
        elif scoring_gap <= -1:
            summary_parts.append("The other team scores a bit more, so this pick leans more on margin, form, and matchup balance than raw points.")
        if form_gap > 0:
            summary_parts.append("Their recent form is a little cleaner over the last ten games, which nudges the number toward them.")
        if winner["abbr"] == home.get("abbr"):
            summary_parts.append("Home court adds a small boost, but it is not the whole reason for the pick.")

        winner_rest = home_rest if winner["abbr"] == home["abbr"] else away_rest
        loser_rest = away_rest if winner["abbr"] == home["abbr"] else home_rest
        if loser_rest == 0 and winner_rest > 0:
            summary_parts.append(f"{loser['abbr']} is on the second night of a back-to-back, which usually costs a point or two of margin.")
        elif winner_rest == 0 and loser_rest > 0:
            summary_parts.append(f"{winner['abbr']} is on a back-to-back too, so the pick already prices in some fatigue.")
        elif winner_rest > loser_rest:
            summary_parts.append(f"{winner['abbr']} also comes in with the extra rest, which helps late in games.")

        winner_out = home_out if winner["abbr"] == home["abbr"] else away_out
        loser_out = away_out if winner["abbr"] == home["abbr"] else home_out
        if loser_out:
            loser_names = ", ".join(p.get("player", "a key player") for p in loser_out)
            summary_parts.append(
                f"Availability helps too: {loser['abbr']} is dealing with injury news around {loser_names}, "
                f"which trims their projected output."
            )
        if winner_out:
            winner_names = ", ".join(p.get("player", "a key player") for p in winner_out)
            summary_parts.append(
                f"Note that {winner['abbr']} also has injury question marks ({winner_names}), so the pick already "
                f"accounts for a slightly thinner rotation."
            )

        winner_split_net = home_split_net if winner["abbr"] == home["abbr"] else away_split_net
        loser_split_net = away_split_net if winner["abbr"] == home["abbr"] else home_split_net
        winner_split_edge = split_edge if winner["abbr"] == home["abbr"] else -split_edge
        if winner_split_net is not None and loser_split_net is not None and abs(winner_split_edge) >= 0.3:
            where = "at home" if winner["abbr"] == home["abbr"] else "on the road"
            summary_parts.append(
                f"{winner['abbr']} also plays better {where} than their season number alone suggests, adding a bit more edge."
            )

        winner_ff_edge = ff_edge if winner["abbr"] == home["abbr"] else -ff_edge
        if winner_ff_edge >= 0.4:
            summary_parts.append(
                f"{winner['abbr']} also grades out better on our shooting-efficiency and ball-security blend "
                f"(eFG%/turnovers), which adds a bit more to the number."
            )
        elif winner_ff_edge <= -0.4:
            summary_parts.append(
                f"{loser['abbr']} actually grades out better on that same shooting/turnover blend, "
                f"so the pick leans more on overall margin, rest, and matchup context than shot quality."
            )

        if sentiment_gap >= 0.2:
            summary_parts.append(
                f"News sentiment also favors {winner['abbr']} ({winner_sentiment.get('label', 'Neutral').lower()}, "
                f"{winner_sentiment.get('score', 0):+.2f}) versus {loser['abbr']} ({loser_sentiment.get('label', 'Neutral').lower()}, "
                f"{loser_sentiment.get('score', 0):+.2f}), reinforcing the pick."
            )
        elif sentiment_gap <= -0.2:
            summary_parts.append(
                f"Heads up: news sentiment is actually leaning the other way ({loser['abbr']} {loser_sentiment.get('label', 'Neutral').lower()} "
                f"{loser_sentiment.get('score', 0):+.2f} vs {winner['abbr']} {winner_sentiment.get('label', 'Neutral').lower()} "
                f"{winner_sentiment.get('score', 0):+.2f}), so the pick is driven by the on-court numbers."
            )
        else:
            summary_parts.append(
                f"News sentiment is roughly even ({winner['abbr']} {winner_sentiment.get('label', 'Neutral').lower()} "
                f"{winner_sentiment.get('score', 0):+.2f}, {loser['abbr']} {loser_sentiment.get('label', 'Neutral').lower()} "
                f"{loser_sentiment.get('score', 0):+.2f}), so it does not move the needle much."
            )

        return {
            "ok": True,
            "winner": winner["abbr"],
            "winner_name": winner["team"],
            "away": away["abbr"],
            "home": home["abbr"],
            "away_probability": round(away_probability, 3),
            "home_probability": round(home_probability, 3),
            "confidence": round(confidence, 3),
            "summary": " ".join(summary_parts),
            "sentiment": {
                "winner": {"abbr": winner["abbr"], **winner_sentiment},
                "loser": {"abbr": loser["abbr"], **loser_sentiment},
                "gap": round(sentiment_gap, 2),
                "weight": "Sentiment is shown for context only — it no longer moves the win probability.",
                "sources": list({s for side in (winner_sentiment, loser_sentiment) for s in (side.get("sources") or [])})[:8],
            },
            "expected_margin": {
                "home": round(expected_home_margin, 1),
                "winner": round(expected_home_margin if winner["abbr"] == home["abbr"] else -expected_home_margin, 1),
                "home_court_advantage": round(hca, 2),
            },
            "injuries": {
                "home": {
                    "abbr": home["abbr"],
                    "players_out": [p.get("player", "") for p in home_out],
                    "points_lost": round(home_injury_pts, 2),
                },
                "away": {
                    "abbr": away["abbr"],
                    "players_out": [p.get("player", "") for p in away_out],
                    "points_lost": round(away_injury_pts, 2),
                },
            },
            "rest": {
                "home": {"abbr": home["abbr"], "days": home_rest, "back_to_back": home_rest == 0},
                "away": {"abbr": away["abbr"], "days": away_rest, "back_to_back": away_rest == 0},
                "margin_edge": round(rest_edge, 2),
            },
            "form": {
                "home": {"abbr": home["abbr"], "last10": home.get("last10", "5-5")},
                "away": {"abbr": away["abbr"], "last10": away.get("last10", "5-5")},
                "margin_edge": round(form_edge, 2),
            },
            "home_road_split": {
                "home": {"abbr": home["abbr"], "home_net": round(home_split_net, 1) if home_split_net is not None else None},
                "away": {"abbr": away["abbr"], "road_net": round(away_split_net, 1) if away_split_net is not None else None},
                "margin_edge": round(split_edge, 2),
            },
            "four_factors": {
                "home": {"abbr": home["abbr"], "efg_pct": home.get("efg_pct"), "tov_pct": home.get("tov_pct")},
                "away": {"abbr": away["abbr"], "efg_pct": away.get("efg_pct"), "tov_pct": away.get("tov_pct")},
                "margin_edge": round(ff_edge, 2),
            },
            "calibration": {
                "home_court_advantage": round(hca, 2),
                "scale": round(scale, 2),
                "source": "fit to real game results" if _CALIBRATION_PATH.exists() else "default constants",
            },
            "data_quality": data_quality,
            "factors": [
                {"label": "Team margin", "winner": round(winner_strength, 1), "opponent": round(loser_strength, 1)},
                {"label": "Scoring", "winner": round(float(winner.get("pts", 0)), 1), "opponent": round(float(loser.get("pts", 0)), 1)},
                {"label": "Recent form", "winner": winner.get("last10", "0-0"), "opponent": loser.get("last10", "0-0")},
                {"label": "Availability", "winner": f"{len(winner_out)} key out", "opponent": f"{len(loser_out)} key out"},
                {"label": "Rest", "winner": f"{winner_rest}d rest", "opponent": f"{loser_rest}d rest"},
                {
                    "label": "Home/road split",
                    "winner": f"{winner_split_net:+.1f} net" if winner_split_net is not None else "N/A",
                    "opponent": f"{loser_split_net:+.1f} net" if loser_split_net is not None else "N/A",
                },
                {
                    "label": "Shooting/turnovers",
                    "winner": f"{winner.get('efg_pct', 0):.1f}% eFG, {winner.get('tov_pct', 0):.1f}% TOV",
                    "opponent": f"{loser.get('efg_pct', 0):.1f}% eFG, {loser.get('tov_pct', 0):.1f}% TOV",
                },
                {"label": "News sentiment", "winner": f"{winner_sentiment.get('label', 'Neutral')} ({winner_sentiment.get('score', 0):+.2f})", "opponent": f"{loser_sentiment.get('label', 'Neutral')} ({loser_sentiment.get('score', 0):+.2f})"},
            ],
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def player_analysis(self, season: str, news: list[dict[str, Any]]) -> list[dict[str, Any]]:
        frame = self._stats_frame(
            "leaguedashplayerstats",
            common_dash_params(season, "Playoffs", "PerGame"),
            "LeagueDashPlayerStats",
        )
        if frame.empty:
            return fallback_players()

        numeric = ["PTS", "REB", "AST", "PLUS_MINUS", "FG_PCT", "GP", "MIN"]
        for column in numeric:
            if column in frame:
                frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0)
        frame["IMPACT"] = (
            frame.get("PTS", 0) * 1.0
            + frame.get("REB", 0) * 1.15
            + frame.get("AST", 0) * 1.35
            + frame.get("PLUS_MINUS", 0) * 0.45
        )
        top = frame.sort_values("IMPACT", ascending=False).head(12)
        rows = []
        for item in top.to_dict("records"):
            name = item.get("PLAYER_NAME", "Player")
            team = item.get("TEAM_ABBREVIATION", "")
            sentiment = self._sentiment_for_terms(news, [name, team], item.get("PLUS_MINUS", 0))
            rows.append(
                {
                    "player": name,
                    "team": team,
                    "pts": round(float(item.get("PTS", 0)), 1),
                    "reb": round(float(item.get("REB", 0)), 1),
                    "ast": round(float(item.get("AST", 0)), 1),
                    "fg_pct": round(float(item.get("FG_PCT", 0)) * 100, 1),
                    "plus_minus": round(float(item.get("PLUS_MINUS", 0)), 1),
                    "impact": round(float(item.get("IMPACT", 0)), 1),
                    "sentiment": sentiment,
                }
            )
        return rows

    def team_analysis(self, season: str, news: list[dict[str, Any]]) -> list[dict[str, Any]]:
        frame = self._stats_frame(
            "leaguedashteamstats",
            common_dash_params(season, "Playoffs", "PerGame"),
            "LeagueDashTeamStats",
        )
        if frame.empty:
            return fallback_teams()

        for column in ["W", "L", "PTS", "REB", "AST", "PLUS_MINUS", "FG_PCT"]:
            if column in frame:
                frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0)
        frame["RATING"] = frame.get("PTS", 0) + frame.get("PLUS_MINUS", 0) * 1.8 + frame.get("AST", 0) * 0.55
        top = frame.sort_values("RATING", ascending=False).head(12)
        rows = []
        for item in top.to_dict("records"):
            team = item.get("TEAM_NAME", "Team")
            abbreviation = item.get("TEAM_ABBREVIATION", "")
            sentiment = self._sentiment_for_terms(news, [team, abbreviation], item.get("PLUS_MINUS", 0))
            rows.append(
                {
                    "team": team,
                    "abbr": abbreviation,
                    "record": f"{int(item.get('W', 0))}-{int(item.get('L', 0))}",
                    "pts": round(float(item.get("PTS", 0)), 1),
                    "reb": round(float(item.get("REB", 0)), 1),
                    "ast": round(float(item.get("AST", 0)), 1),
                    "net": round(float(item.get("PLUS_MINUS", 0)), 1),
                    "fg_pct": round(float(item.get("FG_PCT", 0)) * 100, 1),
                    "sentiment": sentiment,
                }
            )
        return rows

    def sentiment_summary(self, news: list[dict[str, Any]]) -> dict[str, Any]:
        if not news:
            return {"label": "Neutral", "score": 0, "headline": "No public news feed available", "sources": []}
        scored = []
        for article in news:
            text = f"{article.get('headline', '')} {article.get('description', '')}"
            rank = int(article.get("source_rank", 3))
            weight = max(0.4, 1.05 - rank * 0.15)
            scored.append((article, sentiment_score(text), weight))
        total_weight = sum(weight for _, _, weight in scored) or 1.0
        average = sum(score * weight for _, score, weight in scored) / total_weight
        label = sentiment_label(average)
        headline = max(scored, key=lambda triple: abs(triple[1]))[0].get("headline", "NBA news sentiment")
        sources_seen: list[str] = []
        for article in sorted(news, key=lambda a: int(a.get("source_rank", 9))):
            label_text = article.get("source", "")
            if label_text and label_text not in sources_seen:
                sources_seen.append(label_text)
        return {
            "label": label,
            "score": round(average, 2),
            "headline": headline,
            "sources": sources_seen[:8],
        }

    def _stats_frame(self, endpoint: str, params: dict[str, Any], result_name: str) -> pd.DataFrame:
        try:
            response = requests.get(
                f"https://stats.nba.com/stats/{endpoint}",
                params=params,
                headers=NBAStatsHTTP.headers,
                timeout=self.timeout,
                verify=False,
            )
            response.raise_for_status()
            result_sets = response.json().get("resultSets", [])
            selected = next((item for item in result_sets if item.get("name") == result_name), result_sets[0])
            return pd.DataFrame(selected.get("rowSet", []), columns=selected.get("headers", []))
        except Exception:
            return pd.DataFrame()

    @lru_cache(maxsize=16)
    def _espn_scoreboard(self, game_date: date) -> list[dict[str, Any]]:
        try:
            response = requests.get(
                "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard",
                params={"dates": game_date.strftime("%Y%m%d")},
                timeout=self.timeout,
                verify=False,
            )
            response.raise_for_status()
            return response.json().get("events", [])
        except Exception:
            return []

    @lru_cache(maxsize=1)
    def _espn_news(self) -> list[dict[str, Any]]:
        return self._fetch_espn_news()

    def _aggregated_news(self, refresh_key: str = "cached") -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        for raw in self._espn_news_for_refresh(refresh_key):
            article = news_sources.normalize_espn(raw)
            if article:
                normalized.append(article)
        normalized.extend(news_sources.fetch_general_pool(refresh_key))
        return news_sources.dedupe(normalized)

    def contextual_news(self, entity_type: str, terms: list[str], team_abbr: str = "", force_refresh: bool = False) -> dict[str, Any]:
        clean_terms = [term.strip() for term in terms if term and term.strip()]
        team = TEAM_BY_ABBR.get(team_abbr.upper()) if team_abbr else None

        refresh_key = datetime.now(timezone.utc).isoformat() if force_refresh else "cached"

        general_pool = self._aggregated_news(refresh_key)

        team_news_normalized: list[dict[str, Any]] = []
        if team:
            code = ESPN_TEAM_CODES.get(team["abbr"], team["abbr"].lower())
            for raw in self._espn_team_news_for_refresh(code, refresh_key):
                article = news_sources.normalize_espn(raw)
                if article:
                    article = {**article, "source": f"{article.get('source', 'ESPN')} (team feed)"}
                    team_news_normalized.append(article)

        if entity_type == "player":
            team_lower: set[str] = set()
            if team:
                team_lower = {team["abbr"].lower(), team["team"].lower(), team["team"].split()[-1].lower()}
            player_terms = [term for term in clean_terms if term.lower() not in team_lower]
            primary = player_terms[0] if player_terms else (clean_terms[0] if clean_terms else "")

            search_terms = self._expand_name_terms(player_terms)
            entity_articles = news_sources.fetch_entity_pool(primary, refresh_key) if primary else []
            merged = news_sources.dedupe(team_news_normalized + entity_articles + general_pool)
            filtered = [a for a in merged if news_sources.article_relevance(a, search_terms) > 0]
            source_labels = self._collect_source_labels(filtered)
        else:
            team_terms: list[str] = []
            if team:
                team_terms.extend([team["abbr"], team["team"], team["team"].split()[-1]])
            team_terms.extend(clean_terms)
            primary = team["team"] if team else (clean_terms[0] if clean_terms else "")
            entity_articles = news_sources.fetch_entity_pool(primary, refresh_key) if primary else []
            merged = news_sources.dedupe(team_news_normalized + entity_articles + general_pool)
            filtered = [a for a in merged if news_sources.article_relevance(a, team_terms) > 0]
            source_labels = self._collect_source_labels(filtered)

        sorted_articles = news_sources.sort_articles(filtered)[:8]

        return {
            "entity_type": entity_type,
            "terms": clean_terms,
            "source": ", ".join(source_labels) or "Multi-source NBA news (no matches)",
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "articles": sorted_articles,
        }

    @staticmethod
    def _expand_name_terms(terms: list[str]) -> list[str]:
        expanded: list[str] = []
        seen: set[str] = set()
        for term in terms:
            for candidate in (term, *term.split()):
                key = candidate.lower().strip()
                if len(key) >= 3 and key not in seen:
                    seen.add(key)
                    expanded.append(candidate)
        return expanded

    @staticmethod
    def _collect_source_labels(articles: list[dict[str, Any]]) -> list[str]:
        seen: list[str] = []
        for article in sorted(articles, key=lambda a: int(a.get("source_rank", 9))):
            label = article.get("source", "")
            if label and label not in seen:
                seen.append(label)
        return seen[:8]

    @lru_cache(maxsize=16)
    def _espn_news_for_refresh(self, refresh_key: str) -> list[dict[str, Any]]:
        del refresh_key
        return self._fetch_espn_news(limit=80)

    @lru_cache(maxsize=64)
    def _espn_team_news_for_refresh(self, team_code: str, refresh_key: str) -> list[dict[str, Any]]:
        del refresh_key
        return self._fetch_espn_team_news(team_code, limit=20)

    def _fetch_espn_news(self, limit: int = 40) -> list[dict[str, Any]]:
        try:
            response = requests.get(
                "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/news",
                params={"limit": limit},
                timeout=self.timeout,
                verify=False,
            )
            response.raise_for_status()
            return response.json().get("articles", [])
        except Exception:
            return []

    def _fetch_espn_team_news(self, team_code: str, limit: int = 20) -> list[dict[str, Any]]:
        try:
            response = requests.get(
                f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/{team_code}/news",
                params={"limit": limit},
                timeout=self.timeout,
                verify=False,
            )
            response.raise_for_status()
            return response.json().get("articles", [])
        except Exception:
            return []

    @staticmethod
    def _form_wins(last10: str) -> int:
        try:
            return int(str(last10).split("-")[0])
        except (TypeError, ValueError):
            return 0

    def _sentiment_for_terms(self, news: list[dict[str, Any]], terms: list[str], plus_minus: float) -> dict[str, Any]:
        lowered_terms = [term.lower() for term in terms if term]
        matches: list[tuple[float, float, str]] = []
        for article in news:
            headline = article.get("headline", "")
            description = article.get("description", "")
            haystack = f"{headline} {description}".lower()
            if any(term in haystack for term in lowered_terms):
                rank = int(article.get("source_rank", 3))
                weight = max(0.4, 1.05 - rank * 0.15)
                score = sentiment_score(f"{headline} {description}")
                matches.append((score, weight, article.get("source", "")))

        if matches:
            total_weight = sum(weight for _, weight, _ in matches) or 1.0
            weighted_score = sum(score * weight for score, weight, _ in matches) / total_weight
            sources_seen: list[str] = []
            for _, _, label in sorted(matches, key=lambda item: -item[1]):
                if label and label not in sources_seen:
                    sources_seen.append(label)
            return {
                "label": sentiment_label(weighted_score),
                "score": round(weighted_score, 2),
                "samples": len(matches),
                "sources": sources_seen[:5],
            }

        fallback = max(-1.0, min(1.0, float(plus_minus) / 12))
        return {"label": sentiment_label(fallback), "score": round(fallback, 2), "samples": 0, "sources": []}


def current_season(today: date | None = None) -> str:
    today = today or date.today()
    start_year = today.year if today.month >= 10 else today.year - 1
    return f"{start_year}-{str(start_year + 1)[-2:]}"


def season_id(season: str) -> str:
    return f"2{season.split('-')[0]}"


def common_dash_params(season: str, season_type: str, per_mode: str) -> dict[str, Any]:
    return {
        "LeagueID": "00",
        "Season": season,
        "SeasonType": season_type,
        "PerMode": per_mode,
        "MeasureType": "Base",
        "LastNGames": "0",
        "Month": "0",
        "OpponentTeamID": "0",
        "PaceAdjust": "N",
        "Period": "0",
        "PlusMinus": "N",
        "Rank": "N",
    }


def sentiment_score(text: str) -> float:
    words = {word.strip(".,:;!?()[]'\"").lower() for word in text.split()}
    positive = len(words & POSITIVE_WORDS)
    negative = len(words & NEGATIVE_WORDS)
    return max(-1.0, min(1.0, (positive - negative) / 3))


def sentiment_label(score: float) -> str:
    if score >= 0.25:
        return "Positive"
    if score <= -0.25:
        return "Concern"
    return "Neutral"


def playoff_round_sort(label: str) -> int:
    lowered = label.lower()
    if "first" in lowered or "1st" in lowered or "round 1" in lowered:
        return 1
    if "semifinal" in lowered:
        return 2
    if "nba final" in lowered or lowered.strip() == "finals":
        return 4
    if "final" in lowered:
        # "Conf. Finals"/"Conference Finals" - checked after "semifinal" so it
        # doesn't get caught by a bare "conf." substring match.
        return 3
    return 9


_ROUND_LABELS = {1: "First Round", 2: "Conf. Semifinals", 3: "Conf. Finals", 4: "NBA Finals"}


def playoff_round_label(sort_round: int) -> str:
    return _ROUND_LABELS.get(sort_round, "Playoffs")


def slugify(value: str) -> str:
    return "".join(character.lower() if character.isalnum() else "-" for character in value).strip("-").replace("--", "-")


def normalize_team_abbr(value: str) -> str:
    code = str(value or "").upper()
    return SCHEDULE_TEAM_ALIASES.get(code, code)


def team_logo_url(team_id: int) -> str:
    return f"https://cdn.nba.com/logos/nba/{team_id}/primary/L/logo.svg"


def player_headshot_url(player_id: int) -> str:
    return f"https://cdn.nba.com/headshots/nba/latest/1040x760/{player_id}.png"


def normalize_espn_article(article: dict[str, Any]) -> dict[str, Any]:
    images = article.get("images") or []
    links = article.get("links") or {}
    web_link = links.get("web") or {}
    image = next((item.get("url") for item in images if item.get("url")), "")
    return {
        "id": str(article.get("id", "")),
        "headline": article.get("headline") or article.get("title") or "NBA news update",
        "description": article.get("description") or "",
        "published": article.get("published") or article.get("lastModified") or "",
        "url": web_link.get("href") or "",
        "image": image,
        "source": article.get("source") or "ESPN",
    }


def games_back(team: dict[str, Any], teams: list[dict[str, Any]]) -> str:
    conference_teams = [row for row in teams if row["conference"] == team["conference"]]
    leader = max(conference_teams, key=lambda row: row["wins"] - row["losses"])
    gb = ((leader["wins"] - team["wins"]) + (team["losses"] - leader["losses"])) / 2
    return "-" if gb <= 0 else f"{gb:.1f}"


def seed_points(seed: int) -> float:
    return 118.0 - seed * 1.8


def seed_net_rating(seed: int) -> float:
    return round(10.0 - seed * 2.1, 1)


def advanced_fallback(net_rating: float) -> dict[str, float]:
    """Deterministic off/def rating, pace, and four-factors stand-ins when the
    NBA Stats Advanced endpoint is unreachable, derived from the net rating we
    already have so a team's fallback ratings stay internally consistent."""
    off_rtg = 113.0 + net_rating / 2
    return {
        "off_rtg": round(off_rtg, 1),
        "def_rtg": round(off_rtg - net_rating, 1),
        "pace": 99.5,
        "efg_pct": 53.0,
        "ts_pct": 56.5,
        "tov_pct": 13.0,
    }


def clutch_fallback(net_rating: float) -> dict[str, Any]:
    """Deterministic clutch-time stand-in when the NBA Stats clutch endpoint is
    unreachable, derived from season net rating so it stays internally consistent."""
    return {"clutch_record": "0-0", "clutch_net": round(net_rating / 3, 1)}


def form_margin_edge(home_last10: str, away_last10: str) -> float:
    """Points of home margin from recent-form momentum (capped, symmetric)."""
    home_wins = LeagueAnalyticsService._form_wins(home_last10)
    away_wins = LeagueAnalyticsService._form_wins(away_last10)
    edge = (home_wins - away_wins) * _FORM_POINTS_PER_WIN
    return max(-_FORM_POINTS_CAP, min(_FORM_POINTS_CAP, edge))


def home_road_split_edge(
    home_split_net: float | None,
    away_split_net: float | None,
    home_season_net: float,
    away_season_net: float,
) -> float:
    """Points of home margin added on top of blended season net rating once each team's
    home-only / road-only net rating is known. Missing splits (rare - only happens if the
    Location-filtered NBA Stats query fails) contribute nothing, matching the fallback
    behavior of the other pre-game adjustments."""
    if home_split_net is None or away_split_net is None:
        return 0.0
    blended_delta = (home_split_net - away_split_net) - (home_season_net - away_season_net)
    edge = blended_delta * _HOME_ROAD_SPLIT_WEIGHT
    return max(-_HOME_ROAD_SPLIT_CAP, min(_HOME_ROAD_SPLIT_CAP, edge))


def four_factors_edge(home_efg: float, away_efg: float, home_tov: float, away_tov: float) -> float:
    """Points of home margin from eFG% and TOV% - two of Dean Oliver's Four Factors.
    Higher eFG% (shoots more efficiently) and lower TOV% (protects the ball better)
    both favor that side; missing/zeroed stats simply contribute nothing thanks to
    the symmetric subtraction, matching the fallback behavior of the other edges."""
    efg_edge = (home_efg - away_efg) * _FOUR_FACTORS_EFG_WEIGHT
    tov_edge = (away_tov - home_tov) * _FOUR_FACTORS_TOV_WEIGHT
    edge = efg_edge + tov_edge
    return max(-_FOUR_FACTORS_CAP, min(_FOUR_FACTORS_CAP, edge))


def simulated_last10(wins: int, losses: int) -> str:
    games = max(wins + losses, 1)
    ratio = wins / games
    last_wins = max(1, min(9, round(ratio * 10)))
    return f"{last_wins}-{10 - last_wins}"


def streak_from_net(net: float) -> str:
    if net >= 8:
        return "W6"
    if net >= 4:
        return "W3"
    if net >= 0:
        return "W1"
    if net <= -8:
        return "L4"
    return "L1"


def power_ranking_blurb(team: dict[str, Any], form_pct: float, movement: int) -> str:
    """Plain-English one-liner for a team's power ranking slot."""
    net = team["net"]
    profile = "an elite two-way profile" if net >= 6 else "a positive net rating" if net >= 0 else "a net rating still trending negative"
    form_bit = "riding a hot streak" if form_pct >= 0.7 else "cold over their last 10" if form_pct <= 0.3 else "steady form"
    if movement >= 3:
        move_bit = f"ranked {movement} spots above their record"
    elif movement <= -3:
        move_bit = f"ranked {abs(movement)} spots below their record"
    else:
        move_bit = "ranked about where their record says they should be"
    return f"{team['team']} carries {profile} and are {form_bit}, {move_bit}."


def player_trend(points: float, plus_minus: float) -> list[float]:
    base = max(points, 1.0)
    return [
        round(max(0, base - 4 + plus_minus * 0.08), 1),
        round(max(0, base - 1.5), 1),
        round(max(0, base + plus_minus * 0.04), 1),
        round(max(0, base + 2.2), 1),
        round(max(0, base + plus_minus * 0.1), 1),
    ]


def synthetic_player_stats(seed: int, rank: int) -> dict[str, float]:
    starter_bonus = max(0, 6 - rank)
    seed_bonus = max(0, 6 - seed) * 0.45
    minutes = max(6.0, 36.0 - rank * 2.1 + starter_bonus)
    points = max(1.8, 22.0 - rank * 1.7 + seed_bonus)
    rebounds = max(1.0, 8.4 - rank * 0.42 + (rank % 3) * 0.8)
    assists = max(0.4, 6.2 - rank * 0.38 + (rank % 2) * 0.7)
    steals = max(0.1, 1.7 - rank * 0.08)
    blocks = max(0.0, 1.4 - rank * 0.07 + (1 if rank in {4, 5} else 0) * 0.45)
    plus_minus = round(8.5 - seed * 1.4 - rank * 0.35, 1)
    impact = points + rebounds * 1.05 + assists * 1.25 + steals * 2 + blocks * 1.8 + plus_minus * 0.4
    return {
        "min": round(minutes, 1),
        "pts": round(points, 1),
        "reb": round(rebounds, 1),
        "ast": round(assists, 1),
        "stl": round(steals, 1),
        "blk": round(blocks, 1),
        "fg_pct": round(50.5 - rank * 0.7 + seed_bonus, 1),
        "fg3_pct": round(39.0 - rank * 0.45, 1),
        "ft_pct": round(86.0 - rank * 0.35, 1),
        "plus_minus": plus_minus,
        "impact": round(impact, 1),
    }


def fallback_playoff_table() -> list[dict[str, Any]]:
    return [
        {"conference": "East", "matchup": "1 BOS vs 4 NYK", "series": "BOS 2-1", "leader": "BOS", "remaining": 4, "round": "First Round"},
        {"conference": "East", "matchup": "2 CLE vs 3 MIL", "series": "Tied 2-2", "leader": "Even", "remaining": 3, "round": "First Round"},
        {"conference": "West", "matchup": "1 OKC vs 4 DEN", "series": "OKC 2-1", "leader": "OKC", "remaining": 4, "round": "First Round"},
        {"conference": "West", "matchup": "2 MIN vs 3 DAL", "series": "DAL 2-1", "leader": "DAL", "remaining": 4, "round": "First Round"},
    ]


def fallback_upcoming_games() -> list[dict[str, Any]]:
    return [
        {"date": "2026-05-09T23:30Z", "matchup": "NYK @ BOS", "away": "NYK", "home": "BOS", "status": "Scheduled"},
        {"date": "2026-05-10T01:30Z", "matchup": "DEN @ OKC", "away": "DEN", "home": "OKC", "status": "Scheduled"},
        {"date": "2026-05-10T22:00Z", "matchup": "MIL @ CLE", "away": "MIL", "home": "CLE", "status": "Scheduled"},
    ]


def fallback_players() -> list[dict[str, Any]]:
    return [
        {"player": "Jayson Tatum", "team": "BOS", "pts": 29.4, "reb": 9.1, "ast": 5.8, "fg_pct": 47.2, "plus_minus": 7.4, "impact": 56.8, "sentiment": {"label": "Positive", "score": 0.62}},
        {"player": "Luka Doncic", "team": "DAL", "pts": 31.2, "reb": 8.7, "ast": 9.4, "fg_pct": 48.1, "plus_minus": 5.2, "impact": 58.1, "sentiment": {"label": "Positive", "score": 0.43}},
        {"player": "Shai Gilgeous-Alexander", "team": "OKC", "pts": 30.1, "reb": 6.3, "ast": 6.8, "fg_pct": 51.6, "plus_minus": 8.1, "impact": 55.9, "sentiment": {"label": "Positive", "score": 0.68}},
    ]


def fallback_teams() -> list[dict[str, Any]]:
    return [
        {"team": "Boston Celtics", "abbr": "BOS", "record": "7-2", "pts": 118.4, "reb": 44.2, "ast": 27.1, "net": 9.8, "fg_pct": 48.9, "sentiment": {"label": "Positive", "score": 0.7}},
        {"team": "Oklahoma City Thunder", "abbr": "OKC", "record": "6-3", "pts": 116.7, "reb": 42.6, "ast": 26.4, "net": 7.2, "fg_pct": 49.3, "sentiment": {"label": "Positive", "score": 0.55}},
        {"team": "Dallas Mavericks", "abbr": "DAL", "record": "5-4", "pts": 113.9, "reb": 40.8, "ast": 25.6, "net": 2.4, "fg_pct": 47.4, "sentiment": {"label": "Neutral", "score": 0.2}},
    ]
