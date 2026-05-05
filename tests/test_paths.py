from gmailstream.paths import resolve_profile


def test_resolve_profile_keeps_simple_names_inside_profiles_dir(tmp_path):
    profiles_dir = tmp_path / "profiles"

    assert resolve_profile("inbox", profiles_dir) == profiles_dir / "inbox"


def test_resolve_profile_does_not_fallback_path_like_names_inside_profiles_dir(
    monkeypatch, tmp_path
):
    profiles_dir = tmp_path / "profiles"
    escaped_profile = tmp_path / "escape"
    cwd = tmp_path / "work" / "current"
    profiles_dir.mkdir()
    escaped_profile.mkdir()
    cwd.mkdir(parents=True)
    monkeypatch.chdir(cwd)

    resolved = resolve_profile("../escape", profiles_dir)

    assert resolved != escaped_profile
    assert resolved == (cwd / "../escape").resolve()


def test_resolve_profile_accepts_existing_direct_paths(tmp_path):
    profile_dir = tmp_path / "direct-profile"
    profile_dir.mkdir()

    assert resolve_profile(str(profile_dir), tmp_path / "profiles") == profile_dir.resolve()
