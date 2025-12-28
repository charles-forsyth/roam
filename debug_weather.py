from roam.config import settings
from roam.core import RouteRequester
import json

if not settings:
    print("No settings found")
    exit(1)

requester = RouteRequester(api_key=settings.google_maps_api_key)

# Los Angeles coordinates
lat, lng = 34.0522, -118.2437

print(f"Fetching daily forecast for {lat}, {lng}...")
daily = requester.get_daily_forecast(lat, lng)

print(json.dumps(daily, indent=2))
