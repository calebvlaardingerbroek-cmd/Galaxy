# Galaxy — notes for future sessions

## Shape of the app

FastAPI serves both the API and the static front end from one process (single
origin, no CORS needed). There is no build step and no bundler.

- `backend/game.py` — **the single source of truth** for floors, upgrades,
  awards and all money maths. Change balance numbers here, not in the client.
- `backend/store.py` — the whole save is one JSON row (`id = 1`) in SQLite.
  `store.update(fn)` serialises the read-modify-write cycle; always mutate
  through it so concurrent clicks cannot lose money.
- `backend/main.py` — routes. `_with_state()` accrues per-second income, applies
  the optional mutator, saves, and returns the client snapshot.
- `frontend/` — plain HTML/CSS/JS. `app.js` polls `GET /api/state` every second;
  income is accrued server-side from the `last_accrued` timestamp, so there is
  no client-side currency math to drift.

## Number handling (non-obvious)

Money is an exact Python `int` — it must reach 10^32 (nonillion) and beyond, so
it is **never** a float and never a JSON number. It crosses the wire as a
**string**, and `"Infinity"` marks infinite income (the Infinity Engine).
On the client, `fmt()` and all comparisons use `BigInt`, which is why `app.js`
converts with `BigInt(...)` before arithmetic.

`int * float` arithmetic is avoided in `accrue()` on purpose: it multiplies by
elapsed milliseconds and divides by 1000 in integer space so huge rates stay
exact.

## Sandbox / dev environment

- `docker compose -f docker-compose.base44.yml up -d --build` brings it up on
  host port 3000 (container 8000).
- The compose service runs `python:3.12-slim` with the repo bind-mounted and
  `uvicorn --reload` on `/app/backend`; `pip install` runs at container start.
  Python-only edits therefore hot-reload with no rebuild.
- The SQLite file lives in the `galaxy_data` volume at `/data/galaxy.db`
  (`DATABASE_PATH`), not in the repo.
- `ADMIN_PASSWORD` comes from `.env.base44-defaults` (`changeme`) unless the
  dashboard secret of the same name is set, which is loaded last and wins.
- `BASE44_PREVIEW_MODE` is not used: the app has no host/origin allowlist to
  relax and no sandbox-only code path.

## Verifying it works

```sh
curl -s localhost:3000/api/state | head -c 400     # snapshot JSON
curl -s -X POST localhost:3000/api/click -o /dev/null -w '%{http_code}\n'
curl -s -X POST localhost:3000/api/buy/intern      # 400 until you can afford it
curl -s -X POST localhost:3000/api/admin/grant -H 'X-Admin-Key: changeme'
```

The admin panel is at `/admin` (password gate, then grant / click-boost / reset).
