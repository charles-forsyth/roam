from click.testing import CliRunner
from roam.cli import cli

def test_cli_help():
    runner = CliRunner()
    result = runner.invoke(cli)
    assert result.exit_code == 0
    assert "Roam: The Personal Routing Commander" in result.output
