"""Self-check for the Elo team-strength rating (538 NBA Elo methodology).

Run directly: python scripts/test_elo_ratings.py
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
    _ELO_EDGE_CAP,
    _ELO_INITIAL,
    _ELO_MEAN,
    elo_game_update,
    elo_strength_edge,
    elo_win_probability,
    regress_elo_to_mean,
)


def main() -> None:
    # Equal ratings -> home-court bump alone gives the home team the edge.
    prob = elo_win_probability(_ELO_INITIAL, _ELO_INITIAL)
    assert 0.5 < prob < 0.7, "home court alone should give a modest home edge"

    # No home-court adjustment and equal ratings -> a coin flip.
    assert abs(elo_win_probability(_ELO_INITIAL, _ELO_INITIAL, home_advantage=0.0) - 0.5) < 1e-9

    # A much stronger home team is heavily favored.
    assert elo_win_probability(1700, 1300) > 0.9

    # A home win updates ratings in the home team's favor, and conserves total rating
    # (a zero-sum update, like real Elo).
    home_after, away_after = elo_game_update(_ELO_INITIAL, _ELO_INITIAL, home_pts=110, away_pts=100)
    assert home_after > _ELO_INITIAL
    assert away_after < _ELO_INITIAL
    assert abs((home_after + away_after) - (_ELO_INITIAL * 2)) < 1e-6

    # An away win (upset, since home is favored pre-game) moves the away team's rating up.
    home_after, away_after = elo_game_update(_ELO_INITIAL, _ELO_INITIAL, home_pts=95, away_pts=100)
    assert away_after > _ELO_INITIAL
    assert home_after < _ELO_INITIAL

    # Bigger margin of victory -> bigger rating swing, all else equal.
    _, small_margin_away = elo_game_update(_ELO_INITIAL, _ELO_INITIAL, home_pts=101, away_pts=100)
    _, big_margin_away = elo_game_update(_ELO_INITIAL, _ELO_INITIAL, home_pts=130, away_pts=100)
    small_shift = abs(small_margin_away - _ELO_INITIAL)
    big_shift = abs(big_margin_away - _ELO_INITIAL)
    assert big_shift > small_shift, "a blowout should move ratings more than a nailbiter"

    # An underdog upset moves ratings more than the same result would for a favorite.
    _, underdog_home_after = elo_game_update(1300, 1700, home_pts=110, away_pts=100)
    _, favorite_home_after = elo_game_update(1700, 1300, home_pts=110, away_pts=100)
    assert (underdog_home_after - 1300) > (favorite_home_after - 1700), (
        "beating a stronger team should move the rating more than beating a weaker one"
    )

    # Season-boundary regression pulls every rating toward the league mean, never past it.
    high = regress_elo_to_mean(1700)
    low = regress_elo_to_mean(1300)
    assert _ELO_MEAN < high < 1700
    assert 1300 < low < _ELO_MEAN
    assert regress_elo_to_mean(_ELO_MEAN) == _ELO_MEAN

    # The margin-edge conversion is zero on equal ratings, signed correctly, and capped.
    assert elo_strength_edge(1500, 1500) == 0.0
    assert elo_strength_edge(1600, 1400) > 0
    assert elo_strength_edge(1400, 1600) < 0
    assert elo_strength_edge(2200, 800) == _ELO_EDGE_CAP
    assert elo_strength_edge(800, 2200) == -_ELO_EDGE_CAP

    print(
        "OK: Elo win-probability/update/regression/margin-edge behave like 538's NBA Elo "
        "(home-court bump, MOV + upset multiplier, zero-sum updates, mean reversion, signed+capped edge)"
    )


if __name__ == "__main__":
    main()
