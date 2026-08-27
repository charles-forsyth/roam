import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from roam.config import settings, VehicleConfig
from roam.core import RouteRequester
from roam.utils import (
    decode_polyline,
    get_nearest_point_on_polyline,
    calculate_cumulative_distances,
    generate_ascii_chart,
    get_timezone_at_point,
)
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import sys
import urllib.parse

console = Console(record=True)


class DefaultGroup(click.Group):
    """
    A Click Group that invokes a default command if a subcommand is not found.
    """

    def __init__(self, *args, **kwargs):
        self.default_command = kwargs.pop("default_command", None)
        super().__init__(*args, **kwargs)

    def resolve_command(self, ctx, args):
        if args and args[0] in self.commands:
            return super().resolve_command(ctx, args)

        if self.default_command and args and not args[0].startswith("-"):
            # If the first argument is not a flag and not a subcommand, treat as default command
            return (
                self.default_command,
                self.get_command(ctx, self.default_command),
                args,
            )

        return super().resolve_command(ctx, args)


@click.group(
    cls=DefaultGroup,
    default_command="route",
    context_settings={"help_option_names": ["-h", "--help"]},
)
def cli():
    """
    \b
    Roam: The Personal Routing Commander.
    -----------------------------------
    Calculate routes, manage your vehicle fleet, and save favorite places.

    \b
    Examples:
      roam "Los Angeles"
      roam "Work" --with tesla
      roam "Las Vegas" -m two_wheeler -H --weather
    """
    pass


def format_duration(seconds_str):
    try:
        total_seconds = int(seconds_str.replace("s", ""))
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        if hours > 0:
            return f"{hours}h {minutes}m"
        return f"{minutes}m"
    except Exception:
        return seconds_str


def get_seconds(duration_str):
    try:
        return int(duration_str.replace("s", ""))
    except Exception:
        return 0


def format_price_level(level):
    mapping = {
        "PRICE_LEVEL_INEXPENSIVE": "$",
        "PRICE_LEVEL_MODERATE": "$$",
        "PRICE_LEVEL_EXPENSIVE": "$$$",
        "PRICE_LEVEL_VERY_EXPENSIVE": "$$$$",
    }
    return mapping.get(level, level) if level else "-"


def get_fuel_price_float(place):
    """Extracts Regular Unleaded float price if available."""
    fuel_options = place.get("fuelOptions", {})
    prices = fuel_options.get("fuelPrices", [])

    for p in prices:
        if p.get("type") == "REGULAR_UNLEADED":
            price_obj = p.get("price", {})
            units = int(price_obj.get("units", 0))
            nanos = int(price_obj.get("nanos", 0))
            return units + (nanos / 1_000_000_000)

    return None


def get_fuel_price(place):
    """Extracts Regular Unleaded price if available."""
    val = get_fuel_price_float(place)
    if val is not None:
        return f"${val:.2f}"
    return None


def find_forecast_for_time(forecast_data, target_time, max_diff_seconds=7200):
    """
    Finds the hourly forecast entry closest to target_time.
    If the closest match is further than max_diff_seconds, returns None.
    """
    hourly = forecast_data.get("forecastHours", [])
    if not hourly:
        return None

    closest = None
    min_diff = float("inf")

    for entry in hourly:
        forecast_time_str = entry.get("interval", {}).get("startTime")
        if not forecast_time_str:
            continue

        try:
            f_time = datetime.fromisoformat(forecast_time_str.replace("Z", "+00:00"))
            diff = abs((f_time - target_time).total_seconds())

            if diff < min_diff:
                min_diff = diff
                closest = entry
        except ValueError:
            continue

    if closest and min_diff > max_diff_seconds:
        return None

    return closest


def find_daily_forecast_for_date(daily_data, target_date):
    """
    Finds the daily forecast entry for target_date.
    target_date should be a date object.
    """
    days = daily_data.get("forecastDays", [])
    for entry in days:
        date_str = entry.get("interval", {}).get("startTime")
        if not date_str:
            continue
        try:
            # Weather API date_str is usually "YYYY-MM-DDTHH:MM:SSZ"
            f_date = datetime.fromisoformat(date_str.replace("Z", "+00:00")).date()
            if f_date == target_date:
                return entry
        except ValueError:
            continue
    return None


