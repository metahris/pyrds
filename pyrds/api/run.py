from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

if __name__ == "__main__":
    app: Any = None
else:
    from pyrds.api.main import app


def main() -> None:
    args = _parse_args()

    import uvicorn

    from pyrds.infrastructure.config.settings import DEFAULT_CONFIG_FILE, Settings

    settings = (
        Settings.from_config_file(args.config_file)
        if args.config_file
        else Settings.from_config_file(DEFAULT_CONFIG_FILE)
    )
    host = args.host or _normalize_host(settings.pyrds_api.host)
    port = args.port or settings.pyrds_api.port
    reload = args.reload or args.debug
    log_level = args.log_level or ("debug" if args.debug else "info")

    uvicorn.run(
        "pyrds.api.run:app",
        host=host,
        port=port,
        reload=reload,
        log_level=log_level,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Pyrds FastAPI application with Uvicorn.")
    parser.add_argument(
        "--config-file",
        help="Path to config.json. Defaults to pyrds/infrastructure/config/config.json.",
    )
    parser.add_argument("--host", help="API bind host. Overrides pyrds_api.host.")
    parser.add_argument("--port", type=int, help="API bind port. Overrides pyrds_api.port.")
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable Uvicorn reload and debug logging for local development.",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable Uvicorn auto-reload without changing log level.",
    )
    parser.add_argument(
        "--log-level",
        choices=["critical", "error", "warning", "info", "debug", "trace"],
        help="Uvicorn log level.",
    )
    return parser.parse_args()


def _normalize_host(value: str | None) -> str:
    raw_value = (value or "127.0.0.1").strip()
    parsed = urlparse(raw_value if "://" in raw_value else f"//{raw_value}")
    return parsed.hostname or raw_value

if __name__ == "__main__":
    main()
