# API Payloads

Swagger is intentionally kept clean. Copy/paste examples live under `examples/api_payloads`.

The public computing API uses a small wrapper around `PsRequest`:

```json
{
  "dir": "working_dir",
  "ps_request": {}
}
```

`dir` is an alias for `pyrds_dir`. It is the working directory name under the root configured in:

```text
pyrds/infrastructure/config/config.json -> pyrds_api.pyrds_dir
```

For example, if the config root is:

```json
{
  "pyrds_api": {
    "pyrds_dir": "/Users/me/pyrds_dir"
  }
}
```

and the payload contains:

```json
{
  "dir": "working_dir"
}
```

then Pyrds resolves the working directory as:

```text
/Users/me/pyrds_dir/working_dir
```

## Endpoints

Create the working directory:

```text
POST /working-dir
```

Generic computing:

```text
POST /computing/generic/ot
POST /computing/generic/full-qml
POST /computing/generic/custom-market-data
POST /computing/generic/hybrid
```

Backtest:

```text
POST /backtest/full-qml
```

Stress:

```text
POST /stress/full-qml
POST /stress/ot
```

Qlib validation:

```text
POST /qlib/regression-validation
```

Overrides:

```text
POST /overrides/ot
POST /overrides/full-qml
```

Result parsing:

```text
POST /results/parse/price
POST /results/parse/deltair
POST /results/parse/vegair
POST /results/parse/calibration
POST /results/parse/duration
POST /results/parse/func-duration
```

Result parsing accepts either raw QML:

```json
{
  "inline_xml": "<results>...</results>"
}
```

or a result file already present under `results` in a Pyrds working dir:

```json
{
  "dir": "working_dir",
  "file_name": "result_trade.xml",
  "dump_excel": true
}
```

To parse every XML file under the working dir `results` folder for the selected parser, use `file_name: "all"`:

```json
{
  "dir": "working_dir",
  "file_name": "all",
  "dump_excel": true
}
```

For stress examples, the JSON keeps a compact `stress` block. Convert it to the runner model with:

```python
from pyrds import build_stress_request

stress_request = build_stress_request(payload["stress"])
```

The resulting `StressRequest` contains one scenario per mult/add combination and is injected into the request QML as `shiftScenariosWithMultAdd`.

The matching `<stress>` QML file must also be present in `inputs/data`. The file stem is uploaded as the market data key, so `stress_name: "BERM_STRESS"` requires:

```text
inputs/data/BERM_STRESS.xml -> BERM_STRESS
```

Detailed stress payload rules are documented in `docs/stress_payloads.md`.

## Compatibility Notes

The current `PsRequest` model allows extra fields, so existing payloads with fields not explicitly modeled are accepted.

Use `foCluster` in new payloads. Existing examples sometimes use `focCluster`; because extra fields are allowed, it will not be rejected, but runner logic reads `gridPricerTechnicalDetails.foCluster` for market-data lookup.

Use `qmlRunner` exactly. The API passes it to remote set creation.

## Example Files

Generic/API-ready examples:

- `examples/api_payloads/create_working_dir.json`
- `examples/api_payloads/generic_ot_id.json`
- `examples/api_payloads/generic_existing_set_ids.json`
- `examples/api_payloads/generic_full_qml.json`
- `examples/api_payloads/generic_option_ny_mtm.json`
- `examples/api_payloads/generic_sne_mtm_custom.json`
- `examples/api_payloads/generic_hybrid.json`
- `examples/api_payloads/backprice_full_qml.json`
- `examples/api_payloads/backtest_full_qml.json`
- `examples/api_payloads/stress_full_qml.json`
- `examples/api_payloads/qlib_reg_validator.json`
- `examples/api_payloads/parse_result_inline_price.json`
- `examples/api_payloads/parse_result_file_price.json`
- `examples/api_payloads/parse_result_file_deltair.json`
- `examples/api_payloads/parse_result_file_vegair.json`
- `examples/api_payloads/parse_result_file_calibration.json`
- `examples/api_payloads/overrides/`

Detailed override documentation is in `docs/overrides.md`.

## Existing Set IDs

If a user already has remote set ids, use:

```text
POST /computing/generic/ot
```

with a payload like:

```json
{
  "dir": "working_dir",
  "ps_request": {
    "valuationDate": "2024/06/26 23:59:59",
    "marketDataSetIds": [
      "mkt_set_123456"
    ],
    "tradeSetId": "trade_set_789012",
    "requestDataSetId": "request_set_345678",
    "gridPricerTechnicalDetails": {
      "cartography": "FRTB_BOCOLLAT",
      "analyseName": "MCR_MTM",
      "directQmlRunnerCall": true,
      "qmlRunner": "QMLRPREGRPC",
      "foCluster": "OTRPLI1",
      "qlibVersion": "GMDPRS_PS_LATEST",
      "psOutputType": "RAW",
      "outputCurrency": "USD",
      "subtaskPolicy": "AlwaysDistribute"
    },
    "lagInDaysForBackprice": 0
  }
}

```

See:

```text
examples/api_payloads/generic_existing_set_ids.json
```

Use this with `/computing/generic/ot`, because `/computing/generic/full-qml` creates fresh market data, trade, and request sets from local QML files and overwrites those ids.

For this direct-set-id payload, the top-level `marketDataSetIds`, `tradeSetId`, and `requestDataSetId` are the important fields. A `useCache` block is not required here.
