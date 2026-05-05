import json

import pytest

from gmailstream.storage import save_attachments, scan_downloaded_metadata


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
