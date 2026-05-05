import json
import os
import stat

import pytest

from gmailstream.storage import save_attachments, save_eml, save_metadata, scan_downloaded_metadata


def _mode(path):
    return stat.S_IMODE(path.stat().st_mode)


def test_save_attachments_rejects_path_traversal(tmp_path):
    with pytest.raises(ValueError, match="Unsafe attachment filename"):
        save_attachments(
            tmp_path,
            "abcdef123456",
            "2024-01-02",
            "Subject",
            [{"filename": "../escape.txt", "data": b"bad"}],
        )

    assert not (tmp_path / "escape.txt").exists()


def test_save_attachments_rejects_absolute_paths(tmp_path):
    with pytest.raises(ValueError, match="Unsafe attachment filename"):
        save_attachments(
            tmp_path,
            "abcdef123456",
            "2024-01-02",
            "Subject",
            [{"filename": "/tmp/escape.txt", "data": b"bad"}],
        )


def test_save_attachments_preserves_unique_collision_names(tmp_path):
    save_attachments(
        tmp_path,
        "abcdef123456",
        "2024-01-02",
        "Subject",
        [
            {"filename": "report.txt", "data": b"one"},
            {"filename": "report.txt", "data": b"two"},
        ],
    )

    message_dir = tmp_path / "2024-01" / "2024-01-02 - subject - abcdef12"
    assert (message_dir / "report.txt").read_bytes() == b"one"
    assert (message_dir / "report (1).txt").read_bytes() == b"two"


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="symlink support required")
def test_save_attachments_treats_symlinks_as_existing_names(tmp_path):
    message_dir = tmp_path / "2024-01" / "2024-01-02 - subject - abcdef12"
    message_dir.mkdir(parents=True)
    os.symlink(tmp_path / "missing-target", message_dir / "report.txt")

    save_attachments(
        tmp_path,
        "abcdef123456",
        "2024-01-02",
        "Subject",
        [{"filename": "report.txt", "data": b"attachment"}],
    )

    assert (message_dir / "report.txt").is_symlink()
    assert (message_dir / "report (1).txt").read_bytes() == b"attachment"


@pytest.mark.skipif(os.name == "nt", reason="POSIX permission checks")
def test_saved_message_files_use_private_permissions(tmp_path):
    save_eml(tmp_path, "abcdef123456", "2024-01-02", "Subject", b"raw")
    save_metadata(
        tmp_path,
        "abcdef123456",
        "2024-01-02",
        "Subject",
        {"id": "abcdef123456", "date": "2024-01-02"},
    )
    save_attachments(
        tmp_path,
        "abcdef123456",
        "2024-01-02",
        "Subject",
        [{"filename": "report.txt", "data": b"attachment"}],
    )

    month_dir = tmp_path / "2024-01"
    message_dir = month_dir / "2024-01-02 - subject - abcdef12"
    assert _mode(tmp_path) == 0o700
    assert _mode(month_dir) == 0o700
    assert _mode(message_dir) == 0o700
    assert _mode(message_dir / "message.eml") == 0o600
    assert _mode(message_dir / "metadata.json") == 0o600
    assert _mode(message_dir / "report.txt") == 0o600


def test_scan_downloaded_metadata_ignores_incomplete_message_directory(tmp_path):
    incomplete = tmp_path / "2024-01" / "2024-01-02 - subject - abcdef12"
    incomplete.mkdir(parents=True)

    downloaded_ids, most_recent_date = scan_downloaded_metadata(tmp_path)

    assert downloaded_ids == set()
    assert most_recent_date is None


def test_scan_downloaded_metadata_uses_metadata_json_for_message_directories(tmp_path):
    complete = tmp_path / "2024-01" / "2024-01-02 - subject - abcdef12"
    complete.mkdir(parents=True)
    (complete / "metadata.json").write_text(
        json.dumps({"id": "abcdef123456", "date": "2024-01-02"})
    )

    downloaded_ids, most_recent_date = scan_downloaded_metadata(tmp_path)

    assert downloaded_ids == {"abcdef12"}
    assert most_recent_date == "2024-01-02"
