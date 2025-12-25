import click
from rich.console import Console
from rich.panel import Panel
from roam.config import settings, Settings
from roam.core import RouteRequester
import sys

console = Console()

@click.group(invoke_without_command=True)
@click.argument("destination", required=False)
@click.option("--origin", "-f", help="Starting point (default: current location/config)", default="New York, NY") # Placeholder default
@click.option("--mode", "-m", type=click.Choice(["drive", "bicycle", "two_wheeler", "transit", "walk"]), default="drive", help="Travel mode")
@click.option("--engine", "-e", type=click.Choice(["gasoline", "electric", "hybrid", "diesel"]), help="Engine type (for drive mode)")
@click.option("--avoid-tolls", is_flag=True, help="Avoid tolls")
@click.option("--avoid-highways", is_flag=True, help="Avoid highways")
@click.option("--with", "vehicle_alias", help="Use a preset vehicle configuration")
@click.pass_context
def cli(ctx, destination, origin, mode, engine, avoid_tolls, avoid_highways, vehicle_alias):
    """
    Roam: The Personal Routing Commander.
    
    Example: roam "San Francisco" --mode drive --avoid tolls
    """
    if ctx.invoked_subcommand is not None:
        return

    if not destination:
        click.echo(ctx.get_help())
        return

    # TODO: Load vehicle alias from config if specified
    if vehicle_alias:
        console.print(f"[yellow]Loading settings for vehicle: {vehicle_alias} (Not implemented yet)[/yellow]")

    # Validate Config
    if not settings:
        console.print("[bold red]Configuration Error:[/bold red] Could not load settings. Check environment variables.")
        sys.exit(1)

    requester = RouteRequester(api_key=settings.google_maps_api_key)
    
    console.print(Panel(f"Routing to [bold cyan]{destination}[/bold cyan] via [bold green]{mode}[/bold green]...", title="Roam"))

    result = requester.compute_route(
        origin=origin,
        destination=destination,
        mode=mode,
        engine_type=engine,
        avoid_tolls=avoid_tolls,
        avoid_highways=avoid_highways
    )

    if result:
        # Basic output parsing
        routes = result.get("routes", [])
        if routes:
            route = routes[0]
            duration = route.get("duration", "N/A")
            distance = route.get("distanceMeters", 0)
            
            # Convert distance to miles
            miles = int(distance) * 0.000621371
            
            console.print(f"[bold]Distance:[/bold] {miles:.2f} miles")
            console.print(f"[bold]Duration:[/bold] {duration}")
            console.print("[dim]Polyline available (rendering TBD)[/dim]")
        else:
            console.print("[yellow]No routes found.[/yellow]")

@cli.command()
def garage():
    """Manage your fleet of vehicles."""
    console.print("[bold]Garage management coming soon...[/bold]")

def main():
    cli()

if __name__ == "__main__":
    main()
