"""FastAPI entry point for Galaxy — office clicker."""

from __future__ import annotations

import os
import secrets
from pathlib import Path
from typing import Any, Callable

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import game, store

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")

app = FastAPI(title="Galaxy", docs_url="/api/docs", openapi_url="/api/openapi.json")


class LoginBody(BaseModel):
    password: str = ""


class ClickBoostBody(BaseModel):
    enabled: bool


def _with_state(mutate: Callable[[dict[str, Any]], None] | None = None) -> dict[str, Any]:
    """Accrue income, apply ``mutate`` if given, save and return a snapshot."""
    box: dict[str, Any] = {}

    def apply(stored: dict[str, Any]) -> None:
        state = game.parse(stored)
        game.accrue(state)
        if mutate is not None:
            mutate(state)
        stored.update(game.dump(state))
        box["snapshot"] = game.snapshot(state)

    store.update(apply)
    return box["snapshot"]


# ------------------------------------------------------------------- game


@app.get("/api/state")
def get_state() -> dict[str, Any]:
    return _with_state()


@app.post("/api/click")
def click() -> dict[str, Any]:
    def mutate(state: dict[str, Any]) -> None:
        gained = game.click_income(state)
        state["clicks"] += 1
        state["money"] = game.add(state["money"], gained)
        state["total_earned"] = game.add(state["total_earned"], gained)

    return _with_state(mutate)


@app.post("/api/buy/{upgrade_id}")
def buy(upgrade_id: str) -> dict[str, Any]:
    def mutate(state: dict[str, Any]) -> None:
        upgrade = game.upgrade_by_id(upgrade_id)
        if upgrade is None:
            raise HTTPException(status_code=404, detail="Unknown upgrade")
        if upgrade["floor"] > game.floor_of(state["total_earned"]):
            raise HTTPException(status_code=400, detail=f"Unlocks on floor {upgrade['floor']}")
        cost = game.upgrade_cost(upgrade, state["counts"].get(upgrade_id, 0))
        if state["money"] < cost:
            raise HTTPException(status_code=400, detail="Not enough money")
        state["money"] = game.add(state["money"], -cost)
        state["counts"][upgrade_id] = state["counts"].get(upgrade_id, 0) + 1
        if upgrade.get("infinite"):
            state["infinite_income"] = True

    return _with_state(mutate)


# ------------------------------------------------------------------ admin


def _require_admin(key: str | None) -> None:
    if not ADMIN_PASSWORD:
        raise HTTPException(status_code=503, detail="No admin password configured")
    if not key or not secrets.compare_digest(key, ADMIN_PASSWORD):
        raise HTTPException(status_code=401, detail="Wrong admin password")


@app.post("/api/admin/login")
def admin_login(body: LoginBody) -> dict[str, bool]:
    _require_admin(body.password)
    return {"ok": True}


@app.post("/api/admin/grant")
def admin_grant(x_admin_key: str | None = Header(default=None)) -> dict[str, Any]:
    _require_admin(x_admin_key)

    def mutate(state: dict[str, Any]) -> None:
        state["money"] = game.add(state["money"], game.HUNDRED_NONILLION)
        state["total_earned"] = game.add(state["total_earned"], game.HUNDRED_NONILLION)

    return _with_state(mutate)


@app.post("/api/admin/click-boost")
def admin_click_boost(
    body: ClickBoostBody, x_admin_key: str | None = Header(default=None)
) -> dict[str, Any]:
    _require_admin(x_admin_key)

    def mutate(state: dict[str, Any]) -> None:
        state["admin_click_boost"] = body.enabled

    return _with_state(mutate)


@app.post("/api/admin/reset")
def admin_reset(x_admin_key: str | None = Header(default=None)) -> dict[str, Any]:
    _require_admin(x_admin_key)

    def mutate(state: dict[str, Any]) -> None:
        state.clear()
        state.update(game.parse(game.fresh()))

    return _with_state(mutate)


# ------------------------------------------------------------------- pages


@app.get("/")
def index() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/admin")
def admin_page() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "admin.html")


app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")
