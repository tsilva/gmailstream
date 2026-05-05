<div align="center">
  <img src="https://raw.githubusercontent.com/tsilva/gmailstream/main/logo.png" alt="gmailstream" width="512"/>

  **📧 Download Gmail messages matching your filters to local files 📥**
</div>

gmailstream is a Python CLI for downloading Gmail messages through OAuth2. It uses named profiles so each export can keep its own Gmail search query, credentials, mode, and target directory.

Use it to archive full `.eml` messages or save attachments from messages matched by Gmail search filters such as `from:`, `has:attachment`, `after:`, labels, and other Gmail query syntax.

## Install

```bash
git clone https://github.com/tsilva/gmailstream.git
cd gmailstream
uv tool install . --force --no-cache
```

Create and authorize a profile, then run it:

```bash
gmailstream profiles init my-profile
gmailstream --profile my-profile
```

The init flow prompts for a Gmail filter, output directory, download mode, and a Google OAuth `credentials.json` file. See [Creating OAuth Credentials](docs/credentials-guide.md) for the Google Cloud setup.

## Commands

```bash
uv sync                                           # install development dependencies
uv tool install . --force --no-cache              # install the CLI from this checkout
gmailstream --profile <profile>                   # download new matching messages
gmailstream --profile <profile> --from 2024-01-01 # limit by start date
gmailstream --profile <profile> --to 2024-12-31   # limit by end date
gmailstream --verbose --profile <profile>         # enable debug logging
gmailstream --profile-dir /path --profile <name>  # use a custom profiles directory
gmailstream profiles list                         # list profiles
gmailstream profiles init <name>                  # create and authenticate a profile
gmailstream profiles show <name>                  # print profile config
```

## Notes

- Requires Python 3.12+ and `uv`.
- Profiles live in `~/.config/gmailstream/profiles/` by default. Override this with `--profile-dir` or `GMAIL_STREAMER_PROFILE_DIR`.
- Environment variables are loaded from `~/.config/gmailstream/.env` when present. Existing shell environment variables take priority.
- A profile can also be passed as a direct path to an existing profile directory.
- The legacy `gmailstream run <profile>` command still works.
- Each profile contains `config.yaml`, user-supplied `credentials.json`, and auto-generated `token.json`.
- `mode: full` saves `message.eml`, attachments, and `metadata.json`. `mode: attachments_only` saves attachments plus `metadata.json`.
- Downloads are organized under the target directory as `YYYY-MM/YYYY-MM-DD - subject - shortid/`.
- Runs are incremental by default. Explicit `--from` or `--to` date ranges search that date range and skip files already present there.
- `credentials.json`, `token.json`, and downloaded email exports are sensitive local files. On POSIX systems, gmailstream writes them with user-only permissions, and credentials/tokens are ignored by git.

## Architecture

![gmailstream architecture diagram](./architecture.png)

## License

[MIT](LICENSE)
