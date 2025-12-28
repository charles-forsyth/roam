from roam.cli import cli
from click.testing import CliRunner


def test_daily_forecast_condition_extraction(mocker):
    # Mock data based on REAL API response
    mock_daily_data = {
        "forecastDays": [
            {
                "interval": {"startTime": "2025-12-29T15:00:00Z"},
                "daytimeForecast": {
                    "weatherCondition": {"description": {"text": "Sunny"}},
                    "precipitation": {"probability": {"percent": 10}},
                },
                "maxTemperature": {"degrees": 25},
            }
        ]
    }

    # We can't easily test the CLI output formatting logic in isolation without mocking RouteRequester
    # and running the full command, or refactoring the CLI function.
    # Let's do a full CLI invocation mock like before.

    mock_requester_cls = mocker.patch("roam.cli.RouteRequester")
    mock_requester_instance = mock_requester_cls.return_value

    mock_requester_instance.compute_route.return_value = {
        "routes": [
            {
                "legs": [
                    {
                        "steps": [],
                        "startLocation": {"latLng": {"latitude": 10, "longitude": 20}},
                        "endLocation": {"latLng": {"latitude": 10, "longitude": 20}},
                    }
                ],
                "distanceMeters": 1000,
                "duration": "60s",
                "polyline": {"encodedPolyline": "abcd"},
            }
        ]
    }

    mock_requester_instance.get_daily_forecast.return_value = mock_daily_data

    mocker.patch("roam.cli.settings")
    mock_settings = mocker.Mock()
    mock_settings.load_places.return_value = {}
    mock_settings.load_garage.return_value = {}
    mock_settings.google_maps_api_key = "fake_key"
    mocker.patch("roam.cli.settings", mock_settings)

    runner = CliRunner()

    # Target the date in our mock data
    # Note: The CLI uses the timezone of the origin point.
    # We need to make sure 2025-12-29 matches the date logic.
    # The logic finds the daily forecast entry where startTime matches target date.

    result = runner.invoke(cli, ["route", "Nowhere", "-W", "-D", "2025-12-29"])

    assert result.exit_code == 0
    # Check that "Sunny" appears in the output
    assert "Sunny" in result.output
    # Check that "10%" appears
    assert "10%" in result.output
