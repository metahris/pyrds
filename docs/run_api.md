# Running the API

Run the FastAPI development server:

```bash
fastapi dev pyrds/api/run.py
```

If you are already inside `pyrds/api`, use:

```bash
fastapi dev run.py
```

This uses FastAPI's development server and discovers the `app` object exported by `pyrds/api/run.py`.

For Python breakpoints or explicit Uvicorn settings, run the same file directly:

```bash
python pyrds/api/run.py --debug
```

`--debug` starts Uvicorn with auto-reload and debug logging.

## Configuration Order

Host and port are resolved in this order:

1. CLI flags: `--host`, `--port`
2. `pyrds/infrastructure/config/config.json`: `pyrds_api.host`, `pyrds_api.port`

You can select a config file with:

```bash
python pyrds/api/run.py --config-file /path/to/config.json --debug
```

## Examples

Run with FastAPI dev:

```bash
fastapi dev pyrds/api/run.py
```

Run with Uvicorn and config defaults:

```bash
python pyrds/api/run.py
```

Run with Uvicorn debug mode:

```bash
python pyrds/api/run.py --debug
```

Use another port:

```bash
python pyrds/api/run.py --port 8001 --debug
```

Bind to all interfaces:

```bash
python pyrds/api/run.py --host 0.0.0.0 --port 8001
```

Swagger is available at:

```text
http://127.0.0.1:<port>/docs
```

If the port is already used:

```bash
lsof -i :8000
kill -9 <PID>
```

or run on another port:

```bash
python pyrds/api/run.py --port 8001 --debug
```
