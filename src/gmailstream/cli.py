import json
import logging
import re
from datetime import datetime
from pathlib import Path

import click
import yaml

from gmailstream.auth import copy_private_file, ensure_private_dir, get_gmail_service
from gmailstream.config import load_config
from gmailstream.env import load_app_env
from gmailstream.gmail_client import (
    fetch_attachments,
    fetch_message_metadata,
    fetch_raw_message,
    search_messages,
)
from gmailstream.paths import get_profiles_dir, list_profiles, resolve_profile
from gmailstream.storage import (
    ensure_private_export_dir,
    save_attachments,
    save_eml,
    save_metadata,
    scan_downloaded_metadata,
)

logger = logging.getLogger(__name__)

load_app_env()

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_PROFILE_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def _validate_date(value: str | None, param_name: str):
    """Validate a YYYY-MM-DD date string."""
    if value is None:
        return
    if not _DATE_RE.match(value):
        raise click.BadParameter(
            f"Invalid date '{value}'. Expected format: YYYY-MM-DD",
            param_hint=f"'--{param_name}'",
        )
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        raise click.BadParameter(
            f"Invalid date '{value}'. Expected format: YYYY-MM-DD",
            param_hint=f"'--{param_name}'",
        )


def _validate_profile_name(name: str) -> None:
    """Validate a profile name for profile creation."""
    if not _PROFILE_NAME_RE.fullmatch(name):
        raise click.BadParameter(
            "Use only letters, numbers, dots, underscores, and hyphens; "
            "the name must start with a letter or number.",
            param_hint="name",
        )


@click.group(invoke_without_command=True)
@click.option(
    "--profile-dir",
    envvar="GMAIL_STREAMER_PROFILE_DIR",
    default=None,
    type=click.Path(file_okay=False),
    help="Override profiles directory.",
)
@click.option("--profile", default=None, type=str, help="Profile to run.")
@click.option("--from", "from_date", default=None, type=str, help="Start date (YYYY-MM-DD)")
@click.option("--to", "to_date", default=None, type=str, help="End date (YYYY-MM-DD)")
@click.option("--verbose", "-v", is_flag=True, default=False, help="Enable debug logging.")
@click.pass_context
def main(ctx, profile_dir, profile, from_date, to_date, verbose):
    """Download Gmail messages matching configurable filters."""
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.WARNING,
        format="%(levelname)s: %(message)s",
    )
    ctx.ensure_object(dict)
    ctx.obj["profiles_dir"] = get_profiles_dir(profile_dir)

    if ctx.invoked_subcommand is not None:
        if profile:
            raise click.UsageError("--profile cannot be used with a subcommand.")
        return

    if not profile:
        click.echo(ctx.get_help())
        return

    _run_profile(ctx, profile, from_date, to_date)


@main.command()
@click.argument("profile")
@click.option("--from", "from_date", default=None, type=str, help="Start date (YYYY-MM-DD)")
@click.option("--to", "to_date", default=None, type=str, help="End date (YYYY-MM-DD)")
@click.pass_context
def run(ctx, profile, from_date, to_date):
    """Download messages for a profile."""
    _run_profile(ctx, profile, from_date, to_date)


def _run_profile(ctx, profile, from_date, to_date):
    """Download messages for a profile."""
    _validate_date(from_date, "from")
    _validate_date(to_date, "to")

    profiles_dir = ctx.obj["profiles_dir"]
    profile_path = resolve_profile(profile, profiles_dir)

    if not profile_path.is_dir():
        raise click.ClickException(f"Profile directory not found: {profile_path}")

    config = load_config(profile_path)
    target = Path(config.target_directory)
    ensure_private_export_dir(target)

    click.echo(f"Authenticating profile '{profile_path.name}'...")
    service = get_gmail_service(profile_path)

    if from_date or to_date:
        # Explicit date range mode — ignore incremental tracking
        downloaded_ids, _ = scan_downloaded_metadata(target, from_date=from_date, to_date=to_date)
        click.echo(
            f"Date range: {from_date or 'beginning'} to {to_date or 'now'} "
            f"({len(downloaded_ids)} already downloaded)"
        )
        click.echo(f"Searching: {config.filter}")
        msg_ids = search_messages(service, config.filter, after_date=from_date, before_date=to_date)
    else:
        # Incremental mode (existing behavior)
        downloaded_ids, most_recent_date = scan_downloaded_metadata(target)
        if most_recent_date:
            click.echo(
                f"Resuming from {most_recent_date} "
                f"({len(downloaded_ids)} already downloaded)"
            )
        click.echo(f"Searching: {config.filter}")
        msg_ids = search_messages(service, config.filter, after_date=most_recent_date)

    new_ids = [mid for mid in msg_ids if mid[:8] not in downloaded_ids]
    click.echo(f"Found {len(msg_ids)} messages, {len(new_ids)} new.")

    successes = 0
    failures = 0

    for i, msg_id in enumerate(new_ids, 1):
        click.echo(f"[{i}/{len(new_ids)}] Downloading {msg_id}...")

        try:
            metadata = fetch_message_metadata(service, msg_id)
            date = metadata["date"]
            subject = metadata.get("subject", "")

            if config.mode == "full":
                raw = fetch_raw_message(service, msg_id)
                save_eml(target, msg_id, date, subject, raw)
                attachments = fetch_attachments(service, msg_id)
                if attachments:
                    save_attachments(target, msg_id, date, subject, attachments)

            elif config.mode == "attachments_only":
                attachments = fetch_attachments(service, msg_id)
                if attachments:
                    save_attachments(target, msg_id, date, subject, attachments)
                else:
                    click.echo(f"  No attachments for {msg_id}")

            save_metadata(target, msg_id, date, subject, metadata)
            successes += 1

        except Exception as e:
            failures += 1
            logger.debug("Error processing message %s", msg_id, exc_info=True)
            click.echo(f"  Failed: {e}", err=True)

    total = successes + failures
    if total > 0:
        click.echo(f"Done. Downloaded {successes}/{total}, {failures} failed.")
    else:
        click.echo("Done. No new messages to download.")

    if total > 0 and successes == 0:
        ctx.exit(1)


