# API Payload Examples

These examples are intentionally kept outside Swagger.

Use them with:

```bash
curl -X POST http://127.0.0.1:8000/working-dir \
  -H "Content-Type: application/json" \
  --data @examples/api_payloads/create_working_dir.json
```

Then call one of the generic computing endpoints:

```bash
curl -X POST http://127.0.0.1:8000/computing/generic/ot \
  -H "Content-Type: application/json" \
  --data @examples/api_payloads/generic_ot_id.json
```

Backtest and stress are also exposed in Swagger:

```bash
curl -X POST http://127.0.0.1:8000/backtest/full-qml \
  -H "Content-Type: application/json" \
  --data @examples/api_payloads/backtest_full_qml.json

curl -X POST http://127.0.0.1:8000/stress/full-qml \
  -H "Content-Type: application/json" \
  --data @examples/api_payloads/stress_full_qml.json

curl -X POST http://127.0.0.1:8000/qlib/regression-validation \
  -H "Content-Type: application/json" \
  --data @examples/api_payloads/qlib_reg_validator.json

curl -X POST http://127.0.0.1:8000/overrides/full-qml \
  -H "Content-Type: application/json" \
  --data @examples/api_payloads/overrides/multi_scenario_override_plan.json
```

Parse a result QML file already dumped under a working dir:

```bash
curl -X POST http://127.0.0.1:8000/results/parse/price \
  -H "Content-Type: application/json" \
  --data @examples/api_payloads/parse_result_file_price.json
```

Other parser examples use the same payload shape:

```bash
curl -X POST http://127.0.0.1:8000/results/parse/deltair \
  -H "Content-Type: application/json" \
  --data @examples/api_payloads/parse_result_file_deltair.json
```

Available payloads:

- `create_working_dir.json`
- `generic_ot_id.json`
- `generic_full_qml.json`
- `generic_option_ny_mtm.json`
- `generic_sne_mtm_custom.json`
- `generic_hybrid.json`
- `backprice_full_qml.json`
- `parse_result_inline_price.json`
- `parse_result_file_price.json`
- `parse_result_file_deltair.json`
- `parse_result_file_vegair.json`
- `parse_result_file_calibration.json`
- `backtest_full_qml.json`
- `stress_full_qml.json`
- `qlib_reg_validator.json`
- `overrides/`

Use `foCluster` in new payloads. Some older Pyrds examples used `focCluster`; the current runner logic reads `foCluster`.

Stress payloads use a compact `stress` block. Convert it before calling `StressRunner`:

```python
from pyrds import build_stress_request

stress_request = build_stress_request(payload["stress"])
```

See `docs/stress_payloads.md` for `scalar`, `vector`, `iter`, and scenario-count rules.

Compatibility status:

- `backprice_full_qml.json` can be sent to `/computing/generic/full-qml`.
- `backtest_full_qml.json` can be sent to `/backtest/full-qml`.
- `stress_full_qml.json` can be sent to `/stress/full-qml` or `/stress/ot`; the API builds `StressRequest` internally.
- `qlib_reg_validator.json` can be sent to `/qlib/regression-validation`.
- Override examples are grouped under `overrides/` and can be sent to `/overrides/ot` or `/overrides/full-qml` depending on the compute mode.
