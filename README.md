# <img src="assets/logo.png" width="100" height="100" align="left" style="margin-right: 20px;"> Roam 🗺️

**The Personal Routing Commander.**

Roam is a CLI tool designed to generate the perfect route for **your specific vehicle** and **current intent**. It uses the Google Maps Routes API v2 to calculate paths based on engine type, travel mode, and personal preferences.

<br clear="left"/>

## Features

*   **🏎️ The Garage:** Define your fleet (e.g., "tesla", "scooter", "truck") with specific routing rules (EV efficiency, avoid highways, etc.).
*   **📍 Address Book:** Save common locations like `home`, `work`, or `gym` for quick access.
*   **🧭 Smart Routing:** Supports `drive`, `bicycle`, `two_wheeler`, `transit`, and `walk`.
*   **🔋 Eco-Aware:** Optimizes for engine type (`gasoline`, `electric`, `hybrid`, `diesel`).
*   **🗣️ Turn-by-Turn:** Get detailed directions directly in your terminal.
*   **🔍 Search Along Route:** Find "gas", "coffee", or "EV charging" without leaving your path (Segmented Search for full coverage).
*   **☀️ Weather Aware:** Check hourly weather forecast for points along the route (Time-zone aware).
*   **⛰️ Elevation Profile:** Visualize the terrain with an ASCII elevation chart.
*   **💰 Trip Costs:** See real fuel prices and estimated trip costs.
*   **📤 Sharing:** Generate Google Maps URLs and HTML reports.

## Installation

Install directly via `uv`:

```bash
uv tool install git+https://github.com/charles-forsyth/roam.git
```

## Configuration

1.  **Get a Google Maps API Key**: Ensure the following APIs are enabled:
    *   **Routes API**
    *   **Places API (New)**
    *   **Weather API** (optional)
    *   **Elevation API** (optional)
2.  **Set the Key**:
    *   Create `~/.config/roam/.env` and add: `GOOGLE_MAPS_API_KEY=your_key_here`
    *   OR export it: `export GOOGLE_MAPS_API_KEY=your_key_here`

## Usage

### 🚀 Routing
```bash
# Basic routing (from New York to LA)
roam "Los Angeles"

# With a saved place and preset vehicle
roam work --with tesla

# Custom ad-hoc routing with shortcuts
roam "San Francisco" -m two_wheeler -H

# Turn-by-turn directions
roam "Home" -d
```

### 🔍 Search & Weather
```bash
# Find places along the route (e.g. gas)
roam "Las Vegas" -F "gas"

# Check weather conditions
roam "Seattle" -W
```

### ⛰️ Elevation & Reports
```bash
# View Elevation Profile
roam "Lake Tahoe" -E

# Export HTML Report
roam "Portland" --html
```

### 🏎️ Managing Your Garage
```bash
# Add a vehicle
roam garage add "tesla" --mode drive --engine electric --avoid-tolls

# List vehicles
roam garage list

# Use a vehicle
roam "Las Vegas" --with tesla
```

### 📍 Managing Places
```bash
# Add a place
roam places add home "1539 Button Hill Road, Tioga, PA 16946"

# List places
roam places list

# Use a place as origin/destination
roam home --origin work
```

## Development

1.  Clone the repo.
2.  Install `uv`.
3.  Run setup:
    ```bash
    uv sync
    ```
4.  Run tests:
    ```bash
    uv run pytest
    ```
