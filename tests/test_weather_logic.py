from roam.cli import cli
from click.testing import CliRunner
from datetime import datetime, timedelta, timezone


def test_weather_skip_hourly_distant_future(mocker):
    # Patch RouteRequester in cli.py
    mock_requester_cls = mocker.patch("roam.cli.RouteRequester")
    mock_requester_instance = mock_requester_cls.return_value

    # Mock compute_route to return a simple route
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

    # Mock daily forecast to return something so it doesn't crash/print error
    mock_requester_instance.get_daily_forecast.return_value = {
        "forecastDays": [
            {
                "interval": {
                    "startTime": (
                        datetime.now(timezone.utc) + timedelta(days=3)
                    ).strftime("%Y-%m-%dT00:00:00Z")
                },
                "maxTemperature": {"degrees": 25},
                "weatherCondition": {"description": {"text": "Sunny"}},
            }
        ]
    }

    # Mock settings to avoid loading actual config
    mocker.patch("roam.cli.settings")
    mock_settings = mocker.Mock()
    mock_settings.load_places.return_value = {}
    mock_settings.load_garage.return_value = {}
    mock_settings.google_maps_api_key = "fake_key"
    mocker.patch("roam.cli.settings", mock_settings)

    runner = CliRunner()

    # Run with a date > 24h away.
    # We use 3 days to be safe > 24h
    future_date = (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d")

    result = runner.invoke(cli, ["route", "Nowhere", "-W", "-D", future_date])

    # It might fail if I missed mocking something else, so let's check output if exit_code != 0
    if result.exit_code != 0:
        print(result.output)

    assert result.exit_code == 0

    # Verify get_hourly_forecast was NOT called because it's > 24h away
    mock_requester_instance.get_hourly_forecast.assert_not_called()

    # Verify get_daily_forecast WAS called
    mock_requester_instance.get_daily_forecast.assert_called()
