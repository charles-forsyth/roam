from click.testing import CliRunner
from roam.cli import cli


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
                "polyline": {"encodedPolyline": ""},
            }
        ]
    }

    mock_requester_instance.get_daily_forecast.return_value = mock_daily_data

    mocker.patch("roam.cli.settings")
    mock_settings = mocker.Mock()
    mock_settings.load_places.return_value = {"home": "100 Main St"}
    mock_settings.load_garage.return_value = {}
    mock_settings.google_maps_api_key = "fake_key"
    mocker.patch("roam.cli.settings", mock_settings)

    runner = CliRunner()
    result = runner.invoke(cli, ["route", "Nowhere", "-W", "-D", "2025-12-29"])

    assert result.exit_code == 0
