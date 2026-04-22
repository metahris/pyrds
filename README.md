# Pyrds

Python SDK and FastAPI surface for pricing workflows.

## Setup

From the project root:

```bash
pip install -r requirements.txt
```

## Configuration

The default config file is:

```text
pyrds/infrastructure/config/config.json
```

Set the working directory root in this file:

```json
{
  "pyrds_api": {
    "pyrds_dir": "/path/to/pyrds_working_dir"
  }
}
```

For API payloads, `dir` is the working directory name under `pyrds_api.pyrds_dir`.

## Working Directory Layout

Create the directory with:

```text
POST /working-dir
```

The API creates this layout:

```text
working_dir/
├── inputs/
│   ├── data/
│   └── trade/
├── logs/
├── results/
└── qml_updater/
```

For API payloads:

```json
{
  "dir": "working_dir"
}
```

means:

```text
<pyrds_api.pyrds_dir>/working_dir
```

## Full QML Files

For full-QML pricing, put request, instructionset, and market data QMLs in:

```text
working_dir/inputs/data/
```

Put product and pricing params QMLs in:

```text
working_dir/inputs/trade/
```

A realistic `inputs/data` folder can look like this:

```text
inputs/data/
├── 120482_BASE.xml
├── 123778_BASE.xml
├── cache.txt
├── CALIBRATOR_304_USD_BASE.xml
├── MODEL_304_48_172_BASE.xml
├── price-28405308-executeresult.xml
├── price-28405308-instructionset.xml
├── price-28405308-request.xml
├── static_data.xml
├── VOL_IR_USD_BASE.xml
├── VOLIRSETUP_BASE.xml
└── YCSETUP_BASE.xml
```

And `inputs/trade` can look like:

```text
inputs/trade/
├── price-28405308-product.xml
└── price-28405308-pricingparam.xml
```

Pyrds ignores non-QML files like `cache.txt`. It also excludes request, instructionset, and result QMLs from market data upload.

Stress QML files are uploaded to the market data set using the file name as the key:

```text
BERM_STRESS.xml -> BERM_STRESS
```

For stress endpoints, the payload `stress_name` must match this key.

Market data file names ending in `_BASE.xml` are uploaded with pipe keys:

```text
MODEL_304_48_172_BASE.xml -> MODEL_304_48_172|BASE
YCSETUP_BASE.xml          -> YCSETUP|BASE
VOLIRSETUP_BASE.xml       -> VOLIRSETUP|BASE
```

Use `_BASE.xml` for market data files used by the pricing service. If exported files are named like `filename_SNE.xml` or `filename_pricingsetup.xml`, rename them before running full-QML pricing:

```text
filename_SNE.xml          -> filename_BASE.xml
filename_pricingsetup.xml -> filename_BASE.xml
```

The pricing service expects these market data keys to resolve as `filename|BASE`.

If you already have remote set ids and want to price directly from them, use:

```text
POST /computing/generic/ot
```

with:

```text
examples/api_payloads/generic_existing_set_ids.json
```

That payload sends `marketDataSetIds`, `tradeSetId`, and `requestDataSetId` directly in `ps_request`.

Do not use this pattern with:

```text
POST /computing/generic/full-qml
```

because the full-QML runner creates fresh sets from local QML files and overwrites set ids.

Example payloads that define `ps_request.gridPricerTechnicalDetails` also include:

```json
"clientRequestKey": "some_key",
"utCode": "some_ot"
```

Use those fields when the upstream pricing service needs request tracking metadata.

## Backtest Files

For `POST /backtest/full-qml`, put historical data folders under:

```text
working_dir/inputs/data/
```

One folder can contain files for multiple dates. Example:

