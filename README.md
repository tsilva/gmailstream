<div align="center">
  <img src="logo.png" alt="gmailstream" width="512"/>

  [![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://python.org)
  [![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

  **📧 Download Gmail messages matching your filters to local files 📥**

</div>

## ✨ Features

[![CI](https://github.com/tsilva/gmailstream/actions/workflows/ci.yml/badge.svg)](https://github.com/tsilva/gmailstream/actions/workflows/ci.yml)

- **🗂️ Profile-based configuration** — run multiple independent download profiles, each with its own filters, credentials, and output directory
- **🔐 OAuth2 authentication** — secure Google sign-in with automatic token caching
- **📧 Full message download** — save complete `.eml` files for archival
- **📎 Attachments-only mode** — grab just the attachments, skip the rest
- **🧠 Incremental downloads** — remembers what's already been downloaded, no duplicates across runs
- **🔍 Gmail search filters** — use any Gmail search query (`from:`, `has:attachment`, `after:`, label filters, etc.)
- **🏠 Works from anywhere** — install globally with `uv` and run from any directory

## 🚀 Quick Start

### 1. Install

```bash
git clone https://github.com/tsilva/gmailstream.git
cd gmailstream
uv tool install . --force --no-cache
```

### 2. Create a profile

```bash
gmailstream profiles init my-profile
```

This interactive wizard will:
- Prompt for your Gmail filter, output directory, and download mode
- Guide you to create OAuth credentials ([see credentials guide](docs/credentials-guide.md))
- Copy your `credentials.json` and open a browser for Google authorization immediately

Your profile is stored at `~/.gmailstream/profiles/my-profile/`.

### 3. Run

```bash
gmailstream run my-profile
```

Subsequent runs reuse the cached OAuth token and pick up only new messages.

## 📁 Profile Resolution

The profiles directory is resolved in this order:

1. `--profile-dir` flag or `GMAIL_STREAMER_PROFILE_DIR` env var
2. `~/.gmailstream/profiles/` (default)

The `profile` argument can be a **name** (looked up in the profiles directory) or a **path** to an existing directory (backward compatible).

## 🛠️ CLI Reference

```bash
gmailstream run <profile>                         # Download messages
gmailstream run <profile> --from 2024-01-01       # From a start date
gmailstream run <profile> --to 2024-12-31         # Up to an end date
gmailstream --verbose run <profile>               # Enable debug logging
gmailstream --profile-dir /path run <profile>     # Custom profiles directory
gmailstream profiles list                         # List available profiles
gmailstream profiles init <name>                  # Create a new profile (interactive)
gmailstream profiles show <name>                  # Show profile config
```

## ⚙️ Profile Structure

Each profile lives in its own directory with:

| File | Purpose |
|------|---------|
| `config.yaml` | Filter query, target directory, download mode |
| `credentials.json` | OAuth client credentials (you provide this) |
| `token.json` | Auto-generated after first OAuth flow |

## 🏗️ Architecture

| Module | Responsibility |
|--------|---------------|
| `cli.py` | Click CLI entry point (group with `run` and `profiles` subcommands) |
| `paths.py` | Profile directory resolution and discovery |
| `config.py` | Loads and validates `config.yaml` into a `ProfileConfig` dataclass |
| `auth.py` | OAuth2 flow with token caching |
| `gmail_client.py` | Gmail API wrapper: search, fetch messages, fetch attachments |
| `storage.py` | Saves `.eml` files and attachments to disk |

## 📄 License

[MIT](LICENSE)
