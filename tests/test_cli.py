from click.testing import CliRunner

from gmailstream.cli import main
from gmailstream.paths import DEFAULT_PROFILES_DIR


def test_cli_help_imports():
    result = CliRunner().invoke(main, ["--help"])

    assert result.exit_code == 0
    assert "Download Gmail messages matching configurable filters." in result.output
    assert "--profile TEXT" in result.output


def test_default_profiles_dir_uses_xdg_config_home():
    assert DEFAULT_PROFILES_DIR.parts[-3:] == (".config", "gmailstream", "profiles")


def test_profile_option_runs_profile_from_root_command(tmp_path):
    result = CliRunner().invoke(
        main,
        ["--profile-dir", str(tmp_path), "--profile", "missing-profile"],
    )

    assert result.exit_code == 1
    assert f"Profile directory not found: {tmp_path / 'missing-profile'}" in result.output


def test_profile_option_rejects_impossible_dates(tmp_path):
    result = CliRunner().invoke(
        main,
        [
            "--profile-dir",
            str(tmp_path),
            "--profile",
            "missing-profile",
            "--from",
            "2024-99-99",
        ],
    )

    assert result.exit_code == 2
    assert "Invalid date '2024-99-99'. Expected format: YYYY-MM-DD" in result.output


def test_profile_option_rejects_malformed_dates(tmp_path):
    result = CliRunner().invoke(
        main,
        [
            "--profile-dir",
            str(tmp_path),
            "--profile",
            "missing-profile",
            "--from",
            "20240101",
        ],
    )

    assert result.exit_code == 2
    assert "Invalid date '20240101'. Expected format: YYYY-MM-DD" in result.output


def test_profiles_init_rejects_path_like_name(tmp_path):
    result = CliRunner().invoke(
        main,
        ["--profile-dir", str(tmp_path), "profiles", "init", "../escape"],
    )

    assert result.exit_code == 2
    assert "Invalid value for name" in result.output
    assert not (tmp_path.parent / "escape").exists()
