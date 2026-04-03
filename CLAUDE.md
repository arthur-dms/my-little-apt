# CLAUDE.md — my-little-apt

## Project Overview

This is a monorepo containing the services for the **My Little Apt** application. Each service lives in its own subdirectory and is independently developed, tested, and deployed.

| Directory | Description | Language |
|---|---|---|
| `discord-bot/` | Discord command-and-control bot | Python 3.12 |
| `server/` | *(planned)* Backend API server | TBD |
| `app/` | *(planned)* Frontend application | TBD |

---

## Repository Conventions

- **No environment variables for secrets** — credentials and IDs are hardcoded in each service's config file (e.g., `discord-bot/config.py`). Update them directly in code before running.
- **Human-readable variable names** — all variable and function names must be self-explanatory in English.
- **Monorepo structure** — each service is self-contained with its own dependencies, tests, and CI/CD pipeline.

---

## discord-bot

### Architecture

```
discord-bot/
├── bot.py               # Entry point — registers commands, enforces admin-only access
├── config.py            # Hardcoded config: bot token, admin ID, valid parameter values
├── devices.py           # DeviceManager class — business logic for all commands
├── pyproject.toml       # Tool configuration (pytest, mypy, flake8)
├── requirements.txt     # Production dependencies
├── requirements-dev.txt # Dev/test dependencies
└── tests/               # pytest test suite (89 tests, ~97% coverage)
```

### Key Design Decisions

- **Admin-only access**: commands are gated by `is_admin_user()` which checks `interaction.user.id == ADMIN_DISCORD_ID`.
- **Separation of concerns**: `DeviceManager` (in `devices.py`) holds all business logic; `bot.py` is a thin adapter layer.
- **Slash commands with autocomplete**: uses Discord's `app_commands` for native `/` command support with parameter suggestions.
- **Terminal logging**: every command invocation and access denial is logged to stdout.

### Available Commands

| Command | Arguments | Description |
|---|---|---|
| `/show-devices` | — | Lists all managed devices with status |
| `/set-beacon-interval` | `2 \| 8 \| 16 \| 32` (autocomplete) | Sets the beacon interval (seconds) |
| `/request-cookies` | — | Displays stored cookies |
| `/set-communication-protocol` | `http \| https \| dns` (autocomplete) | Sets the communication protocol |

### Running Locally

```bash
cd discord-bot
pip install -r requirements.txt
# Edit config.py → set DISCORD_BOT_TOKEN and ADMIN_DISCORD_ID
python bot.py
```

### Testing

```bash
cd discord-bot
pip install -r requirements-dev.txt
pytest tests/ -v --cov=. --cov-report=term-missing --cov-fail-under=80
```

### Linting & Static Analysis

```bash
cd discord-bot
flake8 bot.py config.py devices.py --max-line-length 100
mypy bot.py config.py devices.py --ignore-missing-imports
bandit -r . --exclude ./tests -ll
```

---

## CI/CD

All GitHub Actions workflows live in the repo root at `.github/workflows/`. Each service has its own workflow file, scoped by `paths` filters.

### discord-bot pipeline (`.github/workflows/discord-bot-ci.yml`)

Triggers on `push` / `pull_request` to `main` when files in `discord-bot/` change.

1. **Lint & Static Analysis** — `flake8` (PEP 8), `mypy` (type checking), `bandit` (security)
2. **Tests & Coverage** — `pytest` with 80% minimum coverage threshold

---

## Code Style

- **Python**: PEP 8, enforced by `flake8` (max line length 100). Type hints on all public functions; checked by `mypy`.
- **Commits**: use conventional commits (`feat:`, `fix:`, `docs:`, `test:`, `ci:`).
- **Tests**: pytest with `pytest-asyncio`. Every new feature must include tests to maintain ≥80% coverage.
