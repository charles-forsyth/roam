from click.testing import CliRunner
from roam.cli import cli
from roam.config import VehicleConfig


def test_garage_add_and_list(mocker):
    # Mock settings.save_garage and settings.load_garage to avoid filesystem I/O
    mock_save = mocker.patch("roam.config.Settings.save_garage")
    mock_load = mocker.patch("roam.config.Settings.load_garage")

    mock_load.return_value = {}  # Start empty

    runner = CliRunner()

    # 1. Test Add
    result = runner.invoke(
        cli, ["garage", "add", "my-tesla", "--mode", "drive", "--engine", "electric"]
    )
    assert result.exit_code == 0
    assert "Added my-tesla to garage" in result.output

    # Verify save was called with correct config
    args, _ = mock_save.call_args
    assert "my-tesla" in args[0]
    assert args[0]["my-tesla"].engine == "electric"

    # 2. Test List (mocking the data returning)
    mock_load.return_value = {
        "my-tesla": VehicleConfig(mode="drive", engine="electric")
    }
    result_list = runner.invoke(cli, ["garage", "list"])
    assert result_list.exit_code == 0
    assert "my-tesla" in result_list.output
    assert "electric" in result_list.output
