from __future__ import annotations

from typing import Any

from pyrds.application.services.log_context import log_info, log_warning
from pyrds.domain.exceptions import QmlInputNotFoundError, QmlVerificationError


class QmlInputService:
    def __init__(self, *, qml_handler: Any, files_path: Any, logger: Any | None = None) -> None:
        self.qml_handler = qml_handler
        self.files_path = files_path
        self.logger = logger

    @staticmethod
    def adjust_file_name(file_name: str, qml_type: str) -> str:
        if qml_type not in ["fixing", "productDefinition", "stress", "results"]:
            parts = file_name.rsplit("-", 1)
            if len(parts) > 1:
                if parts[1] == "COLLAT":
                    root = parts[0]
                    root_name = root.rsplit("_", 1)[0]
                    file_name = root_name + "|BASE"
                else:
                    file_name = parts[0] + "|BASE"
            else:
                file_name = parts[0]
        return file_name

    def get_market_data_qmls(self, request_set_tags: set[str] | list[str]) -> dict[str, str]:
        data = self.qml_handler.load_qmls(self.files_path.data)
        output: dict[str, str] = {}

        for file_name, meta in data.items():
            data_type = meta["data_type"]
            if data_type in request_set_tags:
                continue
            if data_type in {"stress", "results"}:
                continue

            adjusted_name = self.adjust_file_name(file_name, data_type)
            output[adjusted_name] = meta["raw_data"]

        if not output:
            log_warning(self.logger, "No input market data qmls found", path=self.files_path.data)
        return output

    def get_pricing_params_qml(self) -> str:
        data = self.qml_handler.load_qmls(self.files_path.trade)
        qmls = {
            key: value["raw_data"]
            for key, value in data.items()
            if value["data_type"] == "pricingparams"
        }

        if not qmls:
            log_warning(self.logger, "No pricing params qml found", path=self.files_path.trade)
            return ""

        log_info(self.logger, "Pricing params selected", keys=list(qmls.keys()))
        return qmls[next(iter(qmls))]

    def get_product_qml(self) -> dict[str, str]:
        data = self.qml_handler.load_qmls(self.files_path.trade)
        qmls = {
            key: value["raw_data"]
            for key, value in data.items()
            if value["data_type"] == "product"
        }

        if not qmls:
            log_warning(self.logger, "No product qml found", path=self.files_path.trade)
            return {"product_qml": "", "trade_id": ""}

        trade_id = next(iter(qmls))
        log_info(self.logger, "Product selected", trade_id=trade_id, keys=list(qmls.keys()))
        return {"product_qml": qmls[trade_id], "trade_id": trade_id}

    def get_instruction_set_qml(self, *, verify: bool = False, ps_request: Any | None = None) -> str:
        data = self.qml_handler.load_qmls(self.files_path.data)
        qmls = {
            key: value["raw_data"]
            for key, value in data.items()
            if value["data_type"] == "instructionset"
        }

        instruction_set_qml = ""
        if not qmls:
            log_warning(self.logger, "No instruction set qml found", path=self.files_path.data)
        else:
            log_info(self.logger, "Instruction set selected", keys=list(qmls.keys()))
            instruction_set_qml = qmls[next(iter(qmls))]

        if verify:
            try:
                self.qml_handler.verify_instruction_set_qml(
                    instruction_set_qml=instruction_set_qml,
                    ps_request=ps_request,
                )
            except Exception as exc:
                raise QmlVerificationError("Instruction set qml verification failed.") from exc

        return instruction_set_qml

    def get_request_qml(self) -> str:
        data = self.qml_handler.load_qmls(self.files_path.data)
        qmls = {
            key: value["raw_data"]
            for key, value in data.items()
            if value["data_type"] == "request"
        }

        if not qmls:
            raise QmlInputNotFoundError(f"No request qml found in {self.files_path.data}")

        request_key = next(iter(qmls))
        log_info(self.logger, "Request qml selected", key=request_key)

        try:
            return self.qml_handler.verify_request_qml(request_qml=qmls[request_key])
        except Exception as exc:
            raise QmlVerificationError("Request qml verification failed.") from exc
