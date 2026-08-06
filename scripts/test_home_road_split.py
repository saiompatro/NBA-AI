"""Self-check for the home/road split net-rating adjustment.

Run directly: python scripts/test_home_road_split.py
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
    _HOME_ROAD_SPLIT_CAP,
    home_road_split_edge,
)


def main() -> None:
    # Missing splits (query failed) must not move the margin at all.
    assert home_road_split_edge(None, -2.0, 5.0, -1.0) == 0.0
    assert home_road_split_edge(5.0, None, 5.0, -1.0) == 0.0

    # A home team that plays exactly to its season number, against a road team that
    # also plays exactly to its season number, should add nothing on top.
    assert home_road_split_edge(5.0, -1.0, 5.0, -1.0) == 0.0

    # Home team overperforms its season net rating at home -> positive (home-favoring) edge.
    edge = home_road_split_edge(home_split_net=9.0, away_split_net=-1.0, home_season_net=5.0, away_season_net=-1.0)
    assert edge > 0, "home team playing above its season number at home should help the home side"

    # Away team overperforms its season net rating on the road -> negative (away-favoring) edge.
    edge = home_road_split_edge(home_split_net=5.0, away_split_net=4.0, home_season_net=5.0, away_season_net=-1.0)
    assert edge < 0, "away team playing above its season number on the road should hurt the home side"

    # Extreme splits must stay capped.
    edge = home_road_split_edge(home_split_net=40.0, away_split_net=-40.0, home_season_net=0.0, away_season_net=0.0)
    assert edge == _HOME_ROAD_SPLIT_CAP, "edge must clamp at the positive cap"
    edge = home_road_split_edge(home_split_net=-40.0, away_split_net=40.0, home_season_net=0.0, away_season_net=0.0)
    assert edge == -_HOME_ROAD_SPLIT_CAP, "edge must clamp at the negative cap"

    print("OK: home/road split edge is zero on missing data, signed correctly, and capped")


if __name__ == "__main__":
    main()
