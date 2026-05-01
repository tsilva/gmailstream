from click.testing import CliRunner

from gmailstream.cli import main


def test_cli_help_imports():
    result = CliRunner().invoke(main, ["--help"])

    assert result.exit_code == 0
    assert "Download Gmail messages matching configurable filters." in result.output
