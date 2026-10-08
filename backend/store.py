"""Tiny SQLite persistence for the single Galaxy save slot."""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from typing import Any, Callable

DB_PATH = os.environ.get("DATABASE_PATH", os.path.join("data", "galaxy.db"))

_LOCK = threading.RLock()

_SCHEMA = """
CREATE TABLE IF NOT EXISTS game_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    data TEXT NOT NULL
)
"""


def _connect() -> sqlite3.Connection:
    directory = os.path.dirname(os.path.abspath(DB_PATH))
    os.makedirs(directory, exist_ok=True)
    connection = sqlite3.connect(DB_PATH, timeout=30)
    connection.execute(_SCHEMA)
    return connection


def _load_unlocked() -> dict[str, Any]:
    connection = _connect()
    try:
        row = connection.execute("SELECT data FROM game_state WHERE id = 1").fetchone()
        if row is None:
            connection.execute(
                "INSERT INTO game_state (id, data) VALUES (1, ?)", (json.dumps(_default()),)
            )
            connection.commit()
            return _default()
        return json.loads(row[0])
    finally:
        connection.close()


def _save_unlocked(state: dict[str, Any]) -> None:
    connection = _connect()
    try:
        connection.execute(
            "INSERT INTO game_state (id, data) VALUES (1, ?) "
            "ON CONFLICT(id) DO UPDATE SET data = excluded.data",
            (json.dumps(state),),
        )
        connection.commit()
    finally:
        connection.close()


def _default() -> dict[str, Any]:
    # Imported lazily so this module stays trivially importable on its own.
    from . import game

    return game.fresh()


def load() -> dict[str, Any]:
    with _LOCK:
        return _load_unlocked()


def update(mutate: Callable[[dict[str, Any]], None]) -> dict[str, Any]:
    """Load the save, hand it to ``mutate``, persist it and return the saved data.

    The whole read-modify-write cycle is serialised, so concurrent clicks and
    income ticks can never lose money.
    """
    with _LOCK:
        state = _load_unlocked()
        mutate(state)
        _save_unlocked(state)
        return state
