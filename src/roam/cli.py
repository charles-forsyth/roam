import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from roam.config import settings, VehicleConfig
from roam.core import RouteRequester
from roam.utils import decode_polyline, get_nearest_point_on_polyline, calculate_cumulative_distances, generate_ascii_chart
from datetime import datetime, timedelta, timezone
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
        try:
            return super().resolve_command(ctx, args)
        except click.UsageError:
            if self.default_command:
                # We need to return the default command name, the command object, and the full args
                return (
                    self.default_command,
                    self.get_command(ctx, self.default_command),
                    args,
                )
            else:
                raise


@click.group(
    cls=DefaultGroup,
    default_command="route",
    context_settings={"help_option_names": ["-h", "--help"]},
)
def cli():
    """
    
    Roam: The Personal Routing Commander.
    -----------------------------------
    Calculate routes, manage your vehicle fleet, and save favorite places.

    
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

def get_fuel_price(place):
    """Extracts Regular Unleaded price if available."""
    fuel_options = place.get("fuelOptions", {})
    prices = fuel_options.get("fuelPrices", [])
    
    for p in prices:
        if p.get("type") == "REGULAR_UNLEADED":
            price_obj = p.get("price", {})
            units = int(price_obj.get("units", 0))
            nanos = int(price_obj.get("nanos", 0))
            currency = price_obj.get("currencyCode", "USD")
            
            # Construct float
            val = units + (nanos / 1_000_000_000)
            
            symbol = "$" if currency == "USD" else currency + " "
            return f"{symbol}{val:.2f}"
            
    return None

def find_forecast_for_time(forecast_data, target_time):
    """
    Finds the hourly forecast entry closest to target_time.
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

    return closest

def generate_maps_url(origin, destination, mode):
    """Generates a Universal Google Maps URL."""
    base = "https://www.google.com/maps/dir/?api=1"
    
    # Map roam modes to Google Maps travelmode
    mode_map = {
        "drive": "driving",
        "bicycle": "bicycling",
        "two_wheeler": "driving", # Maps URL doesn't support 2-wheeler mode explicitly
        "transit": "transit",
        "walk": "walking"
    }
    
    params = {
        "origin": origin,
        "destination": destination,
        "travelmode": mode_map.get(mode, "driving")
    }
    
    return f"{base}&{urllib.parse.urlencode(params)}"


