from click.testing import CliRunner
from roam.cli import cli

def test_places_add_and_list(mocker):
    # Mock settings.save_places and settings.load_places
    mock_save = mocker.patch("roam.config.Settings.save_places")
    mock_load = mocker.patch("roam.config.Settings.load_places")
    
    mock_load.return_value = {} # Start empty

    runner = CliRunner()
    
    # 1. Test Add
    result = runner.invoke(cli, ["places", "add", "home", "123 Main St"])
    assert result.exit_code == 0
    assert "Added home" in result.output
    
    # Verify save was called
    args, _ = mock_save.call_args
    assert "home" in args[0]
    assert args[0]["home"] == "123 Main St"

    # 2. Test List
    mock_load.return_value = {"home": "123 Main St"}
    result_list = runner.invoke(cli, ["places", "list"])
    assert result_list.exit_code == 0
    assert "123 Main St" in result_list.output
