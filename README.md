# applog

Drop-in logging for Python apps. One call at startup gives you:

- Console + rotating file logs (`app.log`) and a separate `errors.log`
- File name, line number and function name on every line
- A **request id** on every line, so you can trace one request end to end
- Full tracebacks for unhandled errors
- Uvicorn / `fastapi dev` logs in the same format
- Noisy libraries quieted by default (and a fix for the file-watcher feedback loop)

The core has **zero dependencies** (standard library only). The FastAPI/Starlette middleware is an optional extra.

---

## Install

From GitHub (pin a version tag):

```bash
# core only
uv add "applog @ git+https://github.com/coolbams/appLog@v0.1.0"

# with the FastAPI/Starlette middleware
uv add "applog[fastapi] @ git+https://github.com/coolbams/appLog@v0.1.0"
```

While developing it locally (edits show up instantly):

```bash
uv add --editable "../applog[fastapi]"
```

Requires Python 3.10+.

---

## Quick start (FastAPI)

```python
# main.py
from fastapi import FastAPI
from applog import setup_logging
from applog.middleware import RequestLoggingMiddleware

setup_logging(level="INFO", log_dir="logs")   # call once, before anything logs

app = FastAPI()
app.add_middleware(RequestLoggingMiddleware)
```

In **every other file**, no setup, just two lines:

```python
import logging

log = logging.getLogger(__name__)

log.info("Registered user id=%s", user.id)
log.warning("Failed login for %s", email)
```

Inside an `except` block, use `log.exception` so the traceback is included:

```python
try:
    ...
except Exception:
    log.exception("Failed to create session for user %s", user.id)
    raise
```

### Example output

```
2026-11-08 10:31:02,114 | INFO     | a1b2c3d4 | auth.router:41 register | Registered user id=7f3c...
2026-11-08 10:31:02,120 | INFO     | a1b2c3d4 | applog.requests:30 dispatch | POST /auth/register -> 201 (12.3 ms)
```

Columns: `time | level | request id | module:line function | message`

---

## Quick start (script / non-FastAPI)

```python
import logging
from applog import setup_logging

setup_logging(level="DEBUG", log_dir="logs")
log = logging.getLogger(__name__)
log.info("hello")
```

No Starlette needed. Install plain `applog` (no extra).

---

## API reference

### `setup_logging(...)`

Configures logging for the whole process. Call **once**, at startup, in your entry point only (never in library modules).

```python
from applog import setup_logging
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `level` | `str` | `"INFO"` | Root log level: `"DEBUG"`, `"INFO"`, `"WARNING"`, `"ERROR"`, `"CRITICAL"` |
| `log_dir` | `str \| Path` | `"logs"` | Folder for log files. Created if missing. Relative paths are relative to where you **run** the app |
| `fmt` | `str` | see below | Log line format (standard `logging` format string) |
| `to_console` | `bool` | `True` | Print logs to the terminal (stderr) |
| `to_file` | `bool` | `True` | Write `app.log` (everything) and `errors.log` (ERROR and above) |
| `max_bytes` | `int` | `5_000_000` | Rotate a log file when it reaches this size |
| `backup_count` | `int` | `3` | How many rotated files to keep (`app.log.1`, `.2`, `.3`) |
| `quiet` | `dict[str, str] \| None` | `None` | Extra `{"logger.name": "LEVEL"}` entries to silence noisy libraries. **Merged** with the defaults |
| `capture_uvicorn` | `bool` | `True` | Route uvicorn / `fastapi dev` logs through the same handlers and format |

Default format:

```
%(asctime)s | %(levelname)-8s | %(request_id)s | %(name)s:%(lineno)d %(funcName)s | %(message)s
```

Default quieted loggers (`DEFAULT_QUIET`):

| Logger | Level | Why |
|---|---|---|
| `watchfiles` | `WARNING` | The reload watcher logs "1 change detected" every time the log file is written, which creates an endless feedback loop |
| `sqlalchemy.engine` | `WARNING` | Hides every SQL statement. Set to `"INFO"` to see queries |
| `uvicorn.access` | `WARNING` | Avoids duplicate request lines (the middleware already logs them) |

Examples:

```python
# Debug mode, custom folder
setup_logging(level="DEBUG", log_dir="/var/log/myapp")

