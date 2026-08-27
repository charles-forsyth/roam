from click.testing import CliRunner
from roam.cli import cli
from roam.config import VehicleConfig


def test_doordash_command():
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "doordash",
            "--start",
            "Corning NY",
            "--end",
            "Tioga PA",
            "--miles",
            "78.9",
            "--earnings",
            "22.30",
            "--gas-price",
            "3.99",
            "--mpg",
            "40.6",
        ],
    )
    assert result.exit_code == 0
    assert "DoorDash Shift IRS Tax Shelter" in result.output
    assert "78.9 Miles" in result.output
    assert "NET TAX SHELTER GAIN" in result.output


def test_compare_and_econ_options(mocker):
    mock_requester_cls = mocker.patch("roam.cli.RouteRequester")
    mock_requester_instance = mock_requester_cls.return_value

    mock_requester_instance.compute_route.return_value = {
        "routes": [
            {
                "legs": [],
                "distanceMeters": 16093,  # 10 miles
                "duration": "600s",
                "polyline": {"encodedPolyline": ""},
            }
        ]
    }

    mock_settings = mocker.Mock()
    mock_settings.load_places.return_value = {"home": "100 Main St"}
    mock_settings.load_garage.return_value = {
        "SCRV": VehicleConfig(
            mode="drive",
            engine="hybrid",
            avoid_tolls=True,
            avoid_highways=False,
            avoid_ferries=False,
            mpg=36.0,
            mpg_econ=44.0,
        )
    }
    mock_settings.google_maps_api_key = "fake_key"
    mocker.patch("roam.cli.settings", mock_settings)

    runner = CliRunner()
    result = runner.invoke(cli, ["route", "Nowhere", "--compare", "--econ"])
    assert result.exit_code == 0
    assert "Multi-Vehicle Fleet Comparison" in result.output
    assert "SCRV" in result.output
