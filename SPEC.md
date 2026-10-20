# roam specification

Version 0.1.31 (2026-10-20; code 0.1.31). Owner: Chuck Forsyth.
Repository: `charles-forsyth/roam` (local checkout `~/Projects/roam`). License: MIT.

## 1. Purpose and scope

`roam` is a vehicle-aware routing, trip FinOps, and corridor intelligence CLI built on the **Google Maps Platform Routes API v2**, **Places API (New)**, **Weather API**, and **Elevation API**. It provides:

1. **Fleet-aware route calculation** (`roam DESTINATION [--with VEHICLE]`) with engine-specific eco-routing (`gasoline`, `hybrid`, `electric`, `diesel`), Normal vs. Econ MPG fuel cost estimation, and multi-vehicle comparison tables (`--compare` / `-C`).
2. **Segmented search along route** (`-F QUERY` / `--find QUERY`), including automated fuel price discovery (`fuelOptions`) and tax-free reservation fuel stop filtering (`-F taxfree`).
3. **Time-aware corridor weather** (`-W` / `--weather`), computing ETA at sampled waypoints along the route and selecting hourly forecast (<48h) or daily forecast (48h–240h) with QPF precipitation amounts.
4. **ASCII elevation profile** (`-E` / `--elevation`) and **HTML / Google Maps URL export** (`--html`, `--url`).
5. **DoorDash / IRS mileage tax-shelter & net profit calculator** (`roam doordash`).
6. **Persistent Fleet Garage (`garage.json`) and Saved Places (`places.json`)** in `~/.config/roam/`.

## 2. Design decisions

| # | Decision | Rationale |
|---|---|---|
| D1 | Dedicated per-tool config `~/.config/roam/` (`0600` `.env`, `garage.json`, `places.json`) | Keeps `GOOGLE_MAPS_API_KEY`, vehicle profiles (`VehicleConfig`), and saved place aliases isolated to `roam`. |
| D2 | Default origin resolves `"home"` from `places.json` | When `--origin` is omitted, `cli.py` looks up `"home"` (case-insensitive) in `~/.config/roam/places.json` before falling back to `"New York, NY"`. |
| D3 | Segmented polyline search (`search_along_route`) | Passing a full long-distance polyline to Places API `searchText` biases results toward the origin/midpoint. `roam` decodes the route polyline and queries segments along the corridor, deduplicating results by place ID and extracting live regular unleaded fuel prices (`fuelOptions.fuelPrices`). |
| D4 | Horizon-aware route weather (`get_hourly_forecast` vs `get_daily_forecast`) | Waypoints reached within 48 hours use `forecast/hours:lookup`; waypoints between 48 hours and 10 days out use `forecast/days:lookup` with quantitative precipitation (`qpf.quantity`); beyond 10 days, weather lookup is skipped cleanly. |
| D5 | Normal vs. Econ MPG fleet modeling (`mpg`, `mpg_econ`) | Hybrid vehicles (`SCRV`, `WCRV`) have distinct Normal (36.0 MPG) and Econ (44.0 MPG) fuel economy; `--econ` switches trip cost and `--compare` calculations to `mpg_econ`. |

## 3. Architecture

```text
roam CLI (src/roam/cli.py, Click CustomGroup)
  |-- Settings (src/roam/config.py)
  |     |-- ~/.config/roam/.env (GOOGLE_MAPS_API_KEY)
  |     |-- ~/.config/roam/garage.json (Dict[str, VehicleConfig])
  |     `-- ~/.config/roam/places.json (Dict[str, str])
  |-- RouteRequester (src/roam/core.py)
  |     |-- compute_route()        -> POST routes.googleapis.com/directions/v2:computeRoutes
  |     |-- search_along_route()   -> POST places.googleapis.com/v1/places:searchText (with routingParameters + fuelOptions)
  |     |-- get_weather()          -> GET weather.googleapis.com/v1/currentConditions:lookup
  |     |-- get_hourly_forecast()  -> GET weather.googleapis.com/v1/forecast/hours:lookup
  |     |-- get_daily_forecast()   -> GET weather.googleapis.com/v1/forecast/days:lookup
  |     `-- get_elevation()        -> GET maps.googleapis.com/maps/api/elevation/json
  `-- Calculators & Renderers (cli.py, utils.py)
        |-- decode_polyline() / sample_polyline() / haversine() (src/roam/utils.py)
        |-- Fleet comparison table (--compare / --econ)
        |-- DoorDash IRS mileage ($0.67/mi) & fuel depreciation calculator (`roam doordash`)
        `-- ASCII elevation chart, Rich turn-by-turn tables, Google Maps URL & HTML report
```

### Module map

