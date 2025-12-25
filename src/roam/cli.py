import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from roam.config import settings, VehicleConfig
from roam.core import RouteRequester
import sys

console = Console()


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


@click.group(cls=DefaultGroup, default_command="route")
def cli():
    """
    Roam: The Personal Routing Commander.
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


@cli.command()
@click.argument("destination")
@click.option(
    "--origin",
    "-f",
    help="Starting point (default: 'home' preset or New York)",
    default="home",
)
@click.option(
    "--mode",
    "-m",
    type=click.Choice(["drive", "bicycle", "two_wheeler", "transit", "walk"]),
    help="Travel mode",
)
@click.option(
    "--engine",
    "-e",
    type=click.Choice(["gasoline", "electric", "hybrid", "diesel"]),
    help="Engine type (for drive mode)",
)
@click.option("--avoid-tolls", is_flag=True, help="Avoid tolls")
@click.option("--avoid-highways", is_flag=True, help="Avoid highways")
@click.option("--with", "vehicle_alias", help="Use a preset vehicle configuration")
@click.option("--directions", "-d", is_flag=True, help="Show turn-by-turn directions")
def route(
    destination,
    origin,
    mode,
    engine,
    avoid_tolls,
    avoid_highways,
    vehicle_alias,
    directions,
):
    """
    Calculate a route to DESTINATION.

    DESTINATION and ORIGIN can be saved places (e.g. 'home', 'work') or raw addresses.
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
        # Fallback if user hasn't set 'home' yet
        console.print(
            "[yellow]No 'home' preset found. Using default (New York, NY).[/yellow]"
        )
        console.print(
            "[dim]Tip: Set your home address with: `roam places add home 'Your Address'`[/dim]"
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

    # 1. Load from Garage if specified
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

    # Build status string
    status_parts = [f"via [bold green]{final_mode}[/bold green]"]
    if final_engine:
        status_parts.append(f"([cyan]{final_engine}[/cyan])")
    if final_avoid_tolls:
        status_parts.append("[red]no tolls[/red]")
    if final_avoid_highways:
        status_parts.append("[red]no hwys[/red]")

    console.print(
        Panel(
            f"Routing from [bold]{origin}[/bold] to [bold cyan]{destination}[/bold cyan] {' '.join(status_parts)}...",
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
            route = routes[0]
            duration = route.get("duration", "N/A")
            distance = route.get("distanceMeters", 0)
            miles = int(distance) * 0.000621371

            # Format time
            fmt_duration = format_duration(duration)

            console.print(f"[bold]Distance:[/bold] {miles:.2f} miles")
            console.print(f"[bold]Duration:[/bold] {fmt_duration}")

            if directions:
                console.print("\n[bold]Directions:[/bold]")
                legs = route.get("legs", [])
                step_count = 1
                for leg in legs:
                    for step in leg.get("steps", []):
                        # Some steps might not have maneuver but have generic instructions if we parsed HTML (legacy)
                        # Routes API v2 returns mostly maneuvers or nothing for simple steps.
                        # Actually, Routes API v2 field 'navigationInstruction' is sparse.
                        # Let's check for 'instructions' or 'maneuver'.

                        # API v2 often puts the text in `navigationInstruction`.`instructions`?
                        # No, the field mask requested `navigationInstruction`.
                        # Let's inspect what we get. The API returns `maneuver` (enum) and `instructions` (string).

                        # Note: The API documentation says `navigationInstruction` has `maneuver` and `instructions`.
                        # `instructions` is the user-readable text.

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
            else:
                console.print(
                    "\n[dim]Use --directions to see turn-by-turn steps.[/dim]"
                )

        else:
            console.print("[yellow]No routes found.[/yellow]")


# --- Garage Commands ---
@cli.group()
def garage():
    """Manage your fleet of vehicles."""
    pass


@garage.command(name="add")
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
@click.option("--avoid-tolls", is_flag=True, help="Avoid tolls")
@click.option("--avoid-highways", is_flag=True, help="Avoid highways")
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


@garage.command(name="list")
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


@garage.command(name="remove")
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
@cli.group()
def places():
    """Manage saved addresses (home, work, etc.)."""
    pass


@places.command(name="add")
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


@places.command(name="list")
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


@places.command(name="remove")
@click.argument("name")
def places_remove(name):
    """Remove a saved place."""
    if not settings:
        return

    places_data = settings.load_places()
    if name in places_data:
        del places_data[name]
        settings.save_garage(places_data)
        console.print(f"[green]Removed [bold]{name}[/bold] from places.[/green]")
    else:
        console.print(f"[red]Place '{name}' not found.[/red]")


def main():
    cli()