@cli.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.argument("destination")
@click.option(
    "--origin",
    "-f",
    "-o",
    help="Starting point (address or saved place). Defaults to 'home' if set.",
    default="home",
)
@click.option(
    "--mode",
    "-m",
    type=click.Choice(["drive", "bicycle", "two_wheeler", "transit", "walk"]),
    help="Travel mode (default: drive).\nExample: -m bicycle",
)
@click.option(
    "--engine",
    "-e",
    type=click.Choice(["gasoline", "electric", "hybrid", "diesel"]),
    help="Vehicle engine type for eco-routing (only for drive mode).\nExample: -e electric",
)
@click.option(
    "--avoid-tolls",
    "-t",
    is_flag=True,
    help="Avoid toll roads where possible.",
)
@click.option(
    "--avoid-highways",
    "-H",
    is_flag=True,
    help="Avoid highways (good for scooters/scenic routes).",
)
@click.option(
    "--with",
    "-w",
    "vehicle_alias",
    help="Load settings from a saved vehicle in your garage.\nExample: --with tesla",
)
@click.option(
    "--directions",
    "-d",
    is_flag=True,
    help="Display step-by-step navigation instructions.",
)
@click.option(
    "--find",
    "-F",
    multiple=True,
    help="Search for places along the route path. Can be used multiple times.\nExample: -F gas -F coffee",
)
@click.option(
    "--weather",
    "-W",
    is_flag=True,
    help="Fetch hourly weather forecast for points along the route.",
)
@click.option(
    "--elevation",
    "-E",
    is_flag=True,
    help="Display elevation profile chart for the route.",
)
@click.option(
    "--url",
    "-u",
    is_flag=True,
    help="Generate a Google Maps URL for this route.",
)
@click.option(
    "--html",
    is_flag=True,
    help="Export the route report to 'roam_report.html'.",
)
def route(
    destination,
    origin,
    mode,
    engine,
    avoid_tolls,
    avoid_highways,
    vehicle_alias,
    directions,
    find,
    weather,
    elevation,
    url,
    html,
):
    """
    Calculate a route to DESTINATION.

    DESTINATION can be a city ("Los Angeles"), an address ("123 Main St"),
    or a saved place name ("work").

    
    Examples:
      roam "New York"
      roam "Gym" --origin "Work"
      roam "Seattle" -W -F "Starbucks"
    """
    if not settings:
        console.print(
            "[bold red]Configuration Error:[/bold red] Could not load settings."
        )
        sys.exit(1)

    # Resolve Places
    places = settings.load_places()

    # Resolve Origin
    final_origin = origin
    if origin in places:
        final_origin = places[origin]
        console.print(f"[dim]Resolved origin '{origin}' to: {final_origin}[/dim]")
    elif origin == "home" and "home" not in places:
        console.print(
            "[yellow]No 'home' preset found. Using default (New York, NY).[/yellow]"
        )
        final_origin = "New York, NY"

    # Resolve Destination
    final_dest = destination
    if destination in places:
        final_dest = places[destination]
        console.print(
            f"[dim]Resolved destination '{destination}' to: {final_dest}[/dim]"
        )

    # Load defaults
    final_mode = "drive"
    final_engine = None
    final_avoid_tolls = False
    final_avoid_highways = False

    if vehicle_alias:
        garage = settings.load_garage()
        vehicle = garage.get(vehicle_alias)
        if vehicle:
            console.print(
                f"[green]Using garage preset: [bold]{vehicle_alias}[/bold][/green]"
            )
            final_mode = vehicle.mode
            final_engine = vehicle.engine
            final_avoid_tolls = vehicle.avoid_tolls
            final_avoid_highways = vehicle.avoid_highways
        else:
            console.print(
                f"[bold red]Vehicle '{vehicle_alias}' not found in garage![/bold red]"
            )
            sys.exit(1)

    # 2. Overrides from CLI flags (if provided)
    if mode:
        final_mode = mode
    if engine:
        final_engine = engine
    if avoid_tolls:
        final_avoid_tolls = True
    if avoid_highways:
        final_avoid_highways = True

    requester = RouteRequester(api_key=settings.google_maps_api_key)

    status_parts = [f"via [bold green]{final_mode}[/bold green]"]
    if final_engine:
        status_parts.append(f"([cyan]{final_engine}[/cyan])")
    if final_avoid_tolls:
        status_parts.append("[red]no tolls[/red]")
    if final_avoid_highways:
        status_parts.append("[red]no hwys[/red]")

    console.print(
        Panel(
            f"Routing from [bold]{origin}[/bold] to [bold cyan]{destination}[/bold cyan] {" ".join(status_parts)}...",
            title="Roam",
        )
    )

    result = requester.compute_route(
        origin=final_origin,
        destination=final_dest,
        mode=final_mode,
        engine_type=final_engine,
        avoid_tolls=final_avoid_tolls,
        avoid_highways=final_avoid_highways,
    )

    if result:
        routes = result.get("routes", [])
        if routes:
            route_obj = routes[0]
            duration = route_obj.get("duration", "N/A")
            distance = route_obj.get("distanceMeters", 0)
            encoded_polyline = route_obj.get("polyline", {}).get("encodedPolyline", "")
            miles = int(distance) * 0.000621371

            fmt_duration = format_duration(duration)

            console.print(f"[bold]Distance:[/bold] {miles:.2f} miles")
            console.print(f"[bold]Duration:[/bold] {fmt_duration}")

            # Get Start Location for Distance Sorting
            legs = route_obj.get("legs", [])
            start_lat = None
            start_lng = None
            if legs:
                start_loc = legs[0].get("startLocation", {}).get("latLng", {})
                start_lat = start_loc.get("latitude")
                start_lng = start_loc.get("longitude")

            # --- Elevation Profile ---
            if elevation and encoded_polyline:
                console.print("\n[bold]Elevation Profile:[/bold]")
                with console.status("[bold green]Fetching elevation data...[/bold green]"):
                    # Use 60 samples for the ASCII chart width (default width=60)
                    elevation_data = requester.get_elevation_along_path(encoded_polyline, samples=60)
                    if elevation_data:
                        # Extract elevation values (in meters) and convert to feet
                        elevations = [p.get("elevation", 0) * 3.28084 for p in elevation_data]
                        
                        min_elev = min(elevations)
                        max_elev = max(elevations)
                        gain = max_elev - min_elev # Simple range, not cumulative gain
                        
                        console.print(f"Max: {int(max_elev)} ft | Min: {int(min_elev)} ft | Range: {int(gain)} ft")
                        
                        chart = generate_ascii_chart(elevations, height=10)
                        console.print(chart)
                    else:
                        console.print("[yellow]Could not fetch elevation data.[/yellow]")

            # --- Smart Forecast Weather ---
            if weather:
                console.print("\n[bold]Route Forecast:[/bold]")
                
                # We want to sample points every ~1 hour (3600s)
                SAMPLE_INTERVAL = 3600

                current_elapsed = 0
                last_sample_time = -SAMPLE_INTERVAL  # Force sample at 0

                samples = []  # List of (time_offset, lat, lng, description)

                # Start Point
                if start_lat:
                    samples.append(
                        (
                            0,
                            start_lat,
                            start_lng,
                            "Start",
                        )
                    )

                # Walk the steps to find intermediate points
                for leg in legs:
                    for step in leg.get("steps", []):
                        step_dur = get_seconds(step.get("staticDuration", "0s"))

                        if current_elapsed > last_sample_time + SAMPLE_INTERVAL:
                            end_loc = step.get("endLocation", {}).get("latLng", {})
                            if end_loc:
                                samples.append(
                                    (
                                        current_elapsed,
                                        end_loc.get("latitude"),
                                        end_loc.get("longitude"),
                                        f"En Route (+{format_duration(str(current_elapsed)+'s')})",
                                    )
                                )
                                last_sample_time = current_elapsed

                        current_elapsed += step_dur

                # Destination Point
                total_dur = get_seconds(duration)
                end_loc = legs[-1].get("endLocation", {}).get("latLng", {})
                if end_loc:
                    # Only add if significant time passed since last sample
                    if total_dur > last_sample_time + (SAMPLE_INTERVAL / 2):
                        samples.append(
                            (
                                total_dur,
                                end_loc.get("latitude"),
                                end_loc.get("longitude"),
                                "Destination",
                            )
                        )

                # Fetch Forecasts
                weather_table = Table(box=None)
                weather_table.add_column("Location / Time", style="bold")
                weather_table.add_column("Forecast Temp", style="cyan")
                weather_table.add_column("Condition", style="yellow")
                weather_table.add_column("Precip %", style="blue")

                now = datetime.now(timezone.utc)

                with console.status(
                    "[bold green]Fetching forecast along route...[/bold green]"
                ):
                    for offset, lat, lng, desc in samples:
                        target_time = now + timedelta(seconds=offset)

                        # Fetch Hourly Forecast
                        forecast_data = requester.get_hourly_forecast(lat, lng)
                        match = find_forecast_for_time(forecast_data, target_time)

                        if match:
                            temp_c = match.get("temperature", {}).get("degrees")
                            temp_f = (
                                (temp_c * 9 / 5) + 32 if temp_c is not None else None
                            )
                            temp_str = f"{temp_f:.1f}°F" if temp_f else "N/A"

                            condition = (
                                match.get("weatherCondition", {})
                                .get("description", {})
                                .get("text", "Unknown")
                            )
                            precip = (
                                match.get("precipitation", {})
                                .get("probability", {})
                                .get("percent", 0)
                            )

                            # Format time label
                            local_time_str = target_time.strftime("%I:%M %p")
                            label = f"{desc}\n[dim]{local_time_str}[/dim]"

                            weather_table.add_row(
                                label, temp_str, condition, f"{precip}%"
                            )
                        else:
                            weather_table.add_row(desc, "No Data", "-", "-")

                console.print(weather_table)

            # --- Search Along Route ---
            if find and encoded_polyline:
                console.print("\n[bold]Highlights Along Route:[/bold]")
                
                # Decode polyline once for Detour calculation
                route_points = decode_polyline(encoded_polyline)
                
                # Pre-calculate distances for Trip Mile
                cumulative_distances = calculate_cumulative_distances(route_points)
                
                for query in find:
                    console.print(f"  [dim]Searching for '{query}'...[/dim]")
                    # We no longer pass origin/routingParams because we calculate trip mile manually
                    places_list = requester.search_along_route(query, encoded_polyline)

                    if places_list:
                        # ENRICHMENT
                        for place in places_list:
                            # 1. Detour Distance & 2. Trip Mile
                            loc = place.get("location", {})
                            lat = loc.get("latitude")
                            lng = loc.get("longitude")
                            
                            if lat and lng:
                                # Subsample points for finding nearest point speed
                                # NOTE: If we subsample, we must map index back to original index for cumulative_distances
                                
                                # Simple optimization: Check every 5th point
                                STEP = 5
                                sub_points = route_points[::STEP]
                                
                                detour_mi, sub_index = get_nearest_point_on_polyline(lat, lng, sub_points)
                                
                                # Map sub_index to real index
                                real_index = sub_index * STEP
                                if real_index >= len(cumulative_distances):
                                    real_index = len(cumulative_distances) - 1
                                
                                place["_detour_mi"] = detour_mi
                                place["_trip_mi"] = cumulative_distances[real_index]
                            else:
                                place["_detour_mi"] = float("inf")
                                place["_trip_mi"] = float("inf")

                        # SORT LOGIC (Sort by Trip Mile)
                        places_list.sort(key=lambda x: x["_trip_mi"])

                        table = Table(
                            title=f"{query.capitalize()} Stops (Trip Order)",
                            show_header=True,
                            header_style="bold magenta",
                        )
                        table.add_column("Trip Mile", style="dim")
                        table.add_column("Detour", style="red")
                        table.add_column("Name", style="cyan")
                        table.add_column("Rating", style="yellow")
                        table.add_column("Price", style="green")
                        table.add_column("Address", style="white")

                        # Show all results
                        for place in places_list:
                            name = place.get("displayName", {}).get("text", "Unknown")
                            addr = place.get("formattedAddress", "Unknown Address")
                            rating = place.get("rating", "N/A")
                            count = place.get("userRatingCount", 0)
                            price_level = place.get("priceLevel", "")
                            
                            fuel_price = get_fuel_price(place)
                            price_display = fuel_price if fuel_price else format_price_level(price_level)
                            
                            # Trip Mile
                            trip_mi = place.get("_trip_mi", float("inf"))
                            trip_str = f"{trip_mi:.1f} mi" if trip_mi != float("inf") else "-"
                            
                            # Detour
                            detour_mi = place.get("_detour_mi", float("inf"))
                            detour_str = f"+{detour_mi:.1f} mi" if detour_mi != float("inf") else "-"
                            
                            rating_str = f"{rating} ({count})" if rating != "N/A" else "-"
                            
                            table.add_row(trip_str, detour_str, name, rating_str, str(price_display), addr)

                        console.print(table)
                    else:
                        console.print(f"  [yellow]No '{query}' found along route.[/yellow]")

            if directions:
                console.print("\n[bold]Directions:[/bold]")
                legs = route_obj.get("legs", [])
                step_count = 1
                for leg in legs:
                    for step in leg.get("steps", []):
                        nav = step.get("navigationInstruction", {})
                        text = nav.get("instructions", "")
                        maneuver = nav.get("maneuver", "").replace("_", " ").title()

                        step_dist_meters = int(step.get("distanceMeters", 0))
                        step_miles = step_dist_meters * 0.000621371
                        step_dist_str = (
                            f"{step_miles:.1f} mi"
                            if step_miles >= 0.1
                            else f"{step_dist_meters * 3.28084:.0f} ft"
                        )

                        if not text:
                            text = maneuver  # Fallback

                        console.print(
                            f"{step_count}. [cyan]{text}[/cyan] ([dim]{step_dist_str}[/dim])"
                        )
                        step_count += 1
            elif not find and not weather:
                console.print(
                    "\n[dim]Use -d for steps, -F for places, -W for weather.[/dim]"
                )
            
            # --- Output & Sharing ---
            if url:
                maps_url = generate_maps_url(final_origin, final_dest, final_mode)
                console.print(f"\n[bold green]Open in Maps:[/bold green] {maps_url}")
            
            if html:
                from rich.terminal_theme import MONOKAI
                console.save_html("roam_report.html", theme=MONOKAI)
                console.print("\n[bold]Report saved to:[/bold] roam_report.html")

        else:
            console.print("[yellow]No routes found.[/yellow]")