def generate_maps_url(origin, destination, mode):
    """Generates a Universal Google Maps URL."""
    base = "https://www.google.com/maps/dir/?api=1"

    # Map roam modes to Google Maps travelmode
    mode_map = {
        "drive": "driving",
        "bicycle": "bicycling",
        "two_wheeler": "driving",  # Maps URL doesn't support 2-wheeler mode explicitly
        "transit": "transit",
        "walk": "walking",
    }

    params = {
        "origin": origin,
        "destination": destination,
        "travelmode": mode_map.get(mode, "driving"),
    }

    return f"{base}&{urllib.parse.urlencode(params)}"


def parse_start_time(start_str, date_str, origin_tz_str):
    """
    Parses start time and date into a timezone-aware datetime object.
    Defaults to now if not provided.
    """
    tz = ZoneInfo(origin_tz_str)
    now = datetime.now(tz)

    target_date = now.date()

    if date_str:
        if date_str.lower() == "today":
            target_date = now.date()
        elif date_str.lower() == "tomorrow":
            target_date = now.date() + timedelta(days=1)
        else:
            try:
                target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                raise click.BadParameter(
                    f"Invalid date format: {date_str}. Use YYYY-MM-DD, 'today', or 'tomorrow'."
                )

    if start_str:
        # Try parsing various time formats
        parsed_time = None
        time_formats = [
            "%H:%M",
            "%I:%M %p",
            "%I:%M%p",
            "%I %p",
            "%I%p",
        ]  # e.g., 14:30, 02:30 PM, 2:30pm, 2 PM, 2pm

        start_str_clean = start_str.strip()
        for fmt in time_formats:
            try:
                parsed_time = datetime.strptime(start_str_clean, fmt).time()
                break
            except ValueError:
                continue

        if not parsed_time:
            raise click.BadParameter(
                f"Invalid start time format: {start_str}. Use 'HH:MM' or '02:30 PM'."
            )

        departure_dt = datetime.combine(target_date, parsed_time, tzinfo=tz)
    else:
        if date_str:
            # Date specified without time: default to 08:00 AM on that date
            default_time = datetime.strptime("08:00", "%H:%M").time()
            departure_dt = datetime.combine(target_date, default_time, tzinfo=tz)
        else:
            departure_dt = now

    return departure_dt


def get_mpg_for_vehicle(v_name: str, v_cfg: VehicleConfig, econ_mode: bool) -> float:
    """Helper to determine effective MPG for a vehicle."""
    if econ_mode and v_cfg.mpg_econ:
        return v_cfg.mpg_econ
    if v_cfg.mpg:
        return v_cfg.mpg
    # Defaults based on vehicle name / mode
    if "Rig" in v_name or "Towing" in v_name:
        return 9.5
    if "Daytona" in v_name or "Truck" in v_name:
        return 11.0
    if "CRV" in v_name or "SCRV" in v_name or "WCRV" in v_name:
        return 44.0 if econ_mode else 36.0
    return 25.0


