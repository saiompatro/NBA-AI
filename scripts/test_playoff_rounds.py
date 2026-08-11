"""Self-check for playoff round classification (used by the bracket view).

Run directly: python scripts/test_playoff_rounds.py
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

from app.services.league_analytics import playoff_round_label, playoff_round_sort


def main() -> None:
    assert playoff_round_sort("Round 1") == 1
    assert playoff_round_sort("First Round") == 1
    assert playoff_round_sort("Conf. Semifinals") == 2
    # regression: "Conf. Finals" contains the substring "conf." and used to be
    # misclassified into the semifinals bucket alongside "Conf. Semifinals".
    assert playoff_round_sort("Conf. Finals") == 3, "conference finals must not collide with semifinals"
    assert playoff_round_sort("Conference Finals") == 3
    assert playoff_round_sort("NBA Finals") == 4
    assert playoff_round_sort("Finals") == 4
    assert playoff_round_sort("") == 9

    assert playoff_round_label(1) == "First Round"
    assert playoff_round_label(2) == "Conf. Semifinals"
    assert playoff_round_label(3) == "Conf. Finals"
    assert playoff_round_label(4) == "NBA Finals"
    assert playoff_round_label(9) == "Playoffs"

    print("OK: playoff round labels are distinct for semis vs. conf. finals vs. NBA finals")


if __name__ == "__main__":
    main()