```text
inputs/data/
└── HISTO_20240102/
    ├── cache.txt
    ├── CALIBRATOR_6442_USD_HISTO_20240102.xml
    ├── CALIBRATOR_6442_USD_HISTO_20240103.xml
    ├── CCSETUP_HISTO_20240102.xml
    ├── CCSETUP_HISTO_20240103.xml
    ├── COPULA_IR_USD_HISTO_20240102.xml
    ├── COPULA_IR_USD_HISTO_20240103.xml
    ├── CURVE!USD1D_SOFR_HISTO_20240102.xml
    ├── CURVE!USD1D_SOFR_HISTO_20240103.xml
    ├── instructionset_20240102.xml
    ├── MODEL_6442_48_62_HISTO_20240102.xml
    ├── MODEL_6442_48_62_HISTO_20240103.xml
    ├── MODEL_6442_48_62_SwaptionMode_HISTO_20240102.xml
    ├── MODEL_6442_48_62_SwaptionMode_HISTO_20240103.xml
    ├── pricingparam_ptf.xml
    ├── pricingparam_swaptionmode.xml
    ├── PricingParams.BT.xml
    ├── QUOTE!USD_SOFR_1D.xml
    ├── request_20240102.xml
    ├── VOL!USD_SOFR_HISTO_20240102.xml
    ├── VOL!USD_SOFR_HISTO_20240103.xml
    ├── VOLIRSETUP_HISTO_20240102.xml
    ├── VOLIRSETUP_HISTO_20240103.xml
    ├── YCSETUP_HISTO_20240102.xml
    └── YCSETUP_HISTO_20240103.xml
```

Keep the shared product and pricing params in:

```text
inputs/trade/
├── price-28405308-product.xml
└── price-28405308-pricingparam.xml
```

For backtests, a payload `carto` like `HISTO` keeps the date suffix in uploaded market data keys:

```text
YCSETUP_HISTO_20240102.xml -> YCSETUP|HISTO_20240102
YCSETUP_HISTO_20240103.xml -> YCSETUP|HISTO_20240103
MODEL_6442_48_62_SwaptionMode_HISTO_20240102.xml -> MODEL_6442_48_62_SwaptionMode|HISTO_20240102
```

Files without the carto token keep their file stem as the key, for example:

```text
QUOTE!USD_SOFR_1D.xml -> QUOTE!USD_SOFR_1D
```

## Request QML Checks

Request QML must contain these exact placeholders:

```xml
<request version="3">
  <product>!{PRODUCT}</product>
  <instruction/>
  <instructionset>!{INSTRUCTIONSET}</instructionset>
  <pricingparam>!{PRICINGPARAM}</pricingparam>
  <gridConfiguration>
    <distribute>true</distribute>
  </gridConfiguration>
</request>
```

The `<instruction/>` content is allowed to vary. These values are not optional:

```text
product        -> !{PRODUCT}
instructionset -> !{INSTRUCTIONSET}
pricingparam   -> !{PRICINGPARAM}
distribute     -> true
```

Common request errors:

```text
product tag of the request qml must be !{PRODUCT}, got product.
instructionset tag of the request qml must be !{INSTRUCTIONSET}, got instructionset.
pricingparam tag of the request qml must be !{PRICINGPARAM}, got pricingparams.
distribute tag of the gridConfiguration must be true, got false.
```

## Instructionset Checks

Instructionset QML must have an `<instructionset>` root, an `<instructions>` block, and at least one `<item>`.

Every `PRICE` item must contain:

```xml
<item type="PRICE" version="8">
  <valdate>2024/06/26</valdate>
  <filterDateCCF>2024/06/26</filterDateCCF>
  <mktdataenv>BASE</mktdataenv>
</item>
```

When `ps_request.valuationDate` is available, `valdate` and `filterDateCCF` must match it. Any present `<mktdataenv>` must be `BASE`.

Common instructionset errors:

```text
Instruction set QML is required.
Instruction set QML must contain an instructions block.
Instruction set QML instructions block must contain at least one item.
valdate is required in instruction set item 1 (PRICE).
filterDateCCF is required in instruction set item 1 (PRICE).
mktdataenv in instructionset must be BASE for item 1, got HISTO.
```

## Results

Raw pricing results are written under:

```text
working_dir/results/
```

Typical result names:

```text
result_<timestamp>.xml
HISTO_20240102_backtest_<timestamp>.xml
base_request_result_<timestamp>.xml
<scenario_id>_result_<timestamp>.xml
override_full_qml_summary_<timestamp>.xlsx
override_ot_summary_<timestamp>.xlsx
```

## Logs

Each working directory also has:

```text
working_dir/logs/
```

For JSON API requests that include `dir` or `pyrds_dir`, Pyrds writes a per-run text log file there. It contains:

- the same log lines written to the terminal
- the final HTTP response body returned to Swagger

