import os
import stat

import pytest

from gmailstream.auth import copy_private_file, ensure_private_dir, write_private_text

pytestmark = pytest.mark.skipif(os.name == "nt", reason="POSIX permission checks")


def _mode(path):
    return stat.S_IMODE(path.stat().st_mode)


def test_ensure_private_dir_uses_user_only_permissions(tmp_path):
    profile_dir = tmp_path / "profile"

    ensure_private_dir(profile_dir)

    assert _mode(profile_dir) == 0o700


def test_write_private_text_uses_user_only_permissions(tmp_path):
    token_path = tmp_path / "token.json"

    write_private_text(token_path, "{}")

    assert token_path.read_text() == "{}"
    assert _mode(token_path) == 0o600


def test_copy_private_file_does_not_preserve_permissive_source_mode(tmp_path):
    src = tmp_path / "source-credentials.json"
    dest = tmp_path / "credentials.json"
    src.write_text("{}")
    src.chmod(0o644)

    copy_private_file(src, dest)

    assert dest.read_text() == "{}"
    assert _mode(dest) == 0o600