@main.group("profiles")
def profiles_group():
    """Manage profiles."""


@profiles_group.command("list")
@click.pass_context
def profiles_list(ctx):
    """List available profiles."""
    profiles_dir = ctx.obj["profiles_dir"]
    names = list_profiles(profiles_dir)
    if not names:
        click.echo(f"No profiles found in {profiles_dir}")
        return
    click.echo(f"Profiles in {profiles_dir}:\n")
    for name in names:
        click.echo(f"  {name}")


@profiles_group.command("init")
@click.argument("name")
@click.pass_context
def profiles_init(ctx, name):
    """Interactively create and authenticate a new profile."""
    _validate_profile_name(name)
    profiles_dir = ctx.obj["profiles_dir"]
    profile_dir = profiles_dir / name

    if profile_dir.exists():
        raise click.ClickException(f"Profile already exists: {profile_dir}")

    click.echo(f"\nCreating profile '{name}'\n")

    # Step 1 — Config prompts
    filter_query = click.prompt("Gmail filter query", default="has:attachment")
    default_target = str(profile_dir / "downloads")
    target_directory = click.prompt("Target directory for downloads", default=default_target)
    mode = click.prompt(
        "Download mode",
        type=click.Choice(["full", "attachments_only"]),
        default="full",
    )

    ensure_private_dir(profile_dir)
    config = {
        "filter": filter_query,
        "target_directory": target_directory,
        "mode": mode,
    }
    (profile_dir / "config.yaml").write_text(yaml.dump(config, default_flow_style=False))

    # Step 2 — Credentials setup
    click.echo(
        "\nNext, you need a Google OAuth credentials file.\n"
        "Follow the guide to create one:\n"
        "  https://github.com/tsilva/gmailstream/blob/main/docs/credentials-guide.md\n"
    )
    default_credentials = str(profile_dir / "credentials.json")
    creds_src = click.prompt(
        "Path to your downloaded credentials.json",
        default=default_credentials,
    )
    creds_src_path = Path(creds_src).expanduser().resolve()
    creds_dest_path = profile_dir / "credentials.json"

    if not creds_src_path.exists():
        raise click.ClickException(f"File not found: {creds_src_path}")

    try:
        creds_data = json.loads(creds_src_path.read_text())
        if not ("installed" in creds_data or "web" in creds_data):
            raise click.ClickException(
                "Invalid credentials.json: missing 'installed' or 'web' key. "
                "Make sure you downloaded an OAuth 2.0 Client ID (not a service account)."
            )
    except json.JSONDecodeError as e:
        raise click.ClickException(f"credentials.json is not valid JSON: {e}")

    if creds_src_path != creds_dest_path.resolve():
        copy_private_file(creds_src_path, creds_dest_path)
        click.echo("Credentials copied.")
    else:
        click.echo("Credentials ready.")

    # Step 3 — OAuth flow
    click.echo("\nOpening browser for Google authorization...")
    try:
        get_gmail_service(profile_dir)
        click.echo("Authentication complete.")
    except Exception as e:
        raise click.ClickException(f"OAuth flow failed: {e}")

    # Step 4 — Summary
    click.echo(f"\nProfile '{name}' is ready!")
    click.echo(f"  Location : {profile_dir}")
    click.echo(f"  Filter   : {filter_query}")
    click.echo(f"  Output   : {target_directory}")
    click.echo(f"  Mode     : {mode}")
    click.echo(f"\nRun it with:\n  gmailstream --profile {name}")


@profiles_group.command("show")
@click.argument("name")
@click.pass_context
def profiles_show(ctx, name):
    """Show a profile's configuration."""
    profiles_dir = ctx.obj["profiles_dir"]
    profile_path = resolve_profile(name, profiles_dir)

    if not profile_path.is_dir():
        raise click.ClickException(f"Profile not found: {profile_path}")

    config_file = profile_path / "config.yaml"
    if not config_file.exists():
        raise click.ClickException(f"No config.yaml in {profile_path}")

    click.echo(f"Profile: {profile_path.name} ({profile_path})\n")
    click.echo(config_file.read_text())
