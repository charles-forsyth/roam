from click.testing import CliRunner
from roam.cli import cli, format_duration

def test_cli_help():
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "Roam: The Personal Routing Commander" in result.output
    
    result_route = runner.invoke(cli, ["route", "--help"])
    assert result_route.exit_code == 0
    assert "turn-by-turn directions" in result_route.output

def test_format_duration():
    assert format_duration("3600s") == "1h 0m"
    assert format_duration("60s") == "1m"
    assert format_duration("invalid") == "invalid"
