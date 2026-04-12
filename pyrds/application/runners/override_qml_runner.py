from __future__ import annotations

import copy
from os.path import join
from typing import Any

import pandas as pd

from pyrds.application.runners.base_runner import BaseRunner
from pyrds.application.services.log_context import log_info
from pyrds.application.services.qml_override_service import QmlOverrideService
from pyrds.domain.exceptions import DumpError, OverrideApplicationError, ValidationError
from pyrds.domain.override_models import OverridePlan, OverrideScenario, OverrideTargetType
from pyrds.domain.ps_request import PsRequest


class OverrideQmlRunner(BaseRunner):
    def __init__(
        self,
        *,
        logger: Any,
        files_path: Any,
        qml_handler: Any,
        ps_api: Any,
        market_api: Any,
        trades_api: Any,
        request_set_tags: set[str] | list[str] | None = None,
    ) -> None:
        super().__init__(
            logger=logger,
            files_path=files_path,
            qml_handler=qml_handler,
            ps_api=ps_api,
            market_api=market_api,
            trades_api=trades_api,
            request_set_tags=request_set_tags,
        )
        self.override_service = QmlOverrideService(files_path=files_path, logger=logger)

    async def compute_override_ot_async(
        self,
        *,
        ps_request: PsRequest,
        override_plan: OverridePlan | dict[str, Any],
        use_cache_factory: Any,
        dump: bool = True,
        dump_excel: bool = True,
    ) -> dict[str, dict[str, Any]]:
        plan = self._normalize_plan(override_plan)
        qml_runner = self.require_non_empty_str(
            ps_request.gridPricerTechnicalDetails.qmlRunner,
            "ps_request.gridPricerTechnicalDetails.qmlRunner",
        )

        log_info(self.logger, "Started OT override pricing", qml_runner=qml_runner)

        base_response = self._compute(body=self.model_to_payload(ps_request))
        base_summary = self._build_summary(response=base_response)
        base_trade_set_id = self.get_trade_set_id_from_response(base_response)
        base_market_data_set_id = self.get_mkt_data_set_id_from_response(base_response)

        results: dict[str, dict[str, Any]] = {"base_request": base_summary}
        for scenario in plan.scenarios:
            results[scenario.scenario_id] = await self._run_ot_scenario(
                scenario=scenario,
                ps_request=ps_request,
                qml_runner=qml_runner,
                base_trade_set_id=base_trade_set_id,
                base_market_data_set_id=base_market_data_set_id,
                use_cache_factory=use_cache_factory,
                dump=dump,
            )

        if dump_excel:
            self._dump_summary_excel(results, prefix="override_ot_summary")

        log_info(self.logger, "Finished OT override pricing", qml_runner=qml_runner)
        return results

    async def compute_override_full_qml_async(
        self,
        *,
        ps_request: PsRequest,
        override_plan: OverridePlan | dict[str, Any],
        use_cache_factory: Any,
        dump: bool = True,
        dump_excel: bool = True,
    ) -> dict[str, dict[str, Any]]:
        plan = self._normalize_plan(override_plan)
        qml_runner = self.require_non_empty_str(
            ps_request.gridPricerTechnicalDetails.qmlRunner,
            "ps_request.gridPricerTechnicalDetails.qmlRunner",
        )

        log_info(self.logger, "Started full QML override pricing", qml_runner=qml_runner)

        results: dict[str, dict[str, Any]] = {}
        for scenario in plan.scenarios:
            results[scenario.scenario_id] = await self._run_full_qml_scenario(
                scenario=scenario,
                ps_request=ps_request,
                qml_runner=qml_runner,
                use_cache_factory=use_cache_factory,
                dump=dump,
            )

        if dump_excel:
            self._dump_summary_excel(results, prefix="override_full_qml_summary")

        log_info(self.logger, "Finished full QML override pricing", qml_runner=qml_runner)
        return results

    async def _run_ot_scenario(
        self,
        *,
        scenario: OverrideScenario,
        ps_request: PsRequest,
        qml_runner: str,
        base_trade_set_id: str,
        base_market_data_set_id: str,
        use_cache_factory: Any,
        dump: bool,
    ) -> dict[str, Any]:
        market_data_set_id = base_market_data_set_id
        trade_set_id = base_trade_set_id
        request_set_id: str | None = None

        if self._has_target_type(scenario, OverrideTargetType.MARKETDATA):
            market_data_set_id = await self._clone_and_override_remote_market_data_set(
                base_set_id=base_market_data_set_id,
                scenario=scenario,
                qml_runner=qml_runner,
            )

        if self._has_target_type(scenario, OverrideTargetType.PRODUCT) or self._has_target_type(
            scenario,
            OverrideTargetType.PRICINGPARAMS,
        ):
            trade_set_id = await self._clone_and_override_remote_trade_set(
                base_set_id=base_trade_set_id,
                scenario=scenario,
                qml_runner=qml_runner,
            )

        if self._has_target_type(scenario, OverrideTargetType.REQUEST) or self._has_target_type(
            scenario,
            OverrideTargetType.INSTRUCTIONSET,
        ):
            request_set_id = self._create_and_fill_request_set(
                scenario=scenario,
                qml_runner=qml_runner,
            )

        scenario_request = copy.deepcopy(ps_request)
        self.add_set_ids_to_ps_request(
            ps_request=scenario_request,
            market_data_set_id=market_data_set_id,
            trade_set_id=trade_set_id,
            request_set_id=request_set_id,
            use_cache_factory=use_cache_factory,
        )

        response = self._compute(body=self.model_to_payload(scenario_request))
        summary = self._build_summary(response=response)

        if dump:
            self._dump_scenario_raw_result(
                scenario_id=scenario.scenario_id,
                raw_data=summary["raw_data"],
            )

        return summary

    async def _run_full_qml_scenario(
        self,
        *,
        scenario: OverrideScenario,
        ps_request: PsRequest,
        qml_runner: str,
        use_cache_factory: Any,
        dump: bool,
    ) -> dict[str, Any]:
        params = {"qmlRunner": qml_runner}
        set_ids = self.create_full_qml_sets(qml_runner=qml_runner)

        market_data_qmls = self.override_service.apply_scenario_to_mapping(
            qml_by_target_id=self.get_mkt_data_qmls(),
            scenario=scenario,
            target_type=OverrideTargetType.MARKETDATA,
        )
        self.add_market_data_qml(
            set_id=set_ids["market_data_set_id"],
            mkt_data=market_data_qmls,
            params=params,
        )

        product_qml_data = self.get_product_qml()
        pricing_params_qml = self.get_pricing_params_qml()
        trade_id = self.require_non_empty_str(product_qml_data.get("trade_id"), "trade_id")
        product_qml = self.require_non_empty_str(product_qml_data.get("product_qml"), "product_qml")

        trade_qmls = {
            trade_id: {"product": product_qml, "pricingparams": pricing_params_qml}
        }
        trade_qmls = self._apply_local_trade_overrides(trade_qmls=trade_qmls, scenario=scenario)

        self.add_trade_qml(
            set_id=set_ids["trade_set_id"],
            trade_id=trade_id,
            product_qml=trade_qmls[trade_id]["product"],
            pricing_params_qml=trade_qmls[trade_id]["pricingparams"],
            params=params,
        )

        request_qml = self.override_service.apply_scenario_to_single_qml(
            qml=self.get_request_qml(),
            scenario=scenario,
            target_type=OverrideTargetType.REQUEST,
        )
        instruction_set_qml = self.override_service.apply_scenario_to_single_qml(
            qml=self.get_instruction_set_qml(verify=True, ps_request=ps_request),
            scenario=scenario,
            target_type=OverrideTargetType.INSTRUCTIONSET,
        )

        self.add_request_qml(
            set_id=set_ids["request_set_id"],
            instruction_set_qml=instruction_set_qml,
            request_qml=request_qml,
            qml_runner=qml_runner,
        )

        scenario_request = copy.deepcopy(ps_request)
        self.add_set_ids_to_ps_request(
            ps_request=scenario_request,
            market_data_set_id=set_ids["market_data_set_id"],
            trade_set_id=set_ids["trade_set_id"],
            request_set_id=set_ids["request_set_id"],
            use_cache_factory=use_cache_factory,
        )

        response = self._compute(body=self.model_to_payload(scenario_request))
        summary = self._build_summary(response=response)

        if dump:
            self._dump_scenario_raw_result(
                scenario_id=scenario.scenario_id,
                raw_data=summary["raw_data"],
            )

        return summary

    async def _clone_and_override_remote_market_data_set(
        self,
        *,
        base_set_id: str,
        scenario: OverrideScenario,
        qml_runner: str,
    ) -> str:
        params = {"qmlRunner": qml_runner}
        new_set_id = self.market_api.create_set(params=params)
        keys = await self.market_api.get_mkt_data_keys_async(set_id=base_set_id)
        qml_by_key = await self.market_api.get_ot_mkt_data_qmls_async(
            set_id=base_set_id,
            fail_on_any_error=True,
        )

        overridden = self.override_service.apply_scenario_to_mapping(
            qml_by_target_id=qml_by_key,
            scenario=scenario,
            target_type=OverrideTargetType.MARKETDATA,
        )

        for key in keys:
            self.market_api.add_qml(
                set_id=new_set_id,
                market_data_id=str(key),
                market_data_qml=overridden[str(key)],
                params=params,
            )

        return new_set_id

    async def _clone_and_override_remote_trade_set(
        self,
        *,
        base_set_id: str,
        scenario: OverrideScenario,
        qml_runner: str,
    ) -> str:
        params = {"qmlRunner": qml_runner}
        new_set_id = self.trades_api.create_set(params=params)
        trade_ids = await self.trades_api.get_trades_in_set_async(set_id=base_set_id)
        trade_contents = await self.trades_api.get_specific_trade_content_async(
            set_id=base_set_id,
            trade_ids=[str(item) for item in trade_ids],
            fail_on_any_error=True,
        )

        trade_qmls: dict[str, dict[str, str]] = {}
        for trade_id, payload in trade_contents.items():
            product_qml = payload.get("qml_product") or payload.get("productQml") or payload.get("product_qml")
            pricing_qml = (
                payload.get("qml_pricing_params")
                or payload.get("pricingParamsQml")
                or payload.get("pricing_params_qml")
            )

            if not isinstance(product_qml, str):
                raise OverrideApplicationError(f"Trade '{trade_id}' is missing product qml.")
            if not isinstance(pricing_qml, str):
                raise OverrideApplicationError(f"Trade '{trade_id}' is missing pricing params qml.")

            trade_qmls[trade_id] = {"product": product_qml, "pricingparams": pricing_qml}

        trade_qmls = self._apply_remote_trade_overrides(trade_qmls=trade_qmls, scenario=scenario)

        for trade_id, qmls in trade_qmls.items():
            self.trades_api.add_qml(
                set_id=new_set_id,
                trade_id=trade_id,
                product_qml=qmls["product"],
                pricing_parameters_qml=qmls["pricingparams"],
                params=params,
            )

        return new_set_id

    def _create_and_fill_request_set(
        self,
        *,
        scenario: OverrideScenario,
        qml_runner: str,
    ) -> str:
        request_set_id = self.ps_api.create_set(qml_runner=qml_runner)
        request_qml = self.override_service.apply_scenario_to_single_qml(
            qml=self.get_request_qml(),
            scenario=scenario,
            target_type=OverrideTargetType.REQUEST,
        )
        instruction_set_qml = self.override_service.apply_scenario_to_single_qml(
            qml=self.get_instruction_set_qml(),
            scenario=scenario,
            target_type=OverrideTargetType.INSTRUCTIONSET,
        )
        self.add_request_qml(
            set_id=request_set_id,
            instruction_set_qml=instruction_set_qml,
            request_qml=request_qml,
            qml_runner=qml_runner,
        )
        return request_set_id

    def _build_summary(self, *, response: dict[str, Any]) -> dict[str, Any]:
        raw_data = self.get_raw_data(response)
        first_qml = next(iter(raw_data.values()))
        first_response = response["responses"][0]

        return {
            "currency": self.response_parser.get_ccy_from_response(first_response),
            "price": self.response_parser.get_total_from_response(first_response),
            "duration": self.qml_handler.get_pricing_duration(qml=first_qml),
            "parsed_result_price": self.qml_handler.parse_result_price(first_qml),
            "raw_data": raw_data,
            "response": response,
        }

    def _dump_scenario_raw_result(self, *, scenario_id: str, raw_data: dict[str, str]) -> str:
        file_name = self.dump_service.result_file_name(prefix=f"{scenario_id}_result", extension="xml")
        return self.dump_raw_results(raw_data, file_name=file_name)

    def _dump_summary_excel(self, results: dict[str, dict[str, Any]], *, prefix: str) -> str:
        rows: list[dict[str, Any]] = []
        for scenario_id, payload in results.items():
            rows.append(
                {
                    "scenario_id": scenario_id,
                    "currency": payload.get("currency"),
                    "price": payload.get("price"),
                    "parsed_result_price": payload.get("parsed_result_price"),
                    "duration": payload.get("duration"),
                }
            )

        file_name = self.dump_service.result_file_name(prefix=prefix, extension="xlsx")
        dump_path = join(self.files_path.results, file_name)
        try:
            pd.DataFrame(rows).to_excel(dump_path, index=False)
        except Exception as exc:
            raise DumpError(f"Failed to write summary excel to {dump_path}") from exc
        return dump_path

    @staticmethod
    def _normalize_plan(plan: OverridePlan | dict[str, Any]) -> OverridePlan:
        if isinstance(plan, OverridePlan):
            return plan
        if isinstance(plan, dict):
            return OverridePlan.model_validate(plan)
        raise ValidationError("override_plan must be OverridePlan or dict.")

    @staticmethod
    def _has_target_type(scenario: OverrideScenario, target_type: OverrideTargetType) -> bool:
        return any(item.target_type == target_type for item in scenario.overrides)

    def _apply_remote_trade_overrides(
        self,
        *,
        trade_qmls: dict[str, dict[str, str]],
        scenario: OverrideScenario,
    ) -> dict[str, dict[str, str]]:
        output = copy.deepcopy(trade_qmls)
        for override in scenario.overrides:
            if override.target_type not in {OverrideTargetType.PRODUCT, OverrideTargetType.PRICINGPARAMS}:
                continue

            field_name = "product" if override.target_type == OverrideTargetType.PRODUCT else "pricingparams"
            target_ids = (
                list(output.keys())
                if override.apply_to_all
                else [self.require_non_empty_str(override.target_id, "override.target_id")]
            )

            for target_id in target_ids:
                if target_id not in output:
                    raise OverrideApplicationError(
                        f"Trade '{target_id}' does not exist for override '{override.name}'."
                    )
                output[target_id][field_name] = self.override_service.apply_override(
                    qml=output[target_id][field_name],
                    override=override,
                )

        return output

    def _apply_local_trade_overrides(
        self,
        *,
        trade_qmls: dict[str, dict[str, str]],
        scenario: OverrideScenario,
    ) -> dict[str, dict[str, str]]:
        return self._apply_remote_trade_overrides(trade_qmls=trade_qmls, scenario=scenario)
