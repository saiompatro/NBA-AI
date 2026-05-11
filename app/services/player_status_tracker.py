from __future__ import annotations

from typing import Any


_FOUL_OUT_THRESHOLD = 6

_EJECTABLE_SUBTYPES = {"flagrant.type2", "flagrant2", "double.technical"}

_PERSONAL_FOUL_SUBTYPES = {
    "personal",
    "offensive",
    "personal.take",
    "personal.block",
    "shooting",
    "personal.charge",
    "loose.ball",
    "away.from.play",
}

_INJURY_KEYWORDS = {
    "injury",
    "injured",
    "will not return",
    "left game",
    "ruled out",
    "x-ray",
    "x ray",
    "ambulance",
    "stretcher",
    "concussion",
}

# Minutes elapsed per period boundary (to estimate time-of-absence)
_PERIOD_MINUTES = {1: 0, 2: 12, 3: 24, 4: 36}


def _clock_to_minutes(clock: str) -> float:
    clean = clock.replace("PT", "").replace("M", ":").replace("S", "")
    try:
        minutes, seconds = clean.split(":")
        return int(minutes) + float(seconds) / 60
    except (ValueError, AttributeError):
        return 0.0


def _elapsed_minutes(period: int, clock: str) -> float:
    base = _PERIOD_MINUTES.get(min(period, 4), 36)
    remaining_in_period = _clock_to_minutes(clock)
    return base + (12.0 - remaining_in_period)


def _description_has_injury(description: str) -> bool:
    lower = (description or "").lower()
    return any(kw in lower for kw in _INJURY_KEYWORDS)


def track(
    actions: list[dict[str, Any]],
    home_team_id: int | str,
    away_team_id: int | str,
    rotation_minutes: dict[int, float] | None = None,
) -> dict[str, Any]:
    """Parse PBP actions and return out-player lists + per-player foul counts.

    Args:
        actions: NBA live play-by-play action list (ordered oldest → newest).
        home_team_id: NBA teamId for the home team.
        away_team_id: NBA teamId for the away team.
        rotation_minutes: Optional map of player_id → avg minutes/game for
            injury-via-long-absence detection. Only starters (avg >= 25 mpg)
            are checked.

    Returns:
        {
            "home_out": [...],  # list of out-player dicts
            "away_out": [...],
            "personal_fouls": {player_id: int, ...},
        }
    """
    home_team_id = str(home_team_id)
    away_team_id = str(away_team_id)
    rotation_minutes = rotation_minutes or {}

    personal_fouls: dict[str, int] = {}
    tech_fouls: dict[str, int] = {}
    ejected: dict[str, dict[str, Any]] = {}       # player_id → info dict
    fouled_out: dict[str, dict[str, Any]] = {}    # player_id → info dict
    substituted_out: dict[str, dict[str, Any]] = {}  # player_id → info dict (last sub-out)
    substituted_in: set[str] = set()
    injured_out: dict[str, dict[str, Any]] = {}   # player_id → info dict

    def _player_info(action: dict[str, Any]) -> dict[str, Any]:
        pid = str(action.get("personId") or action.get("player1Id") or "")
        name = (
            action.get("playerNameI")
            or action.get("playerName")
            or action.get("player1Name")
            or "Unknown"
        )
        team_id = str(action.get("teamId") or "")
        return {
            "player_id": pid,
            "name": name,
            "team_id": team_id,
            "period": action.get("period", 0),
            "clock": action.get("clock") or action.get("gameClock") or "",
        }

    for action in actions:
        action_type = (action.get("actionType") or "").lower()
        sub_type = (action.get("subType") or "").lower()
        qualifiers = [str(q).lower() for q in (action.get("qualifiers") or [])]
        description = action.get("description") or action.get("descriptor") or ""
        pid = str(action.get("personId") or action.get("player1Id") or "")
        if not pid:
            continue

        # --- Ejections ---
        is_ejection = (
            action_type == "ejection"
            or "ejection" in qualifiers
            or sub_type in _EJECTABLE_SUBTYPES
        )
        if is_ejection and pid not in ejected:
            info = _player_info(action)
            reason = f"ejection ({sub_type or action_type})" if sub_type else "ejection"
            ejected[pid] = {**info, "reason": reason}

        # --- Technical fouls (2 techs = ejection) ---
        if action_type == "foul" and sub_type == "technical":
            tech_fouls[pid] = tech_fouls.get(pid, 0) + 1
            if tech_fouls[pid] >= 2 and pid not in ejected:
                info = _player_info(action)
                ejected[pid] = {**info, "reason": "ejection (2 technicals)"}

        # --- Flagrant 2 (auto-eject) ---
        if action_type == "foul" and "flagrant" in sub_type and "2" in sub_type:
            if pid not in ejected:
                info = _player_info(action)
                ejected[pid] = {**info, "reason": "ejection (flagrant 2)"}

        # --- Personal fouls (foul-out at 6) ---
        if action_type == "foul" and sub_type in _PERSONAL_FOUL_SUBTYPES:
            personal_fouls[pid] = personal_fouls.get(pid, 0) + 1
            if personal_fouls[pid] >= _FOUL_OUT_THRESHOLD and pid not in fouled_out:
                info = _player_info(action)
                fouled_out[pid] = {**info, "reason": f"fouled out ({personal_fouls[pid]} personal fouls)"}

        # --- Substitutions ---
        if action_type == "substitution":
            if sub_type == "out":
                info = _player_info(action)
                # Check if injury is mentioned in description
                if _description_has_injury(description):
                    injured_out[pid] = {**info, "reason": "injury (play-by-play)"}
                else:
                    substituted_out[pid] = info
                substituted_in.discard(pid)
            elif sub_type == "in":
                substituted_in.add(pid)
                substituted_out.pop(pid, None)
                injured_out.pop(pid, None)

        # --- Injury mentioned for a player already out ---
        if _description_has_injury(description) and pid in substituted_out:
            info = substituted_out.pop(pid)
            injured_out[pid] = {**info, "reason": "injury (play-by-play)"}

    # Long-absence detection: starters who've been out >8 game-minutes without returning
    last_action = actions[-1] if actions else {}
    current_period = int(last_action.get("period") or 1)
    current_clock = last_action.get("clock") or last_action.get("gameClock") or "PT12M00.00S"
    current_elapsed = _elapsed_minutes(current_period, current_clock)

    for pid, info in list(substituted_out.items()):
        if pid in ejected or pid in fouled_out or pid in injured_out:
            continue
        avg_min = rotation_minutes.get(int(pid) if pid.isdigit() else -1, 0)
        if avg_min < 25:
            continue
        absence_elapsed = current_elapsed - _elapsed_minutes(info["period"], info["clock"])
        if absence_elapsed >= 8:
            injured_out[pid] = {**info, "reason": "possible injury (extended absence)"}

    # Build per-team out lists
    all_out: dict[str, dict[str, Any]] = {}
    for pid, info in ejected.items():
        all_out[pid] = info
    for pid, info in fouled_out.items():
        if pid not in all_out:
            all_out[pid] = info
    for pid, info in injured_out.items():
        if pid not in all_out:
            all_out[pid] = info

    home_out = [info for info in all_out.values() if info.get("team_id") == home_team_id]
    away_out = [info for info in all_out.values() if info.get("team_id") == away_team_id]

    return {
        "home_out": home_out,
        "away_out": away_out,
        "personal_fouls": {pid: count for pid, count in personal_fouls.items()},
    }