@cli.command()
@click.argument("destination")
@click.option(
    "-f",
    "-o",
    "--origin",
    default=None,
    help="Starting point (address or saved place). Defaults to 'home' if set.",
)
@click.option(
    "-m",
    "--mode",
    type=click.Choice(["drive", "bicycle", "two_wheeler", "transit", "walk"]),
    default="drive",
    help="Travel mode (default: drive). Example: -m bicycle",
)
@click.option(
    "-e",
    "--engine",
    type=click.Choice(["gasoline", "electric", "hybrid", "diesel"]),
    default=None,
    help="Vehicle engine type for eco-routing (only for drive mode). Example: -e electric",
)
@click.option(
    "-t",
    "--avoid-tolls",
    is_flag=True,
    default=False,
    help="Avoid toll roads where possible.",
)
@click.option(
    "-H",
    "--avoid-highways",
    is_flag=True,
    default=False,
    help="Avoid highways (good for scooters/scenic routes).",
)
@click.option(
    "-w",
    "--with",
    "vehicle_name",
    default=None,
    help="Load settings from a saved vehicle in your garage. Example: --with SCRV",
)
@click.option(
    "-C",
    "--compare",
    is_flag=True,
    default=False,
    help="Compare travel time, fuel burned, and cost across all garaged vehicles.",
)
@click.option(
    "-P",
    "--gas-price",
    type=float,
    default=None,
    help="Gas price per gallon for trip cost calculation (default: $3.99 or auto-discovered).",
)
@click.option(
    "--econ/--normal",
    default=False,
    help="Toggle Econ drive mode for hybrid vehicles (e.g. 44 MPG vs 36 MPG).",
)
@click.option(
    "-d",
    "--directions",
    is_flag=True,
    default=False,
    help="Display step-by-step navigation instructions.",
)
@click.option(
    "-F",
    "--find",
    multiple=True,
    help="Search for places along the route path. Can be used multiple times. Example: -F gas -F coffee",
)
@click.option(
    "-W",
    "--weather",
    is_flag=True,
    default=False,
    help="Fetch hourly weather forecast for points along the route.",
)
@click.option(
    "-s",
    "--start",
    default=None,
    help="Departure time (e.g. '08:00 AM' or '14:30'). Defaults to now.",
)
@click.option(
    "-D",
    "--date",
    default=None,
    help="Departure date (e.g. '2025-12-25' or 'tomorrow'). Defaults to today.",
)
@click.option(
    "-E",
    "--elevation",
    is_flag=True,
    default=False,
    help="Display elevation profile chart for the route.",
)
@click.option(
    "-u",
    "--url",
    is_flag=True,
    default=False,
    help="Generate a Google Maps URL for this route.",
)
@click.option(
    "--html",
    is_flag=True,
    default=False,
    help="Export the route report to 'roam_report.html'.",
)
def route(
    destination,
    origin,
    mode,
    engine,
    avoid_tolls,
    avoid_highways,
    vehicle_name,
    compare,
    gas_price,
    econ,
    directions,
    find,
    weather,
    start,
    date,
    elevation,
    url,
    html,
):
    """
    \b
    Calculate a route to DESTINATION.

    DESTINATION can be a city ("Los Angeles"), an address ("123 Main St"), or a saved place name ("work").

    \b
    Examples:
      roam "New York"
      roam "Gym" --origin "Work"
      roam "Seattle" -W -s "08:00 AM" -D "tomorrow"
      roam "Brushwood" --with Daytona-Rig -F gas -F coffee
      roam "Trumansburg" --compare
    """
    if settings is None:
        console.print(
            "[bold red]Error:[/] Settings not initialized. Check your GOOGLE_MAPS_API_KEY environment variable."
        )
        sys.exit(1)

    places = settings.load_places()
    garage = settings.load_garage()

    # Resolve origin
    if not origin:
        if "home" in places:
            origin = places["home"]
            console.print(f"[dim]Resolved origin 'home' to: {origin}[/dim]")
        else:
            console.print(
                "[bold red]Error:[/] No origin specified, and no 'home' place is set. "
                "Use -f/--origin or set a 'home' place with 'roam places add home <address>'."
            )
            sys.exit(1)
    else:
        if origin.lower() in places:
            resolved = places[origin.lower()]
            console.print(f"[dim]Resolved origin '{origin}' to: {resolved}[/dim]")
            origin = resolved

    # Resolve destination
    if destination.lower() in places:
        resolved = places[destination.lower()]
        console.print(f"[dim]Resolved destination '{destination}' to: {resolved}[/dim]")
        destination = resolved

    # Load vehicle preset if provided
    selected_vehicle_config = None
    if vehicle_name:
        # Case insensitive matching
        matched_key = None
        for k in garage:
            if k.lower() == vehicle_name.lower():
                matched_key = k
                break

        if matched_key:
            selected_vehicle_config = garage[matched_key]
            mode = selected_vehicle_config.mode
            if selected_vehicle_config.engine:
                engine = selected_vehicle_config.engine
            if selected_vehicle_config.avoid_tolls:
                avoid_tolls = True
            if selected_vehicle_config.avoid_highways:
                avoid_highways = True
            console.print(f"[dim]Using garage preset: {matched_key}[/dim]")
        else:
            console.print(
                f"[yellow]Warning:[/] Vehicle '{vehicle_name}' not found in garage. Using provided/default options."
            )

    requester = RouteRequester(settings.google_maps_api_key)

    msg = f"Routing from {origin} to {destination} via {mode}"
    if engine:
        msg += f" ({engine})"
    if avoid_tolls or avoid_highways:
        avoids = []
        if avoid_tolls:
            avoids.append("tolls")
        if avoid_highways:
            avoids.append("highways")
        msg += f" no {', '.join(avoids)}"
    msg += "..."

    console.print(Panel(msg, title="Roam", border_style="cyan"))

    try:
        route_data = requester.compute_route(
            origin=origin,
            destination=destination,
            mode=mode,
            engine_type=engine,
            avoid_tolls=avoid_tolls,
            avoid_highways=avoid_highways,
        )

        routes = route_data.get("routes", [])
        if not routes:
            console.print("[bold red]Error:[/] No routes found.")
            sys.exit(1)

        primary_route = routes[0]
        distance_meters = primary_route.get("distanceMeters", 0)
        duration_str = primary_route.get("duration", "0s")

        distance_miles = distance_meters / 1609.344
        formatted_dist = f"{distance_miles:.2f} miles"
        formatted_dur = format_duration(duration_str)

        console.print(f"[bold]Distance:[/] {formatted_dist}")
        console.print(f"[bold]Duration:[/] {formatted_dur}")

        # Decode polyline for spatial features
        polyline = primary_route.get("polyline", {}).get("encodedPolyline")
        route_points = decode_polyline(polyline) if polyline else []

        # Find gas price automatically if -F gas is used
        discovered_gas_price = None
        find_results = {}

        if find and route_points:
            cum_dists = calculate_cumulative_distances(route_points)
            for query in find:
                console.print(f"\n[bold cyan]Searching for '{query}'...[/]")
                places_found = requester.search_along_route(
                    query, polyline if polyline else ""
                )
                if not places_found:
                    console.print(f"[dim]No places found for '{query}'.[/dim]")
                    continue

                annotated = []
                for p in places_found:
                    loc = p.get("location", {})
                    plat = loc.get("latitude")
                    plng = loc.get("longitude")

                    if plat and plng:
                        pt_idx, path_dist = get_nearest_point_on_polyline(
                            (plat, plng), route_points, cum_dists
                        )
                        route_pt = route_points[pt_idx]
                        from math import radians, cos, sin, asin, sqrt

                        lat1, lon1, lat2, lon2 = map(
                            radians, [plat, plng, route_pt[0], route_pt[1]]
                        )
                        dlon = lon2 - lon1
                        dlat = lat2 - lat1
                        a = (
                            sin(dlat / 2) ** 2
                            + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
                        )
                        c = 2 * asin(sqrt(a))
                        detour_m = 6371000 * c

                        annotated.append(
                            {
                                "place": p,
                                "trip_dist_m": path_dist,
                                "detour_m": detour_m,
                            }
                        )

                annotated.sort(key=lambda x: x["trip_dist_m"])
                find_results[query] = annotated

                # Check if query is gas related and discover best low-detour gas price
                if "gas" in query.lower() or "fuel" in query.lower():
                    for item in annotated:
                        price_val = get_fuel_price_float(item["place"])
                        if (
                            price_val and item["detour_m"] < 1609.34
                        ):  # under 1 mile detour
                            if (
                                discovered_gas_price is None
                                or price_val < discovered_gas_price
                            ):
                                discovered_gas_price = price_val

                # Render Table for Places
                table = Table(
                    title=f"{query.title()} Stops (Trip Order)",
                    header_style="bold magenta",
                )
                table.add_column("Trip Mile", justify="right")
                table.add_column("Detour", justify="right")
                table.add_column("Name")
                table.add_column("Rating")
                table.add_column("Price")
                table.add_column("Address")

                for item in annotated:
                    p = item["place"]
                    t_mile = f"{item['trip_dist_m'] / 1609.344:.1f} mi"
                    detour_mi = item["detour_m"] / 1609.344
                    detour_str = f"+{detour_mi:.1f} mi"

                    name = p.get("displayName", {}).get("text", "Unknown")
                    rating = p.get("rating", "-")
                    user_ratings = p.get("userRatingCount", 0)
                    rating_str = f"{rating} ({user_ratings})" if rating != "-" else "-"

                    price_str = format_price_level(p.get("priceLevel"))
                    fuel_price = get_fuel_price(p)
                    if fuel_price:
                        price_str = fuel_price

                    addr = p.get("formattedAddress", "-")

                    table.add_row(t_mile, detour_str, name, rating_str, price_str, addr)

                console.print(table)

        # Determine effective gas price
        effective_gas_price = gas_price
        if effective_gas_price is None:
            if discovered_gas_price:
                effective_gas_price = discovered_gas_price
                console.print(
                    f"\n[dim]Auto-discovered lowest gas price along route: ${effective_gas_price:.2f}/gal[/dim]"
                )
            else:
                effective_gas_price = 3.99

        # Render Multi-Vehicle Comparison if --compare is set
        if compare:
            console.print("\n[bold cyan]=== Multi-Vehicle Fleet Comparison ===[/]")
            comp_table = Table(header_style="bold yellow")
            comp_table.add_column("Vehicle")
            comp_table.add_column("Mode / Engine")
            comp_table.add_column("MPG Rating", justify="right")
            comp_table.add_column("Fuel Needed", justify="right")
            comp_table.add_column(
                f"Est. Gas Cost (${effective_gas_price:.2f}/gal)", justify="right"
            )

            if not garage:
                # Add default fallback
                comp_table.add_row(
                    "Default Drive",
                    "drive/gasoline",
                    "25.0 MPG",
                    f"{distance_miles / 25.0:.2f} gal",
                    f"${(distance_miles / 25.0) * effective_gas_price:.2f}",
                )
            else:
                for v_name, v_cfg in garage.items():
                    v_mpg = get_mpg_for_vehicle(v_name, v_cfg, econ)
                    gallons = distance_miles / v_mpg
                    cost = gallons * effective_gas_price
                    engine_str = v_cfg.engine or v_cfg.mode
                    if econ and v_cfg.mpg_econ:
                        engine_str += " (Econ)"
                    comp_table.add_row(
                        v_name,
                        engine_str,
                        f"{v_mpg:.1f} MPG",
                        f"{gallons:.2f} gal",
                        f"${cost:.2f}",
                    )

            console.print(comp_table)

        # Single Vehicle Fuel Cost Calculation
        if selected_vehicle_config or vehicle_name or not compare:
            v_key = vehicle_name or "Default"
            v_cfg = selected_vehicle_config or VehicleConfig(mode=mode, engine=engine)
            v_mpg = get_mpg_for_vehicle(v_key, v_cfg, econ)
            gallons_needed = distance_miles / v_mpg
            trip_cost = gallons_needed * effective_gas_price
            console.print(
                f"[dim]Fuel Estimate ({v_key} @ {v_mpg:.1f} MPG, ${effective_gas_price:.2f}/gal): {gallons_needed:.2f} gal | ${trip_cost:.2f}[/dim]"
            )

        # Elevation Profile
        if elevation and route_points:
            console.print("\n[bold cyan]Fetching elevation profile...[/]")
            elevations = requester.get_elevation_profile(route_points, samples=60)
            if elevations:
                chart = generate_ascii_chart(elevations)
                console.print(chart)

        # Weather Forecast
        if weather and route_points:
            console.print("\n[bold cyan]Fetching weather forecast along route...[/]")
            origin_tz = get_timezone_at_point(route_points[0][0], route_points[0][1])
            departure_dt = parse_start_time(start, date, origin_tz)

            console.print(
                f"[dim]Route Forecast: Departing at {departure_dt.strftime('%Y-%m-%d %I:%M %p')} ({origin_tz})[/dim]"
            )

            # Sample 5 points along route
            sample_indices = [
                0,
                len(route_points) // 4,
                len(route_points) // 2,
                (len(route_points) * 3) // 4,
                len(route_points) - 1,
            ]
            sample_labels = [
                "Start",
                "En Route (+25%)",
                "Halfway (+50%)",
                "En Route (+75%)",
                "Destination",
            ]

            w_table = Table(header_style="bold green")
            w_table.add_column("Location / Time (Local)")
            w_table.add_column("Forecast Temp")
            w_table.add_column("Condition")
            w_table.add_column("Precip %")

            total_dur_sec = get_seconds(duration_str)

            for idx, label in zip(sample_indices, sample_labels):
                pt = route_points[idx]
                frac = idx / (len(route_points) - 1) if len(route_points) > 1 else 0
                point_dt = departure_dt + timedelta(seconds=total_dur_sec * frac)

                point_tz = get_timezone_at_point(pt[0], pt[1])
                local_dt = point_dt.astimezone(ZoneInfo(point_tz))

                w_data = requester.get_weather_forecast(pt[0], pt[1])
                if w_data:
                    fc = find_forecast_for_time(w_data, point_dt)
                    if fc:
                        temp = fc.get("temperature", {}).get("value", "-")
                        unit = fc.get("temperature", {}).get("unit", "F")
                        cond = (
                            fc.get("weatherCondition", {})
                            .get("description", {})
                            .get("text", "-")
                        )
                        precip = fc.get("precipitationProbability", {}).get(
                            "value", "0"
                        )

                        temp_str = (
                            f"{temp:.1f}°{unit}"
                            if isinstance(temp, (int, float))
                            else "-"
                        )
                        time_str = (
                            f"{label}\n[dim]{local_dt.strftime('%I:%M %p %Z')}[/dim]"
                        )

                        w_table.add_row(time_str, temp_str, cond, f"{precip}%")

            console.print(w_table)

        # Generate Google Maps URL
        if url:
            maps_link = generate_maps_url(origin, destination, mode)
            console.print(
                f"\n[bold cyan]Google Maps URL:[/] [link={maps_link}]{maps_link}[/link]"
            )

        # Step-by-step directions
        if directions:
            console.print("\n[bold cyan]Step-by-Step Directions:[s/]")
            legs = primary_route.get("legs", [])
            for leg in legs:
                steps = leg.get("steps", [])
                for i, step in enumerate(steps, 1):
                    instr = step.get("navigationInstruction", {}).get(
                        "instructions", "Proceed"
                    )
                    step_dist = format_duration(step.get("duration", "0s"))
                    console.print(f"{i}. {instr} [dim]({step_dist})[/dim]")

    except Exception as e:
        console.print(f"[bold red]Error computing route:[/] {e}")
        if "--debug" in sys.argv:
            console.print_exception()
        sys.exit(1)


