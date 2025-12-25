from roam.core import RouteRequester
from roam.cli import find_forecast_for_time
from datetime import datetime, timezone

def test_search_along_route_mock(mocker):
    # Mock requests.Session.post
    mock_post = mocker.patch("requests.Session.post")
    
    # Setup mock response for search
    mock_response = mocker.Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "places": [
            {
                "displayName": {"text": "Joe's Coffee"},
                "formattedAddress": "123 Route 66",
                "location": {"latitude": 10, "longitude": 20}
            }
        ]
    }
    mock_post.return_value = mock_response

    requester = RouteRequester(api_key="fake_key")
    results = requester.search_along_route("coffee", "dummy_polyline")

    assert len(results) == 1
    assert results[0]["displayName"]["text"] == "Joe's Coffee"
    
    # Verify payload structure
    args, kwargs = mock_post.call_args
    assert kwargs["json"]["textQuery"] == "coffee"
    assert kwargs["json"]["searchAlongRouteParameters"]["polyline"]["encodedPolyline"] == "dummy_polyline"

def test_get_weather_mock(mocker):
    # Mock requests.get (used for Weather)
    mock_get = mocker.patch("requests.get")
    
    mock_response = mocker.Mock()
    mock_response.status_code = 200
    # Mock the REAL structure from Weather API
    mock_response.json.return_value = {
        "temperature": {"degrees": 20},
        "weatherCondition": {
            "description": {"text": "Sunny"}
        },
        "relativeHumidity": 50
    }
    mock_get.return_value = mock_response
    
    requester = RouteRequester(api_key="fake_key")
    weather = requester.get_weather(37.77, -122.41)
    
    assert weather["weatherCondition"]["description"]["text"] == "Sunny"
    assert weather["temperature"]["degrees"] == 20
    
    # Verify params
    args, kwargs = mock_get.call_args
    assert kwargs["params"]["location.latitude"] == 37.77
    assert kwargs["params"]["location.longitude"] == -122.41

def test_get_hourly_forecast_mock(mocker):
    mock_get = mocker.patch("requests.get")
    mock_response = mocker.Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"hourlyForecasts": []}
    mock_get.return_value = mock_response
    
    requester = RouteRequester(api_key="fake_key")
    requester.get_hourly_forecast(10, 20)
    
    args, kwargs = mock_get.call_args
    assert kwargs["params"]["location.latitude"] == 10
    assert kwargs["params"]["location.longitude"] == 20

def test_find_forecast_for_time():
    data = {
        "forecastHours": [
            {"interval": {"startTime": "2025-12-25T10:00:00Z"}, "temp": 10},
            {"interval": {"startTime": "2025-12-25T11:00:00Z"}, "temp": 11},
            {"interval": {"startTime": "2025-12-25T12:00:00Z"}, "temp": 12},
        ]
    }
    
    # Exact match
    target = datetime(2025, 12, 25, 11, 0, 0, tzinfo=timezone.utc)
    match = find_forecast_for_time(data, target)
    assert match["temp"] == 11
    
    # Closest match (11:20 -> 11:00)
    target = datetime(2025, 12, 25, 11, 20, 0, tzinfo=timezone.utc)
    match = find_forecast_for_time(data, target)
    assert match["temp"] == 11
    
    # Closest match (11:40 -> 12:00)
    target = datetime(2025, 12, 25, 11, 40, 0, tzinfo=timezone.utc)
    match = find_forecast_for_time(data, target)
    assert match["temp"] == 12