Typical log file names:

```text
2026-04-22_10-25-30_post_overrides_ot_ab12cd34.txt
2026-04-22_10-26-11_post_backtest_full-qml_ef56gh78.txt
```

Example:

```text
2026-04-22 10:25:30,123 - pyrds.api - INFO - API request started | {'method': 'POST', 'path': '/overrides/ot', 'log_file': '.../logs/2026-04-22_10-25-30_post_overrides_ot_ab12cd34.txt'}
2026-04-22 10:25:30,456 - pyrds.api - INFO - Started OT override pricing | {'qml_runner': 'QML_RUNNER'}
2026-04-22 10:25:31,789 - pyrds.api - INFO - Finished OT override pricing | {'qml_runner': 'QML_RUNNER', 'manifest_path': '.../logs/override_ot_manifest_2026-04-22_10-25-30.json'}

=== FINAL RESPONSE ===
status_code: 200
content_type: application/json
body:
{
  "base_request": {
    "raw_result_file": ".../results/base_request_result_2026-04-22_10-25-30.xml"
  },
  "scenario_one": {
    "raw_result_file": ".../results/scenario_one_result_2026-04-22_10-25-31.xml"
  },
  "scenario_two": {
    "status": "failed",
    "error": "TransportError: ..."
  }
}
```

## Override Manifest

Override runs also write a machine-readable manifest JSON under:

```text
working_dir/logs/
```

Typical file names:

```text
override_ot_manifest_<timestamp>.json
override_full_qml_manifest_<timestamp>.json
```

The manifest stores run status, per-scenario status, errors, and dumped raw-result file paths. It does not embed raw QML.

Example:

```json
{
  "run_type": "override_ot",
  "status": "partial_failure",
  "dump": true,
  "dump_excel": true,
  "summary_excel_file": "/path/to/working_dir/results/override_ot_summary_2026-04-22_10-25-31.xlsx",
  "base_request": {
    "status": "succeeded",
    "raw_result_file": "/path/to/working_dir/results/base_request_result_2026-04-22_10-25-30.xml"
  },
  "scenarios": {
    "scenario_one": {
      "status": "succeeded",
      "raw_result_file": "/path/to/working_dir/results/scenario_one_result_2026-04-22_10-25-31.xml"
    },
    "scenario_two": {
      "status": "failed",
      "error": "RuntimeError: scenario_two failed"
    }
  }
}
```

## Run The API

From the project root:

```bash
fastapi dev pyrds/api/run.py
```

Swagger is available at:

```text
http://127.0.0.1:8000/docs
```

## Debug In PyCharm

Open:

```text
pyrds/api/run.py
```

Create a Python debug configuration:

```text
Name: Pyrds API Debug
Script path: <project_root>/pyrds/api/run.py
Parameters: --debug
Working directory: <project_root>
Interpreter: your Python interpreter
```

Add breakpoints in the code, select `Pyrds API Debug`, and click `Debug`.

Then open Swagger and call an endpoint:

```text
http://127.0.0.1:8000/docs
```

Debugging rules:

- Use PyCharm `Debug`, not `Run`.
- Do not use `--reload` for breakpoint debugging.
- Keep the working directory set to the project root.

If a breakpoint does not hit, enable:

```text
Settings -> Build, Execution, Deployment -> Debugger
Attach to subprocess automatically
```

## Command Line Debug

Only use this outside PyCharm:

```bash
python pyrds/api/run.py --debug
```

Use another port:

```bash
python pyrds/api/run.py --debug --port 8001
```

## API Host And Port

Host and port are resolved in this order:

1. CLI flags: `--host`, `--port`
2. Config values: `pyrds_api.host`, `pyrds_api.port`

If port `8000` is already used:

```bash
lsof -i :8000
kill -9 <PID>
```

or run on another port:

```bash
python pyrds/api/run.py --debug --port 8001
```

## Tests

Run the test suite:

```bash
pytest
```

External service tests are skipped by default. To run them:

```bash
pytest --run-e2e
```

## Payload Examples

Copy/paste API payloads live under:

```text
examples/api_payloads/
```

Useful docs:

- `docs/api_payloads.md`
- `docs/overrides.md`
- `docs/stress_payloads.md`
- `docs/run_api.md`
