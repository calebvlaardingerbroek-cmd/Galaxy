"""Galaxy — office clicker game rules.

Single source of truth for floors, upgrades, awards and money maths.

Money is kept as an exact Python ``int`` (arbitrary precision) so it can grow
past nonillion.  "Infinite" income is ``math.inf`` internally and travels over
the API as the string ``"Infinity"``.
"""

from __future__ import annotations

import math
import time
from typing import Any

INFINITY = math.inf

TOTAL_FLOORS = 40
BASE_CLICK = 1
NONILLION = 10 ** 30
HUNDRED_NONILLION = 100 * NONILLION

FLOOR_NAMES = [
    "Mail Room",
    "Reception",
    "Open Plan",
    "Break Room",
    "Supply Closet",
    "IT Helpdesk",
    "Sales Floor",
    "Accounting",
    "Legal",
    "Marketing",
    "Human Resources",
    "Call Center",
    "Data Entry",
    "QA Lab",
    "R&D Wing",
    "Server Room",
    "Product Design",
    "Data Center",
    "Trading Desk",
    "Executive Suite",
    "Board Room",
    "Sky Lounge",
    "Robotics Bay",
    "AI Lab",
    "Quantum Floor",
    "Mega Corp HQ",
    "Orbital Lobby",
    "Launch Deck",
    "Satellite Ops",
    "Lunar Office",
    "Mars Branch",
    "Asteroid Mine",
    "Deep Space Ops",
    "Orbital HQ",
    "Galactic HQ",
    "Nebula Tower",
    "Star Forge",
    "Black Hole Bank",
    "Cosmic Boardroom",
    "Singularity Suite",
]

# ``click`` = money per click, ``sec`` = money per second.
# ``growth`` is the cost multiplier applied per already-owned unit (as a
# fraction, so the arithmetic stays in exact integers).
UPGRADES: list[dict[str, Any]] = [
    {"id": "stapler", "name": "Office Stapler", "text": "+1 per click", "cost": 10, "growth": (5, 4), "click": 1, "sec": 0, "floor": 1},
    {"id": "intern", "name": "Unpaid Intern", "text": "+1 per second", "cost": 40, "growth": (5, 4), "click": 0, "sec": 1, "floor": 1},
    {"id": "desk", "name": "Standing Desk", "text": "+5 per click", "cost": 350, "growth": (5, 4), "click": 5, "sec": 0, "floor": 2},
    {"id": "assistant", "name": "Executive Assistant", "text": "+6 per second", "cost": 1_200, "growth": (5, 4), "click": 0, "sec": 6, "floor": 4},
    {"id": "team", "name": "Department Team", "text": "+40 per second", "cost": 25_000, "growth": (5, 4), "click": 0, "sec": 40, "floor": 7},
    {"id": "callcenter", "name": "Call Center", "text": "+300 per second", "cost": 600_000, "growth": (5, 4), "click": 0, "sec": 300, "floor": 10},
    {"id": "serverfarm", "name": "Server Farm", "text": "+2,500 per second", "cost": 20_000_000, "growth": (5, 4), "click": 0, "sec": 2_500, "floor": 14},
    {"id": "megacorp", "name": "Mega Corporation", "text": "+30,000 per second", "cost": 5_000_000_000, "growth": (5, 4), "click": 0, "sec": 30_000, "floor": 20},
    {"id": "orbital", "name": "Orbital HQ", "text": "+5,000,000 per second", "cost": 10 ** 15, "growth": (5, 4), "click": 0, "sec": 5_000_000, "floor": 28},
    {"id": "infinity", "name": "Infinity Engine", "text": "Income becomes ∞", "cost": 10 ** 30, "growth": (2, 1), "click": 0, "sec": 0, "floor": 40, "infinite": True},
]

# Each award doubles all income. They are earned automatically from total earnings.
AWARDS: list[dict[str, Any]] = [
    {"id": "bronze", "name": "Bronze Plaque", "requirement": 10 ** 3},
    {"id": "silver", "name": "Silver Stapler", "requirement": 10 ** 4},
    {"id": "gold", "name": "Golden Memo", "requirement": 10 ** 5},
    {"id": "month", "name": "Employee of the Month", "requirement": 10 ** 6},
    {"id": "regional", "name": "Regional Award", "requirement": 10 ** 7},
    {"id": "national", "name": "National Award", "requirement": 10 ** 8},
    {"id": "global", "name": "Global Award", "requirement": 10 ** 9},
    {"id": "orbital", "name": "Orbital Award", "requirement": 10 ** 10},
    {"id": "galactic", "name": "Galactic Trophy", "requirement": 10 ** 11},
    {"id": "singularity", "name": "Singularity Prize", "requirement": 10 ** 12},
]
AWARD_MULTIPLIER = 2


# ------------------------------------------------------------------ numbers


def _num(value: Any) -> int | float:
    """Read a stored value back into an exact number (int or ``inf``)."""
    if isinstance(value, str):
        return INFINITY if value.startswith("Inf") or value == "∞" else int(value)
    if value is None:
        return 0
    if isinstance(value, float) and not math.isfinite(value):
        return INFINITY
    return int(value)


def _dump(value: int | float) -> str:
    """Serialise a number for the API (always a string, never a float)."""
    return "Infinity" if value == INFINITY else str(int(value))


def add(left: int | float, right: int | float) -> int | float:
    if left == INFINITY or right == INFINITY:
        return INFINITY
    return left + right


# -------------------------------------------------------------- progression


def floor_requirement(floor: int) -> int:
    """Total earnings needed to unlock ``floor``."""
    return 0 if floor <= 1 else 100 * 2 ** (floor - 2)


