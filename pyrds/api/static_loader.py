from __future__ import annotations

import json
from pathlib import Path
from typing import Any


API_DIR = Path(__file__).resolve().parent
STATIC_DIR = API_DIR / "static"


def load_static_json(file_name: str, default: Any) -> Any:
    file_path = STATIC_DIR / file_name
    if not file_path.exists():
        return default
    with file_path.open("r", encoding="utf-8") as file_handle:
        return json.load(file_handle)


def load_api_metadata() -> dict[str, Any]:
    return load_static_json(
        "metadata.json",
        {
            "title": "Pyrds",
            "description": "Pricing workflow API.",
            "version": "3.0.0",
        },
    )


def load_api_tags() -> list[dict[str, Any]]:
    return load_static_json("tags.json", [])