@cli.command()
@click.argument("name")
@click.option(
    "-m",
    "--mode",
    type=click.Choice(["drive", "bicycle", "two_wheeler", "transit", "walk"]),
    required=True,
    help="Travel mode",
)
@click.option(
    "-e",
    "--engine",
    type=click.Choice(["gasoline", "electric", "hybrid", "diesel"]),
    default=None,
    help="Engine type (for drive mode)",
)
@click.option(
    "-t",
    "--avoid-tolls",
    is_flag=True,
    default=False,
    help="Avoid tolls",
)
@click.option(
    "-H",
    "--avoid-highways",
    is_flag=True,
    default=False,
    help="Avoid highways",
)
@click.option(
    "--mpg",
    type=float,
    default=None,
    help="Standard fuel economy MPG",
)
@click.option(
    "--mpg-econ",
    type=float,
    default=None,
    help="Econ mode fuel economy MPG",
)
def garage_add(name, mode, engine, avoid_tolls, avoid_highways, mpg, mpg_econ):
    """Add a vehicle to your garage."""
    if settings is None:
        console.print("[bold red]Error:[/] Settings not initialized.")
        sys.exit(1)

    garage = settings.load_garage()
    garage[name] = VehicleConfig(
        mode=mode,
        engine=engine,
        avoid_tolls=avoid_tolls,
        avoid_highways=avoid_highways,
        mpg=mpg,
        mpg_econ=mpg_econ,
    )
    settings.save_garage(garage)
    console.print(f"[bold green]Added {name} to garage![/]")


