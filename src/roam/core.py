import requests
from typing import Optional, Dict, Any, List
from rich.console import Console

console = Console()

class RouteRequester:
    """
    Handles interactions with the Google Maps Routes, Places, and Weather APIs.
    """
    ROUTES_BASE_URL = "https://routes.googleapis.com/directions/v2:computeRoutes"
    PLACES_BASE_URL = "https://places.googleapis.com/v1/places:searchText"
    WEATHER_BASE_URL = "https://weather.googleapis.com/v1/currentConditions:lookup"
    FORECAST_BASE_URL = "https://weather.googleapis.com/v1/forecast/hours:lookup"

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
            "X-Goog-FieldMask": "routes.duration,routes.distanceMeters,routes.polyline.encodedPolyline,routes.legs.steps.navigationInstruction,routes.legs.steps.distanceMeters,routes.legs.steps.staticDuration,routes.legs.startLocation,routes.legs.endLocation,routes.legs.steps.startLocation,routes.legs.steps.endLocation"
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
        Handles pagination to retrieve up to 60 results (approx).
        """
        all_places = []
        next_page_token = None
        
        # We request name, formatting address, and location
        headers = {
            "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.location,nextPageToken"
        }

        # Max 3 pages (default 20 per page = 60 results) to avoid excessive API usage
        for _ in range(3):
            payload = {
                "textQuery": query,
                "searchAlongRouteParameters": {
                    "polyline": {
                        "encodedPolyline": polyline
                    }
                }
            }
            
            if next_page_token:
                payload["pageToken"] = next_page_token

            try:
                response = self.session.post(self.PLACES_BASE_URL, json=payload, headers=headers, timeout=10)
                response.raise_for_status()
                data = response.json()
                
                places = data.get("places", [])
                if places:
                    all_places.extend(places)
                
                next_page_token = data.get("nextPageToken")
                if not next_page_token:
                    break
                    
            except requests.exceptions.RequestException as e:
                console.print(f"[bold red]Error searching along route for '{query}':[/bold red] {e}")
                if hasattr(e, 'response') and e.response is not None:
                    console.print(f"[red]Details:[/red] {e.response.text}")
                break
                
        return all_places

    def get_weather(self, lat: float, lng: float) -> Dict[str, Any]:
        """
        Fetches current weather conditions for a specific location.
        """
        # The Weather API uses GET requests with query parameters
        params = {
            "location.latitude": lat,
            "location.longitude": lng,
            "key": self.api_key 
        }
        
        # Removing Content-Type for GET
        headers = self.session.headers.copy()
        if "Content-Type" in headers:
            del headers["Content-Type"]
        
        try:
            response = requests.get(self.WEATHER_BASE_URL, params=params, timeout=5)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            console.print(f"[red]Weather API Error:[/red] {e}")
            return {}

    def get_hourly_forecast(self, lat: float, lng: float) -> Dict[str, Any]:
        """
        Fetches hourly weather forecast for a specific location.
        """
        params = {
            "location.latitude": lat,
            "location.longitude": lng,
            "key": self.api_key 
        }
        
        try:
            response = requests.get(self.FORECAST_BASE_URL, params=params, timeout=5)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            console.print(f"[red]Forecast API Error:[/red] {e}")
            return {}
