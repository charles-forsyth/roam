from click.testing import CliRunner
from roam.cli import cli, format_duration, find_daily_forecast_for_date
from datetime import date


def test_cli_help():
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "Roam: The Personal Routing Commander" in result.output

    result_route = runner.invoke(cli, ["route", "--help"])
    assert result_route.exit_code == 0
    assert "step-by-step navigation instructions" in result_route.output


def test_format_duration():
    assert format_duration("3600s") == "1h 0m"
    assert format_duration("60s") == "1m"
    assert format_duration("invalid") == "invalid"


def test_find_daily_forecast_for_date():
    mock_data = {
        "forecastDays": [
            {
                "interval": {"startTime": "2026-01-01T00:00:00Z"},
                "maxTemperature": {"degrees": 20},
            },
            {
                "interval": {"startTime": "2026-01-02T00:00:00Z"},
                "maxTemperature": {"degrees": 25},
            },
        ]
    }

    target = date(2026, 1, 1)
    match = find_daily_forecast_for_date(mock_data, target)
    assert match is not None
    assert match["maxTemperature"]["degrees"] == 20

    target_missing = date(2026, 1, 3)
    match_missing = find_daily_forecast_for_date(mock_data, target_missing)
    assert match_missing is None