# --- Garage Commands ---
@cli.group(context_settings={"help_option_names": ["-h", "--help"]})
def garage():
    """Manage your fleet of vehicles."""
    pass


@garage.command(name="add", context_settings={"help_option_names": ["-h", "--help"]})
@click.argument("name")
@click.option(
    "--mode",
    "-m",
    type=click.Choice(["drive", "bicycle", "two_wheeler", "transit", "walk"]),
    required=True,
    help="Travel mode",
)
@click.option(
    "--engine",
    "-e",
    type=click.Choice(["gasoline", "electric", "hybrid", "diesel"]),
    help="Engine type (for drive mode)",
)
@click.option("--avoid-tolls", "-t", is_flag=True, help="Avoid tolls")
@click.option("--avoid-highways", "-H", is_flag=True, help="Avoid highways")
def garage_add(name, mode, engine, avoid_tolls, avoid_highways):
    """Add a vehicle to your garage."""
    if not settings:
        return

    garage_data = settings.load_garage()
    garage_data[name] = VehicleConfig(
        mode=mode, engine=engine, avoid_tolls=avoid_tolls, avoid_highways=avoid_highways
    )
    settings.save_garage(garage_data)
    console.print(f"[green]Added [bold]{name}[/bold] to garage![/green]")


@garage.command(name="list", context_settings={"help_option_names": ["-h", "--help"]})
def garage_list():
    """List all vehicles in your garage."""
    if not settings:
        return

    garage_data = settings.load_garage()
    if not garage_data:
        console.print(
            "[yellow]Your garage is empty. Use `roam garage add` to populate it.[/yellow]"
        )
        return

    table = Table(title="Garage")
    table.add_column("Name", style="cyan", no_wrap=True)
    table.add_column("Mode", style="green")
    table.add_column("Engine", style="magenta")
    table.add_column("Avoids", style="red")

    for name, config in garage_data.items():
        avoids = []
        if config.avoid_tolls:
            avoids.append("Tolls")
        if config.avoid_highways:
            avoids.append("Highways")

        table.add_row(name, config.mode, config.engine or "-", ", ".join(avoids) or "-")
    console.print(table)


