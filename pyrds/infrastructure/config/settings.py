from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, computed_field

from pyrds.domain.exceptions import ConfigError


PACKAGE_PATH = Path(__file__).resolve().parent
DEFAULT_CONFIG_FILE = PACKAGE_PATH / "config.json"


class FilesPath(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    working_dir: str
    xml_updater_path: str | None = None

    @computed_field
    @property
    def inputs(self) -> str:
        return str(Path(self.working_dir) / "inputs")

    @computed_field
    @property
    def data(self) -> str:
        return str(Path(self.working_dir) / "inputs" / "data")

    @computed_field
    @property
    def trade(self) -> str:
        return str(Path(self.working_dir) / "inputs" / "trade")

    @computed_field
    @property
    def results(self) -> str:
        return str(Path(self.working_dir) / "results")

    @computed_field
    @property
    def logs(self) -> str:
        return str(Path(self.working_dir) / "logs")

    @computed_field
    @property
    def qml_updater(self) -> str:
        if self.xml_updater_path:
            return self.xml_updater_path
        return str(Path(self.working_dir) / "qml_updater")


class AuthenticationSettings(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    certificate: str | None = None
    type: str = "none"
    token: str | dict[str, str] | None = None
    token_url: str | None = None
    client_id: str | None = None
    client_secret: str | None = None
    grant_type: str = "client_credentials"
    scope: list[str] = Field(default_factory=list)

    def resolved_token(self, env: str) -> str | None:
        if isinstance(self.token, str):
            return self.token or None
        if isinstance(self.token, dict):
            return self.token.get(env) or None
        return None


class ApiClientSettings(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    port: int
    host: str | None = None
    scope: str = "_default"
    collection: str = "_default"
    authentication: AuthenticationSettings = Field(default_factory=AuthenticationSettings)
    environment: dict[str, str] = Field(default_factory=dict)
    proxies: dict[str, str] = Field(default_factory=dict)
    env: str = "preprod"

    @property
    def resolved_host(self) -> str:
        if self.host:
            return self.host
        try:
            return self.environment[self.env]
        except KeyError as exc:
            raise ConfigError(f"Environment '{self.env}' not found in environment mapping.") from exc

    def with_shared_defaults(
        self,
        *,
        env: str,
        environment: dict[str, str],
        proxies: dict[str, str],
        authentication: AuthenticationSettings,
    ) -> "ApiClientSettings":
        return self.model_copy(
            update={
                "env": env,
                "environment": self.environment or environment,
                "proxies": self.proxies or proxies,
                "authentication": self.authentication
                if self.authentication.type != "none"
                else authentication,
            }
        )


class PyrdsApiSettings(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    host: str = "http://localhost"
    port: int = 5000
    api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("api_key", "key"),
    )
    env: str = "preprod"
    pyrds_dir: str | None = None
    xml_updater_path: str | None = ""


class Settings(BaseModel):
    model_config = ConfigDict(
        extra="allow",
        populate_by_name=True,
    )

    pyrds_api: PyrdsApiSettings = Field(
        default_factory=PyrdsApiSettings,
        validation_alias=AliasChoices("pyrds_api", "pyras_api"),
    )
    couch_base_api: ApiClientSettings = Field(
        default_factory=lambda: ApiClientSettings(port=5202)
    )
    psweb_api: ApiClientSettings = Field(default_factory=lambda: ApiClientSettings(port=4100))
    ps_api: ApiClientSettings = Field(default_factory=lambda: ApiClientSettings(port=5202))
    market_data_api: ApiClientSettings = Field(default_factory=lambda: ApiClientSettings(port=9003))
    trade_api: ApiClientSettings = Field(default_factory=lambda: ApiClientSettings(port=5112))
    qml_generator_api: ApiClientSettings = Field(default_factory=lambda: ApiClientSettings(port=7771))
    maps_elib_api: ApiClientSettings = Field(default_factory=lambda: ApiClientSettings(port=5000))
    risk_studio_api: ApiClientSettings = Field(default_factory=lambda: ApiClientSettings(port=4300))
    environment: dict[str, str] = Field(
        default_factory=lambda: {"preprod": "http://localhost"}
    )
    proxies: dict[str, str] = Field(default_factory=dict)

    @computed_field
    @property
    def env(self) -> str:
        return self.pyrds_api.env

    @computed_field
    @property
    def files_path(self) -> FilesPath | None:
        if not self.pyrds_api.pyrds_dir:
            return None
        return FilesPath(
            working_dir=self.pyrds_api.pyrds_dir,
            xml_updater_path=self.pyrds_api.xml_updater_path,
        )

    @property
    def pricing_api(self) -> ApiClientSettings:
        return self.ps_api

    @property
    def trades_api(self) -> ApiClientSettings:
        return self.trade_api

    @classmethod
    def from_config_file(cls, path: str | os.PathLike[str]) -> "Settings":
        config_path = Path(path)
        if not config_path.exists():
            raise ConfigError(f"Config file not found: {config_path}")
        with config_path.open("r", encoding="utf-8") as file_handle:
            payload = json.load(file_handle)
        return cls.model_validate(payload).with_api_defaults()

    @classmethod
    def load(cls, path: str | os.PathLike[str] | None = None) -> "Settings":
        configured_path = path or os.getenv("PYRDS_CONFIG_FILE")
        if configured_path:
            return cls.from_config_file(configured_path)
        if DEFAULT_CONFIG_FILE.exists():
            return cls.from_config_file(DEFAULT_CONFIG_FILE)
        return cls().with_api_defaults()

    def with_api_defaults(self) -> "Settings":
        shared_auth = self.couch_base_api.authentication
        updates = {
            "couch_base_api": self.couch_base_api.with_shared_defaults(
                env=self.env,
                environment=self.environment,
                proxies=self.proxies,
                authentication=shared_auth,
            ),
            "psweb_api": self.psweb_api.with_shared_defaults(
                env=self.env,
                environment=self.environment,
                proxies=self.proxies,
                authentication=shared_auth,
            ),
            "ps_api": self.ps_api.with_shared_defaults(
                env=self.env,
                environment=self.environment,
                proxies=self.proxies,
                authentication=shared_auth,
            ),
            "market_data_api": self.market_data_api.with_shared_defaults(
                env=self.env,
                environment=self.environment,
                proxies=self.proxies,
                authentication=shared_auth,
            ),
            "trade_api": self.trade_api.with_shared_defaults(
                env=self.env,
                environment=self.environment,
                proxies=self.proxies,
                authentication=shared_auth,
            ),
            "qml_generator_api": self.qml_generator_api.with_shared_defaults(
                env=self.env,
                environment=self.environment,
                proxies=self.proxies,
                authentication=shared_auth,
            ),
            "maps_elib_api": self.maps_elib_api.with_shared_defaults(
                env=self.env,
                environment=self.environment,
                proxies=self.proxies,
                authentication=shared_auth,
            ),
            "risk_studio_api": self.risk_studio_api.with_shared_defaults(
                env=self.env,
                environment=self.environment,
                proxies=self.proxies,
                authentication=shared_auth,
            ),
        }
        return self.model_copy(update=updates)
