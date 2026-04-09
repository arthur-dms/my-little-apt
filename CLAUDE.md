# CLAUDE.md — my-little-apt

## Project Overview

This is a monorepo containing the services for the **My Little Apt** application. Each service lives in its own subdirectory and is independently developed, tested, and deployed.

| Directory | Description | Language |
|---|---|---|
| `discord-bot/` | Discord command-and-control bot | Python 3.12 |
| `server/` | Backend API server (FastAPI) | Python 3.12 |
| `app/` | *(planned)* Client application | TBD |

---

## Repository Conventions

- **No environment variables for secrets** — credentials and IDs are hardcoded in each service's config file (e.g., `discord-bot/config.py`). Update them directly in code before running.
- **Human-readable variable names** — all variable and function names must be self-explanatory in English.
- **Monorepo structure** — each service is self-contained with its own dependencies, tests, and CI/CD pipeline.

---

## Communication Architecture

The Discord bot communicates with the C2 server via **direct HTTP calls** (using `httpx`). If the server is unreachable, the bot falls back to standalone/demo mode using the local `DeviceManager`.

```
Discord Bot  ──HTTP──▶  FastAPI Server  ──HTTP──▶  Client App (future)
     │                       │
     │ GET /admin/devices    │ POST /beacon/check-in
     │ GET /admin/cookies    │ GET  /beacon/tasks/{name}
     │ POST /admin/...       │ POST /beacon/result
     ▼                       ▼
```

---

## discord-bot

### Architecture

```
discord-bot/
├── bot.py               # Entry point — registers commands, HTTP bridge to server
├── config.py            # Hardcoded config: bot token, admin ID, server URL
├── devices.py           # DeviceManager class — fallback/standalone logic
├── pyproject.toml       # Tool configuration (pytest, mypy, flake8)
├── requirements.txt     # Production dependencies (discord.py, httpx)
├── requirements-dev.txt # Dev/test dependencies
└── tests/               # pytest test suite (~100 tests, ~96% coverage)
```

### Key Design Decisions

- **Admin-only access**: commands are gated by `is_admin_user()` which checks `interaction.user.id == ADMIN_DISCORD_ID`.
- **HTTP bridge**: The bot calls the server's `/admin/*` endpoints via `httpx`. Falls back to standalone logic if the server is unreachable.
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
# Edit config.py → set DISCORD_BOT_TOKEN, ADMIN_DISCORD_ID, and C2_SERVER_URL
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

## server (Backend API)

The server acts as an intermediary, receiving commands from the Discord bot via HTTP (`/admin/*` endpoints) and serving tasks to the client app over HTTP (`/beacon/*` endpoints).

### API Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/health` | Health check |
| `GET` | `/admin/devices` | List managed devices |
| `GET` | `/admin/cookies` | Retrieve cookies from all devices |
| `POST` | `/admin/beacon-interval` | Set beacon interval |
| `POST` | `/admin/communication-protocol` | Set communication protocol |
| `POST` | `/beacon/check-in` | Beacon registers/updates presence |
| `GET` | `/beacon/tasks/{name}` | Beacon polls for pending tasks |
| `POST` | `/beacon/result` | Beacon submits task result |
| `GET` | `/beacon/config` | Get current server config |

### Running Locally

```bash
cd server
pip install -r requirements.txt
cp config-example.py config.py
uvicorn server:app --reload
# Or equivalently: python server.py
```

### Testing

```bash
cd server
pip install -r requirements-dev.txt
pytest tests/ -v --cov=. --cov-report=term-missing
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
