# 🏠 My Little APT

A monorepo for an educational Command and Control (C2) project. The system is composed of a **Discord bot** (admin panel), a **server** (C2 backend), and a **client app** — all managed in a single repository.

> ⚠️ **Disclaimer:** This project was created **strictly for educational purposes**. It is intended to help understand cybersecurity concepts such as C2 architectures, network protocols, and defensive strategies. **Do not use this for any malicious or unauthorized activity.**

---

## Architecture

```
my-little-apt/
├── discord-bot/   → Discord-based admin panel (Python)
├── server/        → C2 backend server (FastAPI + Redis)
└── app/           → Client application (planned)
```

---

## 🤖 Discord Bot

The Discord bot serves as the **admin panel** for the C2 server. It accepts commands exclusively from an authorized administrator.

### Available Commands

| Command | Arguments | Description |
|---|---|---|
| `/show-devices` | — | Lists all managed devices with their status |
| `/set-beacon-interval` | `2` \| `8` \| `16` \| `32` (autocomplete) | Sets the beacon interval (seconds) |
| `/request-cookies` | — | Displays stored cookies from managed devices |
| `/set-communication-protocol` | `http` \| `https` \| `dns` (autocomplete) | Sets the communication protocol |

> **Note:** Commands use Discord's native slash command system — type `/` in the chat to see all available commands with autocomplete.
> The bot sends commands to the C2 server via a **Redis message queue**. If the server is offline, the bot falls back to standalone/demo mode.

### Quick Start

1. **Install system requirements**
   You will need **Redis** installed and running on your system for message routing between the bot and the server.
   ```bash
   sudo apt update && sudo apt install redis-server -y
   # Or using Docker: docker run -d -p 6379:6379 redis
   ```

2. **Start the Discord Bot**
   ```bash
   cd discord-bot
   
   # Install dependencies
   pip install -r requirements.txt
   
   # Copy the example config and fill in your real credentials
   cp config-example.py config.py
   # Edit config.py → set DISCORD_BOT_TOKEN and ADMIN_DISCORD_ID
   
   # Run the bot
   python bot.py
   ```

3. **Start the C2 Server (New terminal)**
   ```bash
   cd server
   pip install -r requirements.txt
   cp config-example.py config.py
   uvicorn server:app --reload
   ```

### Running Tests

```bash
cd discord-bot
pip install -r requirements-dev.txt
pytest tests/ -v --cov=. --cov-report=term-missing
```

---

## CI/CD

All GitHub Actions workflows live in the repo root at `.github/workflows/`. The **discord-bot** pipeline (`.github/workflows/discord-bot-ci.yml`) runs on every push/PR to `main`:

1. **Static Analysis** — `flake8` (PEP 8), `mypy` (type checking), `bandit` (security)
2. **Tests & Coverage** — `pytest` with a minimum 80% coverage threshold

---

## Project Structure

| File / Directory | Purpose |
|---|---|
| `discord-bot/bot.py` | Bot entry point, slash commands, access control, logging |
| `discord-bot/config-example.py` | Configuration template (copy to `config.py`) |
| `discord-bot/devices.py` | `DeviceManager` class — business logic |
| `discord-bot/tests/` | Test suite (89 tests, ~97% coverage) |
| `.github/workflows/` | CI/CD pipeline definitions |
| `CLAUDE.md` | Internal project documentation for AI agents |

---

## Security

- `config.py` is **excluded from version control** via `.gitignore` — it contains real credentials.
- Use `config-example.py` as a template and create your own `config.py` locally.

---

## License

This project is for **educational purposes only**.