@garage.command(name="remove", context_settings={"help_option_names": ["-h", "--help"]})
@click.argument("name")
def garage_remove(name):
    """Remove a vehicle from your garage."""
    if not settings:
        return

    garage_data = settings.load_garage()
    if name in garage_data:
        del garage_data[name]
        settings.save_garage(garage_data)
        console.print(f"[green]Removed [bold]{name}[/bold] from garage.[/green]")
    else:
        console.print(f"[red]Vehicle '{name}' not found.[/red]")


# --- Places Commands ---
@cli.group(context_settings={"help_option_names": ["-h", "--help"]})
def places():
    """Manage saved addresses (home, work, etc.)."""
    pass


@places.command(name="add", context_settings={"help_option_names": ["-h", "--help"]})
@click.argument("name")
@click.argument("address")
def places_add(name, address):
    """Add a saved place."""
    if not settings:
        return

    places_data = settings.load_places()
    places_data[name] = address
    settings.save_places(places_data)
    console.print(f"[green]Added [bold]{name}[/bold]: {address}[/green]")


@places.command(name="list", context_settings={"help_option_names": ["-h", "--help"]})
def places_list():
    """List all saved places."""
    if not settings:
        return

    places_data = settings.load_places()
    if not places_data:
        console.print(
            "[yellow]No places saved. Use `roam places add` to add one.[/yellow]"
        )
        return

    table = Table(title="Saved Places")
    table.add_column("Name", style="cyan", no_wrap=True)
    table.add_column("Address", style="green")

    for name, address in places_data.items():
        table.add_row(name, address)
    console.print(table)


@places.command(name="remove", context_settings={"help_option_names": ["-h", "--help"]})
@click.argument("name")
def places_remove(name):
    """Remove a saved place."""
    if not settings:
        return

    places_data = settings.load_places()
    if name in places_data:
        del places_data[name]
        settings.save_places(places_data)
        console.print(f"[green]Removed [bold]{name}[/bold] from places.[/green]")
    else:
        console.print(f"[red]Place '{name}' not found.[/red]")


def main():
    cli()