@cli.command()
def garage_list():
    """List all vehicles in your garage."""
    if settings is None:
        console.print("[bold red]Error:[/] Settings not initialized.")
        sys.exit(1)

    garage = settings.load_garage()
    if not garage:
        console.print("[dim]Garage is empty.[/dim]")
        return

    table = Table(title="Garage", header_style="bold magenta")
    table.add_column("Name")
    table.add_column("Mode")
    table.add_column("Engine")
    table.add_column("MPG (Norm/Econ)")
    table.add_column("Avoids")

    for name, cfg in garage.items():
        avoids = []
        if cfg.avoid_tolls:
            avoids.append("Tolls")
        if cfg.avoid_highways:
            avoids.append("Highways")
        if cfg.avoid_ferries:
            avoids.append("Ferries")

        mpg_str = "-"
        if cfg.mpg and cfg.mpg_econ:
            mpg_str = f"{cfg.mpg:.1f} / {cfg.mpg_econ:.1f}"
        elif cfg.mpg:
            mpg_str = f"{cfg.mpg:.1f}"

        table.add_row(
            name,
            cfg.mode,
            cfg.engine or "-",
            mpg_str,
            ", ".join(avoids) if avoids else "-",
        )

    console.print(table)


@cli.command()
@click.argument("name")
def garage_remove(name):
    """Remove a vehicle from your garage."""
    if settings is None:
        console.print("[bold red]Error:[/] Settings not initialized.")
        sys.exit(1)

    garage = settings.load_garage()
    if name in garage:
        del garage[name]
        settings.save_garage(garage)
        console.print(f"[bold green]Removed {name} from garage.[/]")
    else:
        console.print(f"[yellow]Vehicle '{name}' not found in garage.[/]")


