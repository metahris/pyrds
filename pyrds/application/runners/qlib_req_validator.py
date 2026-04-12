from __future__ import annotations

import copy
import datetime as dt
from os.path import join
from typing import Any

import pandas as pd

from pyrds.application.runners.base_runner import BaseRunner
from pyrds.application.services.log_context import log_info
from pyrds.domain.ps_request import PsRequest


class QlibReqValidator(BaseRunner):
    @staticmethod
    def result_file_name() -> str:
        time_now = dt.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        return f"test_qlib_dev_{time_now}.xlsx"

    async def qlib_req_validate(
        self,
        *,
        ref_version: str,
        new_version: str,
        ps_request: PsRequest,
        dump_xl: bool = False,
    ) -> dict[str, Any]:
        log_info(
            self.logger,
            "Started qlib regression validation",
            ref_version=ref_version,
            new_version=new_version,
        )

        ps_request_ref = copy.deepcopy(ps_request)
        ps_request_new = copy.deepcopy(ps_request)
        ps_request_ref.gridPricerTechnicalDetails.qlibVersion = ref_version
        ps_request_new.gridPricerTechnicalDetails.qlibVersion = new_version

        responses = await self._compute_async(
            priceable=[
                self.model_to_payload(ps_request_ref),
                self.model_to_payload(ps_request_new),
            ],
            fail_on_any_error=True,
        )
        response_values = list(responses.values())
        result_ref = self.get_raw_data(response_values[0])
        result_new = self.get_raw_data(response_values[1])

        result_ref_dict = self._summarize_raw_results(result_ref)
        result_new_dict = self._summarize_raw_results(result_new)

        df_ref = pd.DataFrame.from_dict(result_ref_dict, orient="index")
        df_new = pd.DataFrame.from_dict(result_new_dict, orient="index")
        df_ref.rename(
            columns={"price": f"price_{ref_version}", "duration": f"duration_{ref_version}"},
            inplace=True,
        )
        df_new.rename(
            columns={"price": f"price_{new_version}", "duration": f"duration_{new_version}"},
            inplace=True,
        )
        df_ref.index = df_ref.index.to_series().str.split("-", n=1).str[0]
        df_new.index = df_new.index.to_series().str.rsplit("-", n=1).str[0]

        merged_df = pd.merge(
            df_ref,
            df_new[[f"price_{new_version}", f"duration_{new_version}"]],
            left_index=True,
            right_index=True,
        )
        merged_df["diff_price"] = merged_df.apply(
            lambda row: self.safe_sub(
                row[f"price_{ref_version}"],
                row[f"price_{new_version}"],
            ),
            axis=1,
        )

        if dump_xl:
            dump_path = join(self.files_path.results, self.result_file_name())
            merged_df.to_excel(dump_path)
            log_info(self.logger, "Qlib regression result dumped", dump_path=dump_path)

        log_info(
            self.logger,
            "Finished qlib regression validation",
            ref_version=ref_version,
            new_version=new_version,
        )
        return merged_df.to_dict()

    def _summarize_raw_results(self, raw_results: dict[str, str]) -> dict[str, dict[str, Any]]:
        output: dict[str, dict[str, Any]] = {}
        for key, qml in raw_results.items():
            parsed = self.qml_handler.parse_result_price(result_qml=qml)
            output[key] = {
                "currency": self.get_ccy_from_response(parsed),
                "price": self.get_total_from_response(parsed),
                "duration": self.qml_handler.get_pricing_duration(qml=qml),
            }
        return output
