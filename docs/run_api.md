# Running the API

## Swagger

```bash
fastapi dev pyrds/api/run.py
```

If you are already inside `pyrds/api`, use:

```bash
fastapi dev run.py
```

Swagger is available at:

```text
http://127.0.0.1:8000/docs
```

## Debugging In PyCharm

### 1. Open File

Open:

```text
pyrds/api/run.py
```

### 2. Create Debug Configuration

In the top-right corner:

Click the dropdown, then `Edit Configurations...`.

Click `+`, then select `Python`.

Fill:

```text
Name: Pyrds API Debug
Script path: <project_root>/pyrds/api/run.py
Parameters: --debug
Working directory: <project_root>
Interpreter: your venv
```

Click `Apply`, then `OK`.

### 3. Add Breakpoint

Click in the left gutter of any file to add a red breakpoint dot.

### 4. Start Debugging

Select `Pyrds API Debug`.

Click `Debug`, not `Run`.

### 5. Trigger Breakpoint

Open:

```text
http://127.0.0.1:8000/docs
```

Call an endpoint. The breakpoint should be hit.

## Critical Rules

- Always use PyCharm `Debug`.
- Never use the terminal for debugging.
- Never use `../run.py`.
- Never use `--reload` for breakpoint debugging.

If a breakpoint does not hit, enable:

```text
Settings -> Build, Execution, Deployment -> Debugger
Attach to subprocess automatically
```

## Command Line Debug

Only use this outside PyCharm:

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

If the port is already used:

```bash
lsof -i :8000
kill -9 <PID>
```

or run on another port:

```bash
python pyrds/api/run.py --debug --port 8001
```
