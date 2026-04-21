from __future__ import annotations

from functools import lru_cache

from pyrds.api.logging import api_logger
from pyrds.infrastructure.config.settings import Settings
from pyrds.sdk.client import PyrdsClient


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings.load()


@lru_cache(maxsize=1)
def get_client() -> PyrdsClient:
    return PyrdsClient(settings=get_settings(), logger=api_logger)
