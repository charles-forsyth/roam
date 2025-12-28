from roam.cli import cli
from click.testing import CliRunner


def test_weather_qpf_display(mocker):
    # Mock Hourly Data with QPF
    mock_hourly_data = {
        "forecastHours": [
            {
                "interval": {"startTime": "2025-01-01T12:00:00Z"},
                "temperature": {"degrees": 20},
                "weatherCondition": {"description": {"text": "Rainy"}},
                "precipitation": {
                    "probability": {"percent": 80},
                    "qpf": {"quantity": 10.0},  # 10mm ~ 0.39 in
                },
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
                "polyline": {"encodedPolyline": "abcd"},
            }
        ]
    }

    mock_requester_instance.get_hourly_forecast.return_value = mock_hourly_data

    # Mock Daily Data with QPF (fall back if needed)
    mock_daily_data = {"forecastDays": []}
    mock_requester_instance.get_daily_forecast.return_value = mock_daily_data

    mocker.patch("roam.cli.settings")
    mock_settings = mocker.Mock()
    mock_settings.load_places.return_value = {}
    mock_settings.load_garage.return_value = {}
    mock_settings.google_maps_api_key = "fake_key"
    mocker.patch("roam.cli.settings", mock_settings)

    # Mock timezone to avoid dealing with 'Now' logic complexity
    mocker.patch("roam.cli.get_timezone_at_point", return_value="UTC")
    mocker.patch("roam.cli.parse_start_time")
    from datetime import datetime, timezone

    # Force start time to match our mock
    mocker.patch(
        "roam.cli.parse_start_time",
        return_value=datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
    )

    runner = CliRunner()
    result = runner.invoke(cli, ["route", "Nowhere", "-W"])

    assert result.exit_code == 0
    # 10mm / 25.4 = 0.3937... -> 0.39 in
    assert "0.39 in" in result.output
    assert "80%" in result.output
