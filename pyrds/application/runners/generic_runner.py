from __future__ import annotations

from typing import Any

from pyrds.application.runners.base_runner import BaseRunner
from pyrds.application.services.log_context import log_info
from pyrds.domain.ps_request import PsRequest


class GenericRunner(BaseRunner):
    def compute_ot(self, ps_request: PsRequest, dump: bool = True) -> dict[str, str]:
        log_info(self.logger, "Started OT pricing", runner=self.__class__.__name__)

        body = self.model_to_payload(ps_request)
        response = self._compute(body=body)
        raw_data = self.get_raw_data(response)

        if dump:
            self.dump_raw_results(raw_data)

        log_info(self.logger, "Finished OT pricing", runner=self.__class__.__name__)
        return raw_data

    def compute_full_qml(
        self,
        ps_request: PsRequest,
        *,
        use_cache_factory: Any,
        dump: bool = True,
    ) -> dict[str, str]:
        qml_runner = self.require_non_empty_str(
            ps_request.gridPricerTechnicalDetails.qmlRunner,
            "ps_request.gridPricerTechnicalDetails.qmlRunner",
        )

        log_info(
            self.logger,
            "Started full QML pricing",
            runner=self.__class__.__name__,
            qml_runner=qml_runner,
        )

        set_ids = self.create_full_qml_sets(qml_runner=qml_runner)
        market_data_set_id = set_ids["market_data_set_id"]
        trade_set_id = set_ids["trade_set_id"]
        request_set_id = set_ids["request_set_id"]

        self.add_set_ids_to_ps_request(
            ps_request=ps_request,
            market_data_set_id=market_data_set_id,
            trade_set_id=trade_set_id,
            request_set_id=request_set_id,
            use_cache_factory=use_cache_factory,
        )

        market_data_qmls = self.get_mkt_data_qmls()
        instruction_set_qml = self.get_instruction_set_qml(verify=True, ps_request=ps_request)
        request_qml = self.get_request_qml()
        pricing_params_qml = self.get_pricing_params_qml()
        product_qml_data = self.get_product_qml()

        trade_id = self.require_non_empty_str(product_qml_data.get("trade_id"), "trade_id")
        product_qml = self.require_non_empty_str(product_qml_data.get("product_qml"), "product_qml")

        params = self.build_set_access_params(qml_runner=qml_runner)

        self.add_market_data_qml(
            set_id=market_data_set_id,
            mkt_data=market_data_qmls,
            params=params,
        )

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

        body = self.model_to_payload(ps_request)
        response = self._compute(body=body)
        raw_data = self.get_raw_data(response)

        if dump:
            self.dump_raw_results(raw_data)

        log_info(
            self.logger,
            "Finished full QML pricing",
            runner=self.__class__.__name__,
            qml_runner=qml_runner,
            market_data_set_id=market_data_set_id,
            trade_set_id=trade_set_id,
            request_set_id=request_set_id,
        )

        return raw_data

    def compute_custom_mkt_data(
        self,
        ps_request: PsRequest,
        *,
        use_cache_factory: Any | None = None,
        dump: bool = True,
    ) -> dict[str, str]:
        qml_runner = self.require_non_empty_str(
            ps_request.gridPricerTechnicalDetails.qmlRunner,
            "ps_request.gridPricerTechnicalDetails.qmlRunner",
        )
        result_file_name = self.result_file_name()
        params = self.build_set_access_params(qml_runner=qml_runner)

        log_info(
            self.logger,
            "Started custom market data pricing",
            runner=self.__class__.__name__,
            qml_runner=qml_runner,
        )

        first_response = self._compute(body=self.model_to_payload(ps_request))

        market_data_set_id = self.market_api.create_set(params=params)
        request_set_id = self.ps_api.create_set(qml_runner=qml_runner)

        market_data_qmls = self.get_mkt_data_qmls()
        instruction_set_qml = self.get_instruction_set_qml(
            verify=True,
            ps_request=ps_request,
        )
        request_qml = self.get_request_qml()

        self.add_market_data_qml(
            set_id=market_data_set_id,
            mkt_data=market_data_qmls,
            params=params,
        )
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
            use_cache_factory=use_cache_factory,
        )

        second_response = self._compute(body=self.model_to_payload(ps_request))
        raw_data = self.get_raw_data(second_response)

        if dump:
            self.dump_raw_results(raw_data, file_name=result_file_name)

        log_info(
            self.logger,
            "Finished custom market data pricing",
            runner=self.__class__.__name__,
            qml_runner=qml_runner,
            market_data_set_id=market_data_set_id,
            ot_market_data_set_id=ot_market_data_set_id,
            request_set_id=request_set_id,
        )

        return raw_data
