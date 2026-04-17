from __future__ import annotations

import datetime as dt
from copy import deepcopy
from os import listdir
from os.path import basename, isdir, join
from typing import Any

from pyrds.application.runners.base_runner import BaseRunner
from pyrds.application.services.log_context import log_error, log_info, log_warning
from pyrds.domain.exceptions import QmlInputNotFoundError, QmlVerificationError
from pyrds.domain.ps_request import PsRequest


class Backtester(BaseRunner):
    @staticmethod
    def adjust_file_name(name: str, carto: str) -> str:
        if not carto:
            return name

        token = f"_{carto}"
        index = name.find(token)
        if index == -1:
            return name

        prefix = name[:index]
        suffix = name[index + 1 :]
        return f"{prefix}|{suffix}"

    @staticmethod
    def result_file_name(folder_name: str) -> str:
        time_now = dt.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        return f"{folder_name}_backtest_{time_now}.xml"

    @staticmethod
    def list_folders(path: str) -> list[str]:
        return sorted([name for name in listdir(path) if isdir(join(path, name))])

    def get_mkt_data_qmls_for_path(self, folder_path: str, *, carto: str) -> dict[str, str]:
        data = self.qml_handler.load_qmls(folder_path)
        market_data_qmls: dict[str, str] = {}
        folder_carto = basename(folder_path)

        for name, value in data.items():
            if value["data_type"] in self.request_set_tags:
                continue
            if value["data_type"] == "results":
                continue

            adjusted_name = self.adjust_file_name(name=name, carto=carto)
            if adjusted_name == name and folder_carto != carto:
                adjusted_name = self.adjust_file_name(name=name, carto=folder_carto)
            market_data_qmls[adjusted_name] = value["raw_data"]

        if not market_data_qmls:
            log_warning(self.logger, "No input market data qmls found", folder_path=folder_path)

        return market_data_qmls

    def get_instruction_set_qml_for_path(self, folder_path: str) -> str:
        data = self.qml_handler.load_qmls(folder_path)
        qml_dict = {
            key: value["raw_data"]
            for key, value in data.items()
            if value["data_type"] == "instructionset"
        }

        if not qml_dict:
            log_warning(self.logger, "No instruction set qml found in input qmls", folder_path=folder_path)
            return ""

        key = next(iter(qml_dict))
        log_info(self.logger, "Instruction set used", folder_path=folder_path, key=key)
        return qml_dict[key]

    def get_request_qml_for_path(self, folder_path: str) -> str:
        data = self.qml_handler.load_qmls(folder_path)
        qml_dict = {
            key: value["raw_data"]
            for key, value in data.items()
            if value["data_type"] == "request"
        }

        if not qml_dict:
            raise QmlInputNotFoundError(f"No request qml found in {folder_path}")

        key = next(iter(qml_dict))
        log_info(self.logger, "Request qml used", folder_path=folder_path, key=key)

        try:
            return self.qml_handler.verify_request_qml(request_qml=qml_dict[key])
        except Exception as exc:
            raise QmlVerificationError("Request qml verification failed.") from exc

    def get_backtest_data(self, *, carto: str) -> dict[str, Any]:
        folder_names = self.list_folders(self.files_path.data)
        folder_paths = {name: join(self.files_path.data, name) for name in folder_names}

        hist_mkt_data = {
            name: self.get_mkt_data_qmls_for_path(path, carto=carto)
            for name, path in folder_paths.items()
        }
        requests = {
            name: self.get_request_qml_for_path(path)
            for name, path in folder_paths.items()
        }
        instruction_sets = {
            name: self.get_instruction_set_qml_for_path(path)
            for name, path in folder_paths.items()
        }

        return {
            "hist_mkt_data": hist_mkt_data,
            "product": self.get_product_qml(),
            "pricing_params": self.get_pricing_params_qmls(),
            "request": requests,
            "instruction_set": instruction_sets,
        }

    @staticmethod
    def add_valdate_to_ps_request(valdate: str, ps_request: PsRequest) -> None:
        ps_request.valuationDate = valdate

    async def backtest(
        self,
        ps_request: PsRequest,
        *,
        carto: str,
        use_cache_factory: Any | None = None,
        dump: bool = True,
        return_result: bool = False,
    ) -> dict[str, str]:
        qml_runner = self.require_non_empty_str(
            ps_request.gridPricerTechnicalDetails.qmlRunner,
            "ps_request.gridPricerTechnicalDetails.qmlRunner",
        )
        params = {"qmlRunner": qml_runner}

        log_info(
            self.logger,
            "Started backtest",
            runner=self.__class__.__name__,
            qml_runner=qml_runner,
            carto=carto,
        )

        backtest_data = self.get_backtest_data(carto=carto)
        hist_mkt_data = backtest_data["hist_mkt_data"]
        product = backtest_data["product"]
        pricing_params = backtest_data["pricing_params"]
        requests = backtest_data["request"]
        instruction_sets = backtest_data["instruction_set"]

        market_data_sets: dict[str, str] = {}
        for name, market_data in hist_mkt_data.items():
            market_data_set_id = self.market_api.create_set(params=params)
            self.add_market_data_qml(
                set_id=market_data_set_id,
                params=params,
                mkt_data=market_data,
            )
            market_data_sets[name] = market_data_set_id

        request_sets: dict[str, dict[str, str]] = {}
        for name, request_qml in requests.items():
            request_set_id = self.ps_api.create_set(qml_runner=qml_runner)
            instruction_set_qml = instruction_sets[name]
            valdate = self.qml_handler.get_valdate_from_price_instruction(instruction_set_qml)

            self.add_request_qml(
                set_id=request_set_id,
                request_qml=request_qml,
                instruction_set_qml=instruction_set_qml,
                qml_runner=qml_runner,
            )

            request_sets[name] = {"set_id": request_set_id, "valdate": valdate}

        trade_id = self.require_non_empty_str(product.get("trade_id"), "trade_id")
        product_qml = self.require_non_empty_str(product.get("product_qml"), "product_qml")
        trade_set_id = self.trades_api.create_set(params=params)

        self.add_trade_qml(
            set_id=trade_set_id,
            trade_id=trade_id,
            product_qml=product_qml,
            pricing_params_qml=pricing_params,
            params=params,
        )

        priceable: list[dict[str, Any]] = []
        ordered_names: list[str] = []
        for name, market_data_set_id in market_data_sets.items():
            ps_request_copy = deepcopy(ps_request)
            self.add_valdate_to_ps_request(
                ps_request=ps_request_copy,
                valdate=request_sets[name]["valdate"],
            )
            self.add_set_ids_to_ps_request(
                ps_request=ps_request_copy,
                market_data_set_id=market_data_set_id,
                trade_set_id=trade_set_id,
                request_set_id=request_sets[name]["set_id"],
                use_cache_factory=use_cache_factory,
            )

            priceable.append(self.model_to_payload(ps_request_copy))
            ordered_names.append(name)

        backtest_results = await self._compute_async(priceable=priceable, fail_on_any_error=False)

        result: dict[str, str] = {}
        for name, response in zip(ordered_names, backtest_results.values()):
            try:
                raw_data = self.get_raw_data(response)
                if return_result:
                    result.update(raw_data)
                if dump:
                    self.dump_raw_results(raw_data, file_name=self.result_file_name(folder_name=name))
            except Exception as exc:
                log_error(self.logger, "Backtest item failed", folder_name=name, error=str(exc))
                continue

        log_info(
            self.logger,
            "Finished backtest",
            runner=self.__class__.__name__,
            qml_runner=qml_runner,
            carto=carto,
            scenarios=len(ordered_names),
        )
        return result