| File | Responsibility |
|---|---|
| `src/roam/cli.py` | Click `CustomGroup` routing default positional `roam DEST` to `go`, plus subcommands `garage-add`, `garage-list`, `garage-remove`, `places-add`, `places-list`, `places-remove`, and `doordash`. |
| `src/roam/config.py` | `VehicleConfig` Pydantic model (`mode`, `engine`, `avoid_tolls`, `avoid_highways`, `avoid_ferries`, `mpg`, `mpg_econ`) and `Settings` managing `~/.config/roam/{.env,garage.json,places.json}`. |
| `src/roam/core.py` | `RouteRequester` session client for Google Maps Routes v2, Places v1, Weather v1, and Elevation APIs. |
| `src/roam/utils.py` | `decode_polyline()`, `encode_polyline()`, `sample_route_points()`, `format_duration()`, `meters_to_miles()`, HTML report generator. |

## 4. External APIs and field masks

| API | Endpoint | Key Header / FieldMask |
|---|---|---|
| Routes API v2 | `POST https://routes.googleapis.com/directions/v2:computeRoutes` | `X-Goog-FieldMask: routes.duration,routes.distanceMeters,routes.polyline.encodedPolyline,routes.legs,routes.travelAdvisory` |
| Places API (New) | `POST https://places.googleapis.com/v1/places:searchText` | `X-Goog-FieldMask: places.displayName,places.formattedAddress,places.location,places.rating,places.fuelOptions,routingSummaries` |
| Weather API v1 | `GET https://weather.googleapis.com/v1/{currentConditions,forecast/hours,forecast/days}:lookup` | `key=GOOGLE_MAPS_API_KEY` |
| Elevation API | `GET https://maps.googleapis.com/maps/api/elevation/json` | `key=GOOGLE_MAPS_API_KEY` |

## 5. Configuration (`~/.config/roam/`)

### `~/.config/roam/.env`
```env
GOOGLE_MAPS_API_KEY=AIza...
```

### `~/.config/roam/garage.json` (`VehicleConfig`)
```json
{
  "SCRV": {
    "mode": "drive",
    "engine": "hybrid",
    "avoid_tolls": true,
    "avoid_highways": false,
    "avoid_ferries": false,
    "mpg": 36.0,
    "mpg_econ": 44.0
  }
}
```

## 6. CLI interface

```text
roam [DESTINATION]
     [--origin ORIGIN | -o ORIGIN]
     [--with VEHICLE | -w VEHICLE]
     [--mode {drive,bicycle,walk,two_wheeler,transit} | -m ...]
     [--engine {gasoline,electric,hybrid,diesel} | -e ...]
     [--avoid-tolls | -T]
     [--avoid-highways | -H]
     [--avoid-ferries]
     [--directions | -d]
     [--find QUERY | -F QUERY]
     [--weather | -W]
     [--elevation | -E]
     [--compare | -C]
     [--econ]
     [--mpg FLOAT]
     [--gas-price FLOAT]                  # default: 3.99
     [--depart-in HOURS]
     [--url]
     [--html]

Subcommands:
  roam garage-add NAME [--mode ...] [--engine ...] [--mpg FLOAT] [--mpg-econ FLOAT] [-T] [-H]
  roam garage-list
  roam garage-remove NAME
  roam places-add ALIAS ADDRESS
  roam places-list
  roam places-remove ALIAS
  roam doordash --start LOC --end LOC --miles FLOAT --earnings FLOAT [--mpg FLOAT] [--gas-price FLOAT]
```

## 7. Requirements traceability

| ID | Requirement | Verified by |
|---|---|---|
| REQ-ROUTE-1 | `compute_route` sends `travelMode`, `routingPreference="TRAFFIC_AWARE"`, `routeModifiers`, and `vehicleInfo.emissionType`. | `tests/test_core.py::test_compute_route_mock` |
| REQ-GARAGE-1 | Vehicles can be added, persisted to `garage.json` (including `mpg` and `mpg_econ`), and listed. | `tests/test_garage.py::test_garage_add_and_list` |
| REQ-PLACES-1 | Saved place aliases can be added, persisted to `places.json`, and resolved in routing commands. | `tests/test_places.py::test_places_add_and_list` |
| REQ-CMP-1 | `--compare` and `--econ` compute multi-vehicle fuel usage and cost tables across the garage. | `tests/test_cli.py::test_compare_and_econ_options` |
| REQ-DD-1 | `roam doordash` computes IRS mileage deduction ($0.67/mi), fuel cost, and net profit. | `tests/test_cli.py::test_doordash_command` |
| REQ-SRCH-1 | `search_along_route` queries Places API along route segments and parses fuel prices. | `tests/test_search.py::test_search_along_route_mock` |
| REQ-WX-1 | Route weather selects hourly forecast (<48h), daily forecast (48h–240h) with QPF display, and skips >240h. | `tests/test_weather_logic.py`, `tests/test_weather_qpf.py`, `tests/test_weather_route.py`, `tests/test_daily_weather_fix.py` |

## 8. Known gaps and backlog

- **K1 (Confirmed):** Two root-level debug scripts (`debug_hourly.py`, `debug_weather.py`) remain in the repository root from earlier Weather API prototyping; moving them to `scripts/` or removing them will tidy the top-level layout.
- **K2 (Confirmed):** `Settings.model_config` checks `./.env` before `~/.config/roam/.env`; prioritizing `~/.config/roam/.env` prevents unrelated project `.env` files from overriding `GOOGLE_MAPS_API_KEY`.
