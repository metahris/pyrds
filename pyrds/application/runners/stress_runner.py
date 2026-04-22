from __future__ import annotations

from typing import Any

from pyrds.application.runners.base_runner import BaseRunner
from pyrds.application.services.log_context import log_info
from pyrds.domain.exceptions import QmlInputNotFoundError
from pyrds.domain.ps_request import PsRequest
from pyrds.domain.stress_models import StressRequest


class StressRunner(BaseRunner):
    def update_request_with_mult_add_shift_scenarios(
        self,
        *,
        request_qml: str,
        stresses_request: StressRequest,
    ) -> str:
        return self.qml_handler.update_request_with_mult_add_shift_scenarios(
            request_qml=request_qml,
            stresses_request=stresses_request,
        )

    def verify_stress_request(self, *, qml_data: dict[str, str], stresses_request: StressRequest) -> None:
        fields_list = [field.name for field in stresses_request.stresses]
        missing = [field for field in fields_list if field not in qml_data]
        if missing:
            raise QmlInputNotFoundError(
                f"Could not find qml for stress field(s) specified in request: {missing}"
            )

    def get_mkt_data_qmls(self) -> dict[str, str]:
        data = self.qml_handler.load_qmls(self.files_path.data)
        market_data_qmls: dict[str, str] = {}

        for key, value in data.items():
            data_type = value["data_type"]
            if data_type in self.request_set_tags:
                continue
            if data_type == "results":
                continue
            adjusted_key = self.adjust_file_name(key, data_type)
            market_data_qmls[adjusted_key] = value["raw_data"]

        if not market_data_qmls:
            self.logger.warning("no input market data qmls found.")
        return market_data_qmls

    def compute_stress_full_qml(
        self,
        ps_request: PsRequest,
        stresses_request: StressRequest,
        *,
        dump: bool = True,
    ) -> dict[str, str]:
        qml_runner = self.require_non_empty_str(
            ps_request.gridPricerTechnicalDetails.qmlRunner,
            "ps_request.gridPricerTechnicalDetails.qmlRunner",
        )
        result_file_name = self.result_file_name()
        params = self.build_set_access_params(qml_runner=qml_runner)

        log_info(self.logger, "Started stress full QML pricing", qml_runner=qml_runner)

        set_ids = self.create_full_qml_sets(qml_runner=qml_runner)
        market_data_set_id = set_ids["market_data_set_id"]
        trade_set_id = set_ids["trade_set_id"]
        request_set_id = set_ids["request_set_id"]

        self.add_set_ids_to_ps_request(
            ps_request=ps_request,
            market_data_set_id=market_data_set_id,
            trade_set_id=trade_set_id,
            request_set_id=request_set_id,
        )

        market_data_qmls = self.get_mkt_data_qmls()
        self.verify_stress_request(qml_data=market_data_qmls, stresses_request=stresses_request)

        instruction_set_qml = self.get_instruction_set_qml(verify=True, ps_request=ps_request)
        request_qml = self.update_request_with_mult_add_shift_scenarios(
            request_qml=self.get_request_qml(),
            stresses_request=stresses_request,
        )
        pricing_params_qml = self.get_pricing_params_qmls()
        product_qml_data = self.get_product_qml()
        trade_id = self.require_non_empty_str(product_qml_data.get("trade_id"), "trade_id")
        product_qml = self.require_non_empty_str(product_qml_data.get("product_qml"), "product_qml")

        self.add_market_data_qml(set_id=market_data_set_id, mkt_data=market_data_qmls, params=params)
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
            qml_runner=qml_runner,
        )

        response = self._compute(body=self.model_to_payload(ps_request))
        raw_data = self.get_raw_data(response)

        if dump:
            self.dump_raw_results(raw_data, file_name=result_file_name)

        log_info(self.logger, "Finished stress full QML pricing", qml_runner=qml_runner)
        return raw_data

    def compute_stress_ot(
        self,
        ps_request: PsRequest,
        stresses_request: StressRequest,
        *,
        dump: bool = True,
    ) -> dict[str, str]:
        qml_runner = self.require_non_empty_str(
            ps_request.gridPricerTechnicalDetails.qmlRunner,
            "ps_request.gridPricerTechnicalDetails.qmlRunner",
        )
        result_file_name = self.result_file_name()
        params = self.build_set_access_params(qml_runner=qml_runner)

        log_info(self.logger, "Started stress OT pricing", qml_runner=qml_runner)

        first_response = self._compute(body=self.model_to_payload(ps_request))
        market_data_set_id = self.market_api.create_set(params=params)
        request_set_id = self.ps_api.create_set(qml_runner=qml_runner)

        market_data_qmls = self.get_mkt_data_qmls()
        self.verify_stress_request(qml_data=market_data_qmls, stresses_request=stresses_request)

        instruction_set_qml = self.get_instruction_set_qml(verify=True, ps_request=ps_request)
        request_qml = self.update_request_with_mult_add_shift_scenarios(
            request_qml=self.get_request_qml(),
            stresses_request=stresses_request,
        )

        self.add_market_data_qml(set_id=market_data_set_id, mkt_data=market_data_qmls, params=params)
        self.add_request_qml(
            set_id=request_set_id,
            instruction_set_qml=instruction_set_qml,
            request_qml=request_qml,
            qml_runner=qml_runner,
        )

        ot_market_data_set_id = self.get_mkt_data_set_id_from_response(first_response)
        self.add_set_ids_to_ps_request(
            ps_request=ps_request,
            market_data_set_id=[market_data_set_id, ot_market_data_set_id],
            request_set_id=request_set_id,
        )

        second_response = self._compute(body=self.model_to_payload(ps_request))
        raw_data = self.get_raw_data(second_response)

        if dump:
            self.dump_raw_results(raw_data, file_name=result_file_name)

        log_info(self.logger, "Finished stress OT pricing", qml_runner=qml_runner)
        return raw_data
