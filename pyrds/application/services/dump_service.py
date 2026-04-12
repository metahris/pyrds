from __future__ import annotations

import datetime as dt
import json
from os.path import join
from typing import Any, Mapping

from pyrds.application.services.log_context import log_error, log_info
from pyrds.domain.exceptions import DumpError


class DumpService:
    def __init__(self, *, qml_handler: Any, files_path: Any, logger: Any | None = None) -> None:
        self.qml_handler = qml_handler
        self.files_path = files_path
        self.logger = logger

    @staticmethod
    def result_file_name(prefix: str = "result", extension: str = "xml") -> str:
        time_now = dt.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        return f"{prefix}_{time_now}.{extension}"

    def dump_raw_results(self, raw_data: Mapping[str, str], *, file_name: str | None = None) -> str:
        file_name = file_name or self.result_file_name()
        dump_path = join(self.files_path.results, file_name)

        try:
            self.qml_handler.dump_qml(dump_path=dump_path, data=dict(raw_data))
        except Exception as exc:
            raise DumpError(f"Failed to dump raw results to {dump_path}") from exc

        log_info(self.logger, "Raw results dumped", dump_path=dump_path)
        return dump_path

    def dump_errors(self, errors: Mapping[str, Any]) -> list[str]:
        dumped: list[str] = []

        for key, payload in errors.items():
            file_name = f"errors_{key}.json"
            file_path = join(self.files_path.results, file_name)
            try:
                with open(file_path, "w", encoding="utf-8") as file_handle:
                    json.dump(payload, file_handle, ensure_ascii=False, indent=2)
            except Exception as exc:
                raise DumpError(f"Failed to dump errors to {file_path}") from exc
            dumped.append(file_path)

        if dumped:
            log_error(self.logger, "Computation errors dumped", files=dumped)

        return dumped

    def dump_ot_market_data(self, *, qmls: Mapping[str, str], folder_name: str | None = None) -> str:
        folder_name = folder_name or f"ot_mkt_data_{dt.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}"
        dump_path = join(self.files_path.results, folder_name)
        normalized_qmls = {key.replace("|", "-"): value for key, value in qmls.items()}

        try:
            self.qml_handler.dump_qml_concurrent(output_dir=dump_path, data=normalized_qmls)
        except Exception as exc:
            raise DumpError(f"Failed to dump OT market data to {dump_path}") from exc

        log_info(self.logger, "OT market data dumped", dump_path=dump_path)
        return dump_path
