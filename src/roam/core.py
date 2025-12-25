import requests
from typing import Optional, Dict, Any
from rich.console import Console

console = Console()

class RouteRequester:
    """
    Handles interactions with the Google Maps Routes API v2.
    """
    BASE_URL = "https://routes.googleapis.com/directions/v2:computeRoutes"

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": "routes.duration,routes.distanceMeters,routes.polyline.encodedPolyline,routes.legs.steps.navigationInstruction,routes.legs.steps.distanceMeters,routes.legs.steps.staticDuration"
        })

    def compute_route(
        self, 
        origin: str, 
        destination: str, 
        mode: str = "DRIVE", 
        engine_type: Optional[str] = None,
        avoid_tolls: bool = False,
        avoid_highways: bool = False,
        avoid_ferries: bool = False
    ) -> Dict[str, Any]:
        """
        Computes a route using the Routes API.
        """
        payload = {
            "origin": {"address": origin},
            "destination": {"address": destination},
            "travelMode": mode.upper(),
            "routingPreference": "TRAFFIC_AWARE",
            "computeAlternativeRoutes": False,
            "routeModifiers": {
                "avoidTolls": avoid_tolls,
                "avoidHighways": avoid_highways,
                "avoidFerries": avoid_ferries
            },
            "languageCode": "en-US",
            "units": "IMPERIAL"
        }

        # Engine type is only valid for DRIVE
        if mode.upper() == "DRIVE" and engine_type:
            # Note: Engine type structure in v2 can be complex, simplifying for initial core
            # It usually goes under routeModifiers -> vehicleInfo -> emissionType
            payload["routeModifiers"]["vehicleInfo"] = {
                "emissionType": engine_type.upper()
            }

        try:
            response = self.session.post(self.BASE_URL, json=payload, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            console.print(f"[bold red]Error connecting to Google Maps API:[/bold red] {e}")
            if hasattr(e, 'response') and e.response is not None:
                console.print(f"[red]Details:[/red] {e.response.text}")
            return {}