# Silence another library, and show SQL queries
setup_logging(quiet={"httpx": "WARNING", "sqlalchemy.engine": "INFO"})

# Console only (e.g. in a container that collects stdout)
setup_logging(to_file=False)

# Files only
setup_logging(to_console=False)

# Custom format
setup_logging(fmt="%(asctime)s %(levelname)s [%(request_id)s] %(name)s: %(message)s")
```

### `RequestLoggingMiddleware`

Starlette/FastAPI middleware. Requires the `fastapi` extra.

```python
from applog.middleware import RequestLoggingMiddleware

app.add_middleware(RequestLoggingMiddleware)
```

No arguments. For every request it:

1. Generates an 8-character request id and stores it in `request_id_var`
2. Logs one summary line: `METHOD /path -> status (ms)`
3. Adds an `X-Request-ID` header to the response
4. On an unhandled exception: logs the **full traceback** and returns a `500` JSON body containing the `request_id`, so a user can quote it to you

Notes:
- Expected errors raised as `HTTPException` (401, 404, 409...) are normal responses, not crashes. Log them yourself where they're raised if you want them recorded.
- Logger name: `applog.requests`.

### `request_id_var`

A `ContextVar[str]` holding the current request's id (`"-"` when there isn't one).

```python
from applog import request_id_var

request_id_var.get()          # read the current id, e.g. include it in an API response
request_id_var.set("job-42")  # set your own id in a script or background job
```

### `RequestIdFilter`

A `logging.Filter` that stamps each record with `request_id` (this is what makes `%(request_id)s` work in the format). `setup_logging` attaches it for you. You only need it directly if you build your own handlers:

```python
from applog.context import RequestIdFilter

handler.addFilter(RequestIdFilter())
```

---

## Files produced

With `to_file=True`, inside `log_dir`:

| File | Contents |
|---|---|
| `app.log` | Everything at or above `level` |
| `errors.log` | Only `ERROR` and `CRITICAL` (including tracebacks) |
| `app.log.1`, `.2`, `.3` | Older, rotated logs |

Add `logs/` to your `.gitignore`.

---

## Tracing an error

1. Open `logs/errors.log`, find the traceback and its request id (e.g. `a1b2c3d4`).
2. Replay that whole request:

   ```bash
   grep a1b2c3d4 logs/app.log
   ```
3. Watch logs live:

   ```bash
   tail -f logs/app.log
   ```

---

## Logging rules

- Use `%s` arguments, not f-strings: `log.info("user %s", uid)`. Logging only builds the string if that level is enabled.
- Use `log.exception(...)` inside `except` blocks. `log.error(...)` alone drops the traceback.
- **Never log secrets**: passwords, password hashes, session ids, tokens. Also avoid logging whole request objects (`log.info("body: %s", body)` can dump a password).
- Levels: `INFO` for normal events, `WARNING` for expected problems (bad password), `ERROR` for bugs.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| Nothing prints to the terminal | Make sure `setup_logging()` runs before your first log call, and that you've actually made a request (the middleware only logs when a request arrives) |
| `app.log` fills with "1 change detected" lines | The reload watcher is logging the log file's own changes. Make sure `watchfiles` is quieted (it is by default, so don't override it with `quiet=`) |
| Logs written to an unexpected folder | `log_dir` is relative to the **current working directory**. Run the app from your project root or pass an absolute path |
| `ModuleNotFoundError: starlette` | Install with the extra: `applog[fastapi]` |
| Duplicate lines | `setup_logging()` was called more than once, or another library configured the root logger. Call it once, in your entry point |

---

## Development

```bash
git clone https://github.com/<you>/applog
cd applog
uv sync --extra fastapi
uv run python -c "from applog import setup_logging; setup_logging(); import logging; logging.getLogger('t').info('works')"
```

Releasing a new version: bump `version` in `pyproject.toml`, then

```bash
git tag v0.1.1 && git push --tags
```

and update the tag in each project (`@v0.1.1`).

## Layout

```
src/applog/
├── __init__.py     # exports setup_logging, request_id_var
├── config.py       # setup_logging, DEFAULT_FORMAT, DEFAULT_QUIET
├── context.py      # request_id_var, RequestIdFilter
├── middleware.py   # RequestLoggingMiddleware (needs starlette)
└── py.typed        # marks the package as typed
```
