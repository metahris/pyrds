from __future__ import annotations

from pyrds.infrastructure.config.settings import ApiClientSettings
from pyrds.infrastructure.http.base_api import BaseAPI


def test_base_api_clients_have_no_request_timeout() -> None:
    api = BaseAPI(
        logger=None,
        settings=ApiClientSettings(port=5202, host="http://localhost"),
    )
    try:
        assert api._sync_client.timeout.connect is None
        assert api._sync_client.timeout.read is None
        assert api._sync_client.timeout.write is None
        assert api._sync_client.timeout.pool is None
        assert api._async_client.timeout.connect is None
        assert api._async_client.timeout.read is None
        assert api._async_client.timeout.write is None
        assert api._async_client.timeout.pool is None
    finally:
        api.close()
