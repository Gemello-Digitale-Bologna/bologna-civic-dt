# bologna-civic-dt — the urban pack of the Civic Digital Twin (CDT)

A proof-of-concept tool for citizen co-design workshops on urban space
transformation with nature-based solutions. It reimplements a paper-based
method — citizens place intervention cards (add trees, change ground cover,
add water features, ...) on a printed map — as a digital twin: a facilitator
places the same interventions on a live 2D map and 3D view of a real site,
and the scene plus a set of indicators (CO2, thermal comfort, accessibility,
cost, space use) update immediately.

This is the **urban pack**, and the app: it's built on the core,
[civic-engagement](https://github.com/fbk-most/civic-engagement), which
holds what every domain shares (the API, sessions and scenarios, the 2D map
and the 3D view). The pack holds the urban domain: sites, cards, model,
indicators, ingestion and data.

| | |
| --- | --- |
| `bologna_civic_dt/` | the backend: the pack (`pack.py`), sites, cards, model, indicators, felt temperature, ingestion |
| `frontend/` | the app: the pack's side of the interface (`src/pack.ts`), built on the core's |
| `data/<site>/` | each site's baseline, terrain grid and scenarios (and its session) |
| `tests/` | the pack's tests |
| `docs/` | the model guide (`model.md`) and a demo storyline (`demo-utopia.md`) |

The sites (see `bologna_civic_dt/sites.py`): Piazza Dante, Utopia — an
imaginary city, built on the data of Piazza Dante in Trento — and Piazza
XX Settembre, Bologna. The app supports one active site per process —
switch sites by relaunching with `CIVIC_ENGAGEMENT_SITE=<site_id>` (defaults
to `piazza_dante`), not live in-session.

## Status

Early PoC, in active development. What's still to do is in `TODO.md` (and
in the core's).

## The core

The pack is built on a specific commit of the core, for both the backend
(`pyproject.toml`) and the app (`frontend/package.json`), fetched from its
public repository on GitHub when installing. To move to another commit of
the core:

```bash
python3 scripts/core.py <commit>
```

To develop the core and the pack together, point the pack at a local
checkout of the core (beside this one by default), and back to a commit
before committing:

```bash
python3 scripts/core.py local [../civic-engagement]
```

The app's dev server then serves the core's sources from that checkout, and
reloads with their changes; the typecheck reads npm's copy, refreshed by
running the script again. A git hook refuses a commit with a local core:
`cp scripts/pre-commit .git/hooks/`.

## Backend

Python 3.12, managed with [uv](https://docs.astral.sh/uv/). From the
repository's root, which holds `data/`:

```bash
uv sync

# One-off: fetch OSM data for the active site and build the baseline
# (CIVIC_ENGAGEMENT_SITE selects the site; defaults to piazza_dante)
uv run python -m bologna_civic_dt.ingestion.build_baseline

# Run the API
uv run uvicorn bologna_civic_dt.main:app --reload
# Or, for the other site:
CIVIC_ENGAGEMENT_SITE=piazza_xx_settembre uv run uvicorn bologna_civic_dt.main:app --reload

# Start from a saved scenario instead of the last session (see the core's README)
CIVIC_ENGAGEMENT_SCENARIO=demo uv run uvicorn bologna_civic_dt.main:app

# Tests
uv run pytest
```

Piazza Dante has **terrain**, from the 2014 LiDAR DTM; Piazza XX Settembre
is flat, for now:

```bash
uv run python -m bologna_civic_dt.ingestion.build_terrain --dtm data/piazza_dante/lidar/dtm_2014.asc
```

The models behind the indicators and the felt temperature still take the
ground as flat: the terrain only changes what the 3D view shows.

The model — tree growth, and the indicators computed over the 30-year
horizon — is a [civic-digital-twins](https://github.com/fbk-most/civic-digital-twins)
model (a dependency installed by uv), in `bologna_civic_dt/`. The backend
evaluates it once per set of interventions, for every year at once, and
serves the scene and the indicators for the year asked. `docs/model.md`
explains the approach.

Felt temperature is a second model (`bologna_civic_dt/thermal_field.py`):
a 1 m grid over the site, hour by hour through one day, from the shade of
buildings, trees and pergolas (real sun position for the date), the ground's
surface and a typical day's air temperature for Trento, warming over the
years by a climate assumption (a summer like 2022 becomes the usual one in
ten years, see `CLIMATE_WARMING_C`). It is evaluated on
demand — `GET /api/thermal-field?t=&month=&day=` — and its values at a
reference moment (21 June, 11:00) are the thermal indicators. A cheap,
uncalibrated proxy: see `parameters.py`.

`tests/test_reference.py` checks that what the backend serves is unchanged
against outputs recorded in `tests/fixtures/reference/`, for both sites. It
is temporary: it guards the restructuring of the model and goes once that is
over. When a change is meant to alter the numbers, re-record the reference
with `CIVIC_ENGAGEMENT_SITE=<site_id> uv run python tests/reference/capture.py`
(once per site) and review the differences before committing.

## Frontend

The app, in `frontend/`:

```bash
cd frontend
npm install
npm run dev       # http://localhost:5173, proxies /api to the backend on :8000
npm run typecheck && npm run lint
```

For workshops, demos and performance measurements, use the production build
(see the core's README for why):

```bash
npm run build && npm run preview   # http://localhost:4173, same proxy
```

The interface, the 3D view and the URL parameters are the core's: see its
README.

## Licence and data sources

The code is released under the [Apache License 2.0](LICENSE).

The site baselines (`data/*/baseline.json`) and Piazza Dante's terrain grid
are derived from third-party data:

- **OpenStreetMap**: buildings, streets, paths, trees, street furniture and
  ground covers. © OpenStreetMap contributors, available under the
  [Open Database License](https://www.openstreetmap.org/copyright).
- **Provincia autonoma di Trento**: the terrain, building heights and roof
  shapes for Piazza Dante from the 2014 LiDAR survey, and roof colours from
  the 2015 orthophoto. The source rasters are not in the repository (see the
  core's `civic_engagement/ingestion/lidar.py` and `ortofoto.py`).
