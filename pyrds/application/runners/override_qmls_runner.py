from __future__ import annotations

import copy
import datetime as dt
from os import makedirs
from os.path import join, splitext
from typing import Any

import pandas as pd

from pyrds.application.runners.base_runner import BaseRunner
from pyrds.application.services.log_context import log_info
from pyrds.domain.ps_request import PsRequest


def change_file_name_ext(*, file_path: str, ext: str) -> str:
    root, _ = splitext(file_path)
    return f"{root}.{ext.lstrip('.')}"


class OverrideQmlsRunner(BaseRunner):
    @staticmethod
    def result_file_name(_id: str) -> str:
        time_now = dt.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        return f"{_id}_override_{time_now}.xml"

    def override_mkt_data(
        self,
        *,
        market_data_set_id: str,
        data: dict[str, Any],
        ps_request: PsRequest,
    ) -> str:
        params = {"qmlRunner": ps_request.gridPricerTechnicalDetails.qmlRunner}
        keys = [str(key) for key in self.market_api.get_mkt_data_keys(set_id=market_data_set_id)]
        overridden_keys: set[str] = set()
        new_set_id = self.market_api.create_set(params=params)

        for group_key, entries in data.items():
            if group_key == "ALL":
                for entry in entries:
                    base_file_name = entry["base_file_name"]
                    if base_file_name not in keys:
                        raise ValueError(f"{base_file_name} does not exist in market data set {keys}")
                    new_file_name = entry["new_file_name"]
                    qml = self.qml_handler.load_qml(join(self.files_path.data, f"{new_file_name}.xml"))
                    self.add_market_data_qml(
                        set_id=new_set_id,
                        market_data_id=base_file_name,
                        market_data_qml=qml,
                        params=params,
                    )
                    overridden_keys.add(base_file_name)
                continue

            for entry in entries:
                file_name = entry["file_name"]
                if file_name not in keys:
                    raise ValueError(f"{file_name} does not exist in market data set {keys}")
                content = self.market_api.get_mkt_data_content(set_id=market_data_set_id, key=file_name)
                qml = self.qml_handler.update_block_in_qml(
                    data_id=file_name,
                    block=entry["value"],
                    qml=content,
                )
                self.add_market_data_qml(
                    set_id=new_set_id,
                    market_data_id=file_name,
                    market_data_qml=qml,
                    params=params,
                )
                overridden_keys.add(file_name)

        for key in keys:
            if key in overridden_keys:
                continue
            qml = self.market_api.get_mkt_data_content(set_id=market_data_set_id, key=key)
            self.add_market_data_qml(
                set_id=new_set_id,
                market_data_id=key,
                market_data_qml=qml,
                params=params,
            )

        log_info(self.logger, "Market data overridden", source_set_id=market_data_set_id, new_set_id=new_set_id)
        return new_set_id

    async def override_trades(
        self,
        *,
        trade_set_id: str,
        _id: str,
        ps_request: PsRequest,
        product_block: str | None = None,
        pricingparams_block: str | None = None,
    ) -> str:
        params = {"qmlRunner": ps_request.gridPricerTechnicalDetails.qmlRunner}
        new_set_id = self.trades_api.create_set(params=params)
        trade_ids = [str(trade_id) for trade_id in self.trades_api.get_trades_in_set(set_id=trade_set_id)]
        trade_contents = await self.trades_api.get_specific_trade_content_async(
            set_id=trade_set_id,
            trade_ids=trade_ids,
            fail_on_any_error=True,
        )

        qml_updater_run_id = self.result_file_name(_id=_id)
        makedirs(join(self.files_path.qml_updater, qml_updater_run_id), exist_ok=True)

        for trade_id, payload in trade_contents.items():
            product_qml = payload.get("qml_product") or payload.get("productQml") or payload.get("product_qml") or ""
            pricing_qml = (
                payload.get("qml_pricing_params")
                or payload.get("pricingParamsQml")
                or payload.get("pricing_params_qml")
                or ""
            )

            if pricingparams_block and pricing_qml:
                pricing_qml = self.qml_handler.update_block_in_qml(
                    qml=pricing_qml,
                    block=pricingparams_block,
                    data_id=f"pricingparams_{trade_id}",
                )

            if product_block and product_qml:
                product_qml = self.qml_handler.update_block_in_qml(
                    qml=product_qml,
                    block=product_block,
                    data_id=f"product_{trade_id}",
                )

            self.add_trade_qml(
                set_id=new_set_id,
                trade_id=trade_id,
                product_qml=product_qml,
                pricing_params_qml=pricing_qml,
                params=params,
            )

        log_info(self.logger, "Trades overridden", source_set_id=trade_set_id, new_set_id=new_set_id)
        return new_set_id

    def get_mkt_data_qmls_for_path(self, file_path: str) -> dict[str, str]:
        data = self.qml_handler.load_qmls(join(self.files_path.data, file_path))
        qmls = {
            self.adjust_file_name(key, value["data_type"]): value["raw_data"]
            for key, value in data.items()
            if value["data_type"] not in self.request_set_tags
        }
        if not qmls:
            self.logger.warning("no input market data qmls found.")
        return qmls

    def get_override_data(self) -> dict[str, Any]:
        names = self._list_data_folders()
        return {
            "mkt_data": {
                name: self.get_mkt_data_qmls_for_path(name)
                for name in names
            }
        }

    async def compute_override_qml_ot_async(
        self,
        *,
        ps_request: PsRequest,
        override_qml: str,
    ) -> dict[str, Any]:
        result_file_name = change_file_name_ext(
            file_path=self.result_file_name(_id="results"),
            ext="xlsx",
        )
        override_qml_str = self.qml_handler.load_qml(join(self.files_path.data, f"{override_qml}.xml"))
        override_data = self.qml_handler.get_override_qml_values(qml=override_qml_str)

        base_response = self._compute(body=self.model_to_payload(ps_request))
        trade_set_id = self.get_trade_set_id_from_response(base_response)
        market_data_set_id = self.get_mkt_data_set_id_from_response(base_response)

        priceable_by_key: dict[str, dict[str, Any]] = {}
        for key, value in override_data.items():
            scenario_market_data_set_id = market_data_set_id
            scenario_trade_set_id = trade_set_id
            request_set_id: str | None = None

            if value.get("marketdata"):
                scenario_market_data_set_id = self.override_mkt_data(
                    market_data_set_id=market_data_set_id,
                    data=value["marketdata"],
                    ps_request=ps_request,
                )

            if value.get("product") or value.get("pricingparams"):
                scenario_trade_set_id = await self.override_trades(
                    trade_set_id=trade_set_id,
                    product_block=value.get("product"),
                    pricingparams_block=value.get("pricingparams"),
                    _id=key,
                    ps_request=ps_request,
                )

            if value.get("request") or value.get("instructionset"):
                instruction_set_qml = self.get_instruction_set_qml(verify=True, ps_request=ps_request)
                request_qml = self.get_request_qml()
                request_set_id = self.ps_api.create_set(
                    qml_runner=ps_request.gridPricerTechnicalDetails.qmlRunner
                )
                if value.get("instructionset"):
                    instruction_set_qml = self.override_instructionset(
                        value=value["instructionset"],
                        qml=instruction_set_qml,
                    )
                self.add_request_qml(
                    set_id=request_set_id,
                    instruction_set_qml=instruction_set_qml,
                    request_qml=request_qml,
                    qml_runner=ps_request.gridPricerTechnicalDetails.qmlRunner,
                )

            ps_request_copy = copy.deepcopy(ps_request)
            self.add_set_ids_to_ps_request(
                ps_request=ps_request_copy,
                market_data_set_id=scenario_market_data_set_id,
                trade_set_id=scenario_trade_set_id,
                request_set_id=request_set_id,
            )
            priceable_by_key[key] = self.model_to_payload(ps_request_copy)

        responses = await self._compute_async(
            priceable=list(priceable_by_key.values()),
            fail_on_any_error=False,
        )
        raw_results = [self.get_raw_data(value) for value in responses.values()]
        raw_results.append(self.get_raw_data(base_response))

        scenario_keys = list(priceable_by_key.keys()) + ["base_request"]
        excel_results = {
            key: self._summarize_raw_result(raw_result)
            for key, raw_result in zip(scenario_keys, raw_results)
        }

        dump_path = join(self.files_path.results, result_file_name)
        with pd.ExcelWriter(dump_path, engine="openpyxl") as writer:
            for sheet, items in excel_results.items():
                df = pd.DataFrame(
                    [
                        {
                            "ot_id": item_key,
                            "total": value["price"],
                            "currency": value["currency"],
                            "duration": value["duration"],
                        }
                        for item_key, value in items.items()
                    ]
                )
                df.to_excel(writer, sheet_name=str(sheet)[:31], index=False)

        log_info(self.logger, "Override OT excel dumped", dump_path=dump_path)
        return excel_results

    def override_instructionset(self, *, qml: str, value: dict[str, Any]) -> str:
        if value.get("xpath"):
            return self.qml_handler.override_in_xpath(qml=qml, overrides=[value["xpath"]])
        block = value.get("block") or value.get("value")
        if not block:
            return qml
        return self.qml_handler.update_block_in_qml(
            data_id="instructionset",
            block=block,
            qml=qml,
        )

    async def compute_override_full_qml_async(
        self,
        *,
        ps_request: PsRequest,
        dump: bool = True,
    ) -> dict[str, dict[str, Any]]:
        params = {"qmlRunner": ps_request.gridPricerTechnicalDetails.qmlRunner}
        market_data = self.get_override_data()["mkt_data"]
        trade_set_id = self.trades_api.create_set(params=params)
        request_set_id = self.ps_api.create_set(qml_runner=ps_request.gridPricerTechnicalDetails.qmlRunner)

        market_data_sets: dict[str, str] = {}
        for key, qmls in market_data.items():
            market_data_set_id = self.market_api.create_set(params=params)
            self.add_market_data_qml(set_id=market_data_set_id, mkt_data=qmls, params=params)
            market_data_sets[key] = market_data_set_id

        instruction_set_qml = self.get_instruction_set_qml(verify=True, ps_request=ps_request)
        request_qml = self.get_request_qml()
        pricing_params_qml = self.get_pricing_params_qmls()
        product_qml_data = self.get_product_qml()
        trade_id = self.require_non_empty_str(product_qml_data.get("trade_id"), "trade_id")
        product_qml = self.require_non_empty_str(product_qml_data.get("product_qml"), "product_qml")

        self.add_trade_qml(
            set_id=trade_set_id,
            trade_id=trade_id,
            product_qml=product_qml,
            pricing_params_qml=pricing_params_qml,
            params=params,
        )
        self.add_request_qml(
            set_id=request_set_id,
            instruction_set_qml=instruction_set_qml,
            request_qml=request_qml,
            qml_runner=ps_request.gridPricerTechnicalDetails.qmlRunner,
        )

        priceable: list[dict[str, Any]] = []
        ordered_keys: list[str] = []
        for key, market_data_set_id in market_data_sets.items():
            ps_request_copy = copy.deepcopy(ps_request)
            self.add_set_ids_to_ps_request(
                ps_request=ps_request_copy,
                market_data_set_id=market_data_set_id,
                trade_set_id=trade_set_id,
                request_set_id=request_set_id,
            )
            priceable.append(self.model_to_payload(ps_request_copy))
            ordered_keys.append(key)

        responses = await self._compute_async(priceable=priceable, fail_on_any_error=False)
        raw_by_key: dict[str, dict[str, str]] = {}
        for key, response in zip(ordered_keys, responses.values()):
            try:
                raw_data = self.get_raw_data(response)
                if dump:
                    self.dump_raw_results(raw_data, file_name=self.result_file_name(_id=key))
                raw_by_key[key] = raw_data
            except Exception as exc:
                self.logger.error(exc)

        flattened = {
            key: list(value.values())[0]
            for key, value in raw_by_key.items()
            if value
        }
        summarized = {
            key: self._summarize_single_qml(qml)
            for key, qml in flattened.items()
        }

        if dump:
            result_file_name = change_file_name_ext(file_path=self.result_file_name(_id="df"), ext="xlsx")
            pd.DataFrame.from_dict(summarized, orient="index").to_excel(
                join(self.files_path.results, result_file_name)
            )
        return summarized

    def _summarize_single_qml(self, qml: str) -> dict[str, Any]:
        parsed = self.qml_handler.parse_result_price(qml)
        return {
            "currency": self.get_ccy_from_response(parsed),
            "price": self.get_total_from_response(parsed),
            "duration": self.qml_handler.get_pricing_duration(qml=qml),
        }

    def _summarize_raw_result(self, raw_data: dict[str, str]) -> dict[str, dict[str, Any]]:
        return {
            key: self._summarize_single_qml(qml)
            for key, qml in raw_data.items()
        }

    def _list_data_folders(self) -> list[str]:
        from os import listdir
        from os.path import isdir

        return sorted(
            name
            for name in listdir(self.files_path.data)
            if isdir(join(self.files_path.data, name))
        )
