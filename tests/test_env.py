import os

from gmailstream.env import load_app_env


def test_load_app_env_reads_config_env_file(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        """
        # comment
        GMAIL_STREAMER_PROFILE_DIR=/tmp/profiles
        QUOTED_VALUE="hello world"
        export EXPORTED_VALUE='set from file'
        INVALID_LINE
        """
    )
    monkeypatch.delenv("GMAIL_STREAMER_PROFILE_DIR", raising=False)
    monkeypatch.delenv("QUOTED_VALUE", raising=False)
    monkeypatch.delenv("EXPORTED_VALUE", raising=False)

    load_app_env(env_file)

    assert os.environ["GMAIL_STREAMER_PROFILE_DIR"] == "/tmp/profiles"
    assert os.environ["QUOTED_VALUE"] == "hello world"
    assert os.environ["EXPORTED_VALUE"] == "set from file"


def test_load_app_env_does_not_override_existing_environment(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("GMAIL_STREAMER_PROFILE_DIR=/tmp/from-file\n")
    monkeypatch.setenv("GMAIL_STREAMER_PROFILE_DIR", "/tmp/from-shell")

    load_app_env(env_file)

    assert os.environ["GMAIL_STREAMER_PROFILE_DIR"] == "/tmp/from-shell"
