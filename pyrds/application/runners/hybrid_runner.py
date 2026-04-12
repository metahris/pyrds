from __future__ import annotations

from typing import Any

from pyrds.application.runners.base_runner import BaseRunner
from pyrds.application.services.log_context import log_info
from pyrds.domain.ps_request import PsRequest


class HybridRunner(BaseRunner):
    def compute_hybrid(
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
        create_set_params = {"qmlRunner": qml_runner}

        log_info(
            self.logger,
            "Started hybrid pricing",
            runner=self.__class__.__name__,
            qml_runner=qml_runner,
        )

        trade_set_id = self.trades_api.create_set(params=create_set_params)
        request_set_id = self.ps_api.create_set(qml_runner=qml_runner)

        market_data_params = {
            "cartographyName": ps_request.gridPricerTechnicalDetails.cartography,
            "date": ps_request.valuationDate,
            "otCluster": ps_request.gridPricerTechnicalDetails.foCluster,
            "lagInDaysForHistoricMarketDatas": ps_request.lagInDaysForBackprice,
            "useCache": True,
        }
        market_data_set_ids = [self.get_ot_mkt_data_set_id(**market_data_params)]

        market_data_qmls = self.get_mkt_data_qmls()
        custom_market_data_set_id: str | None = None
        if market_data_qmls:
            custom_market_data_set_id = self.market_api.create_set(params=create_set_params)
            self.add_market_data_qml(
                set_id=custom_market_data_set_id,
                mkt_data=market_data_qmls,
                params=create_set_params,
            )
            market_data_set_ids.append(custom_market_data_set_id)

        self.add_set_ids_to_ps_request(
            ps_request=ps_request,
            trade_set_id=trade_set_id,
            market_data_set_id=market_data_set_ids,
            request_set_id=request_set_id,
            use_cache_factory=use_cache_factory,
        )

        instruction_set_qml = self.get_instruction_set_qml(
            verify=True,
            ps_request=ps_request,
        )
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
            params=create_set_params,
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

        log_info(
            self.logger,
            "Finished hybrid pricing",
            runner=self.__class__.__name__,
            qml_runner=qml_runner,
            trade_set_id=trade_set_id,
            request_set_id=request_set_id,
            market_data_set_ids=market_data_set_ids,
        )

        return raw_data
