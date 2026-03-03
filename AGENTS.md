# CLAUDE.md

## Project Overview

gmailstream is a Python CLI tool that downloads Gmail messages matching configurable filters via OAuth2, organized by profiles.

## Build & Run

```bash
uv sync                                          # Install dependencies
gmailstream run <profile>                     # Download messages
gmailstream --profile-dir /path run <profile> # Custom profile dir
gmailstream profiles list                     # List available profiles
gmailstream profiles init <name>              # Scaffold new profile
gmailstream profiles show <name>              # Show profile config
```

## Architecture

- `src/gmailstream/cli.py` — Click CLI entry point (group with `run` and `profiles` subcommands)
- `src/gmailstream/paths.py` — Profile directory resolution and discovery
- `src/gmailstream/config.py` — Loads and validates `config.yaml` into a `ProfileConfig` dataclass
- `src/gmailstream/auth.py` — OAuth2 flow using google-auth-oauthlib, token caching
- `src/gmailstream/gmail_client.py` — Gmail API wrapper: search, fetch raw messages, fetch attachments
- `src/gmailstream/storage.py` — Saves `.eml` files and attachment files to disk

## Profile Resolution

Profiles directory is resolved in this order:
1. `--profile-dir` flag or `GMAIL_STREAMER_PROFILE_DIR` env var
2. `~/.gmailstream/profiles/` (default)

The `profile` argument to `run` can be a name (looked up in the profiles dir) or a path to an existing directory.

## Profile Structure

Each profile lives in its own directory with:
- `config.yaml` — filter query, target directory, mode (full/attachments_only)
- `credentials.json` — user-provided OAuth client credentials
- `token.json` — auto-generated after first OAuth flow

## Key Conventions

- Python 3.12+, uses hatchling build backend with uv
- No tests yet
- Sensitive files (token.json, credentials.json) are gitignored
- README.md must be kept up to date with any significant project changes
