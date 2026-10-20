# <img src="assets/logo.png" width="100" height="100" align="left" style="margin-right: 20px;"> Roam

**The Personal Routing & Fleet FinOps Commander (`v0.1.31`).**

Roam is a CLI tool designed to calculate optimal routes for **your specific vehicle fleet** and **current intent** using the Google Maps Routes API v2, Places API (New), Weather API, and Elevation API.

<br clear="left"/>

See [SPEC.md](SPEC.md) for the full system specification, architecture, API field masks, and requirement traceability.

## Features

* **The Garage (`garage.json`):** Define your vehicle fleet (`mode`, `engine`, `avoid_tolls`, `avoid_highways`, `mpg`, `mpg_econ`) and compare trip fuel costs across every vehicle with `--compare` (`-C`) and `--econ`.
* **Saved Places (`places.json`):** Save common locations (`home`, `work`, `campus`) for instant origin/destination resolution.
* **Eco-Aware Routing:** Supports `drive`, `bicycle`, `two_wheeler`, `transit`, and `walk`, plus engine emission optimization (`gasoline`, `electric`, `hybrid`, `diesel`).
* **Search Along Route (`-F`):** Find `"gas"`, `"coffee"`, or `"EV charging"` along the route corridor with live fuel price discovery (`fuelOptions`) and tax-free fuel stop filtering (`-F taxfree`).
* **Horizon-Aware Corridor Weather (`-W`):** Checks hourly (<48h) or daily (48h–10d) weather and precipitation (QPF) at waypoints timed to your arrival.
* **ASCII Elevation Profile (`-E`):** Visualizes route terrain and elevation gain/loss in the terminal.
* **DoorDash / Mileage Ledger (`roam doordash`):** Calculates IRS mileage tax shelter ($0.67/mi), fuel cost, and net shift profit.
* **Sharing (`--url`, `--html`):** Generates shareable Google Maps URLs and standalone HTML trip reports.

## Installation

Install directly via `uv`:

```bash
uv tool install --python 3.12 git+https://github.com/charles-forsyth/roam.git
```

## Configuration

1. **Google Maps Platform API Key**: Enable the following APIs in your Google Cloud project:
   * **Routes API**
   * **Places API (New)**
   * **Weather API**
   * **Elevation API**
2. **Configure `~/.config/roam/.env`** (`chmod 600`):
   ```env
   GOOGLE_MAPS_API_KEY=your_key_here
   ```

## Usage

### 1. Routing & Fleet Comparison
```bash
# Route from default 'home' place to a destination
roam "State College, PA"

# Route using a specific garage vehicle
roam "State College, PA" --with SCRV

# Compare fuel usage & cost across all garaged vehicles (and in Econ mode)
roam "State College, PA" --compare
roam "State College, PA" --compare --econ

# Turn-by-turn directions & shareable Google Maps link
roam "State College, PA" -d --url
```

### 2. Search Along Route, Weather & Elevation
```bash
# Find gas stations with live fuel prices along the route
roam "Syracuse, NY" -F "gas"

# Check arrival-timed weather and elevation profile along the route
roam "Syracuse, NY" -W -E

# Export an HTML trip report
roam "Syracuse, NY" -W -E --html
```

### 3. Managing Your Garage
```bash
roam garage-add "SCRV" --mode drive --engine hybrid --mpg 36.0 --mpg-econ 44.0 --avoid-tolls
roam garage-list
roam garage-remove "SCRV"
```

### 4. Managing Saved Places
```bash
roam places-add home "123 Main St, Springfield, IL"
roam places-add work "900 University Ave, Riverside, CA"
roam places-list
roam work --origin home
```

### 5. Mileage & Shift Tax Shelter Calculator
```bash
roam doordash --start home --end home --miles 32.30 --earnings 45.00 --mpg 36.0 --gas-price 3.99
```

## Development

```bash
uv sync --python 3.12
uv run --python 3.12 pytest
uv run --python 3.12 ruff check .
```
