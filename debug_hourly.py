from roam.config import settings
from roam.core import RouteRequester
import json

if not settings:
    print("No settings found")
    exit(1)

requester = RouteRequester(api_key=settings.google_maps_api_key)

# Los Angeles
lat, lng = 34.0522, -118.2437

print(f"Fetching hourly forecast for {lat}, {lng}...")
hourly = requester.get_hourly_forecast(lat, lng)

# Print first item
if hourly.get("forecastHours"):
    print(json.dumps(hourly["forecastHours"][0], indent=2))
else:
    print(json.dumps(hourly, indent=2))