def floor_of(total_earned: int | float) -> int:
    floor = 1
    for candidate in range(2, TOTAL_FLOORS + 1):
        if total_earned >= floor_requirement(candidate):
            floor = candidate
        else:
            break
    return floor


def award_ids(total_earned: int | float) -> list[str]:
    return [award["id"] for award in AWARDS if total_earned >= award["requirement"]]


def income_multiplier(total_earned: int | float) -> int:
    """Floors multiply income, every earned award doubles it again."""
    return floor_of(total_earned) * AWARD_MULTIPLIER ** len(award_ids(total_earned))


def upgrade_by_id(upgrade_id: str) -> dict[str, Any] | None:
    for upgrade in UPGRADES:
        if upgrade["id"] == upgrade_id:
            return upgrade
    return None


def upgrade_cost(upgrade: dict[str, Any], owned: int) -> int:
    numerator, denominator = upgrade["growth"]
    return upgrade["cost"] * numerator ** owned // denominator ** owned


def click_income(state: dict[str, Any]) -> int | float:
    if state["infinite_income"]:
        return INFINITY
    if state["admin_click_boost"]:
        return HUNDRED_NONILLION
    base = BASE_CLICK + sum(u["click"] * state["counts"].get(u["id"], 0) for u in UPGRADES)
    return base * income_multiplier(state["total_earned"])


def income_per_sec(state: dict[str, Any]) -> int | float:
    if state["infinite_income"]:
        return INFINITY
    base = sum(u["sec"] * state["counts"].get(u["id"], 0) for u in UPGRADES)
    return base * income_multiplier(state["total_earned"])


# ------------------------------------------------------------------- state


def fresh() -> dict[str, Any]:
    """A brand new save, in stored (JSON friendly) form."""
    return {
        "money": "0",
        "total_earned": "0",
        "clicks": 0,
        "counts": {},
        "infinite_income": False,
        "admin_click_boost": False,
        "last_accrued": time.time(),
    }


def parse(stored: dict[str, Any]) -> dict[str, Any]:
    """Stored form -> exact form used by the game maths."""
    return {
        "money": _num(stored.get("money", 0)),
        "total_earned": _num(stored.get("total_earned", 0)),
        "clicks": int(stored.get("clicks") or 0),
        "counts": {str(key): int(value) for key, value in (stored.get("counts") or {}).items()},
        "infinite_income": bool(stored.get("infinite_income")),
        "admin_click_boost": bool(stored.get("admin_click_boost")),
        "last_accrued": float(stored.get("last_accrued") or 0.0),
    }


def dump(state: dict[str, Any]) -> dict[str, Any]:
    """Exact form -> stored form."""
    return {
        "money": _dump(state["money"]),
        "total_earned": _dump(state["total_earned"]),
        "clicks": state["clicks"],
        "counts": dict(state["counts"]),
        "infinite_income": bool(state["infinite_income"]),
        "admin_click_boost": bool(state["admin_click_boost"]),
        "last_accrued": state["last_accrued"],
    }


def accrue(state: dict[str, Any], now: float | None = None) -> None:
    """Pay out per-second income earned since the last request."""
    now = time.time() if now is None else now
    elapsed_ms = int((now - float(state.get("last_accrued") or 0.0)) * 1000)
    if elapsed_ms > 0:
        rate = income_per_sec(state)
        if rate == INFINITY:
            state["money"] = INFINITY
            state["total_earned"] = INFINITY
        elif rate > 0:
            gained = rate * elapsed_ms // 1000
            if gained:
                state["money"] = add(state["money"], gained)
                state["total_earned"] = add(state["total_earned"], gained)
    state["last_accrued"] = now


# ------------------------------------------------------------------- views


def snapshot(state: dict[str, Any]) -> dict[str, Any]:
    """Everything the client needs to draw the game."""
    total = state["total_earned"]
    money = state["money"]
    floor = floor_of(total)
    earned = award_ids(total)

    return {
        "player": {
            "money": _dump(money),
            "total_earned": _dump(total),
            "clicks": state["clicks"],
            "floor": floor,
            "total_floors": TOTAL_FLOORS,
            "click_income": _dump(click_income(state)),
            "income_per_sec": _dump(income_per_sec(state)),
            "awards": earned,
            "infinite_income": bool(state["infinite_income"]),
            "admin_click_boost": bool(state["admin_click_boost"]),
        },
        "upgrades": [
            {
                "id": upgrade["id"],
                "name": upgrade["name"],
                "text": upgrade["text"],
                "count": state["counts"].get(upgrade["id"], 0),
                "cost": _dump(upgrade_cost(upgrade, state["counts"].get(upgrade["id"], 0))),
                "unlock_floor": upgrade["floor"],
                "locked": upgrade["floor"] > floor,
                "affordable": money >= upgrade_cost(upgrade, state["counts"].get(upgrade["id"], 0)),
                "infinite": bool(upgrade.get("infinite")),
            }
            for upgrade in UPGRADES
        ],
        "awards": [
            {
                "id": award["id"],
                "name": award["name"],
                "requirement": _dump(award["requirement"]),
                "multiplier": AWARD_MULTIPLIER,
                "earned": award["id"] in earned,
            }
            for award in AWARDS
        ],
        "floors": [
            {
                "number": number,
                "name": FLOOR_NAMES[number - 1],
                "requirement": _dump(floor_requirement(number)),
                "unlocked": number <= floor,
                "current": number == floor,
            }
            for number in range(1, TOTAL_FLOORS + 1)
        ],
    }