@click.group(name="garage")
def garage_group():
    """Manage your fleet of vehicles."""
    pass


garage_group.add_command(garage_add, name="add")
garage_group.add_command(garage_list, name="list")
garage_group.add_command(garage_remove, name="remove")
cli.add_command(garage_group)


@cli.command()
@click.argument("name")
@click.argument("address")
def places_add(name, address):
    """Add a saved place."""
    if settings is None:
        console.print("[bold red]Error:[/] Settings not initialized.")
        sys.exit(1)

    places = settings.load_places()
    places[name.lower()] = address
    settings.save_places(places)
    console.print(f"[bold green]Saved place '{name}' -> '{address}'![/]")


@cli.command()
def places_list():
    """List all saved places."""
    if settings is None:
        console.print("[bold red]Error:[/] Settings not initialized.")
        sys.exit(1)

    places = settings.load_places()
    if not places:
        console.print("[dim]No saved places.[/dim]")
        return

    table = Table(title="Saved Places", header_style="bold magenta")
    table.add_column("Name")
    table.add_column("Address")

    for name, addr in places.items():
        table.add_row(name, addr)

    console.print(table)


@click.group(name="places")
def places_group():
    """Manage saved addresses (home, work, etc.)."""
    pass


places_group.add_command(places_add, name="add")
places_group.add_command(places_list, name="list")
cli.add_command(places_group)


