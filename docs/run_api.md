# Running the API

Run the API:

```bash
fastapi dev pyrds/api/run.py
```

If you are already inside `pyrds/api`, use:

```bash
fastapi dev run.py
```

For IDE breakpoints, run:

```bash
python pyrds/api/run.py --debug
```

## Configuration Order

Host and port are resolved in this order:

1. CLI flags: `--host`, `--port`
2. `pyrds/infrastructure/config/config.json`: `pyrds_api.host`, `pyrds_api.port`

Use another port:

```bash
python pyrds/api/run.py --debug --port 8001
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
python pyrds/api/run.py --debug --port 8001
```
