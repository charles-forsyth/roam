import requests
from typing import Optional, Dict, Any, List
from rich.console import Console

console = Console()

class RouteRequester:
    """
    Handles interactions with the Google Maps Routes and Places APIs.
    """
    ROUTES_BASE_URL = "https://routes.googleapis.com/directions/v2:computeRoutes"
    PLACES_BASE_URL = "https://places.googleapis.com/v1/places:searchText"

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.session = requests.Session()
        # Headers are slightly different per API (FieldMasks), so we set common ones here
        self.session.headers.update({
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
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

        if mode.upper() == "DRIVE" and engine_type:
            payload["routeModifiers"]["vehicleInfo"] = {
                "emissionType": engine_type.upper()
            }

        headers = {
            "X-Goog-FieldMask": "routes.duration,routes.distanceMeters,routes.polyline.encodedPolyline,routes.legs.steps.navigationInstruction,routes.legs.steps.distanceMeters,routes.legs.steps.staticDuration"
        }

        try:
            response = self.session.post(self.ROUTES_BASE_URL, json=payload, headers=headers, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            console.print(f"[bold red]Error connecting to Routes API:[/bold red] {e}")
            if hasattr(e, 'response') and e.response is not None:
                console.print(f"[red]Details:[/red] {e.response.text}")
            return {}

    def search_along_route(self, query: str, polyline: str) -> List[Dict[str, Any]]:
        """
        Searches for places along the route polyline using Places API (New).
        """
        payload = {
            "textQuery": query,
            "searchAlongRouteParameters": {
                "polyline": {
                    "encodedPolyline": polyline
                }
            }
        }
        
        # We request name, formatting address, and location
        headers = {
            "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.location"
        }

        try:
            response = self.session.post(self.PLACES_BASE_URL, json=payload, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            return data.get("places", [])
        except requests.exceptions.RequestException as e:
            console.print(f"[bold red]Error searching along route for '{query}':[/bold red] {e}")
            if hasattr(e, 'response') and e.response is not None:
                console.print(f"[red]Details:[/red] {e.response.text}")
            return []