@cli.command()
@click.option("--start", prompt="Starting location", help="Starting address or town")
@click.option("--end", prompt="Ending location", help="Ending address or town")
@click.option(
    "--miles",
    type=float,
    prompt="Shift mileage",
    help="Total miles driven during shift",
)
@click.option(
    "--earnings",
    type=float,
    prompt="Gross shift earnings ($)",
    help="Gross cash earnings in dollars",
)
@click.option(
    "--gas-price",
    type=float,
    default=3.99,
    help="Gas price per gallon (default: $3.99)",
)
@click.option(
    "--mpg", type=float, default=40.6, help="Vehicle fuel economy MPG (default: 40.6)"
)
def doordash(start, end, miles, earnings, gas_price, mpg):
    """
    \b
    Calculate DoorDash shift mileage tax shelter and net profit metrics.

    \b
    Examples:
      roam doordash --start "Corning NY" --end "Tioga PA" --miles 78.9 --earnings 22.30
    """
    irs_rate = 0.67  # 2026 IRS Standard Mileage Rate
    gallons_used = miles / mpg
    actual_gas_cost = gallons_used * gas_price
    net_cash_profit = earnings - actual_gas_cost
    irs_tax_deduction = miles * irs_rate
    net_tax_shelter_gain = irs_tax_deduction - net_cash_profit

    table = Table(
        title="DoorDash Shift IRS Tax Shelter & FinOps Ledger",
        header_style="bold green",
    )
    table.add_column("Metric", style="cyan")
    table.add_column("Value", justify="right", style="bold")

    table.add_row("Shift Transit Route", f"{start} ➔ {end}")
    table.add_row("Shift Mileage", f"{miles:.1f} Miles")
    table.add_row("Gross Cash Earnings", f"${earnings:.2f}")
    table.add_row(
        "Actual Gas Spent",
        f"-${actual_gas_cost:.2f} ({gallons_used:.2f} gal @ ${gas_price:.2f}/gal)",
    )
    table.add_row("Net Cash Profit", f"${net_cash_profit:.2f}")
    table.add_row("IRS Standard Tax Deduction ($0.67/mi)", f"+${irs_tax_deduction:.2f}")
    table.add_row(
        "NET TAX SHELTER GAIN", f"+${net_tax_shelter_gain:.2f}", style="bold green"
    )

    console.print(Panel(table, border_style="green"))


def main():
    cli()


if __name__ == "__main__":
    main()
