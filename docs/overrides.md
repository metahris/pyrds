# QML Overrides

Overrides let users modify QML inputs in a controlled, reproducible way before pricing. Instead of editing QML files manually or adding ad hoc runner logic, users define an `override_plan` containing one or more scenarios. Each scenario runs independently and produces its own pricing result.

Override examples live under:

```text
examples/api_payloads/overrides/
```

Swagger endpoints:

```text
POST /overrides/ot
POST /overrides/full-qml
```

## When To Use Overrides

Use overrides when a user wants to test changes such as:

- Replace an entire market data QML file.
- Add extra market data QML files beside the OT market data set.
- Replace one QML block inside a market data, product, pricing params, request, or instructionset QML.
- Replace several QML blocks in the same QML.
- Replace a node selected by XPath.
- Set text on one or more XPath-selected nodes.
- Set attributes on one or more XPath-selected nodes.
- Run several scenarios and compare the outputs.

## Compute Modes

The structured override runner supports two modes.

### OT Override Mode

Method:

```python
compute_override_ot_async(...)
```

Concept:

- Run the base OT request first.
- Extract the existing remote market data and trade set ids.
- Clone only the remote sets that need changes.
- Create an additional market data set when the scenario adds local market data files.
- Apply overrides to cloned QML content.
- Recompute each override scenario.
- Keep a `base_request` result for comparison.

Use this when the base pricing request is OT/platform-driven and users want to override parts of the remote QML used by that request.

### Full QML Override Mode

Method:

```python
compute_override_full_qml_async(...)
```

Concept:

- Load local QML from the Pyrds working dir.
- Apply overrides locally before sending QML to remote sets.
- Create fresh market data, trade, and request sets per scenario.
- Recompute each scenario.

Use this when the full pricing input is managed locally in:

```text
inputs/data
inputs/trade
```

## Top-Level Payload Shape

Override APIs use this shape in Swagger:

```json
{
  "dir": "working_dir",
  "ps_request": {},
  "override_plan": {
    "scenarios": []
  },
  "dump": true,
  "dump_excel": true
}
```

`dir` is the Pyrds working directory name under `pyrds_api.pyrds_dir`.

`ps_request` is a normal `PsRequest`.

`override_plan` defines scenarios and operations.

`dump` writes raw scenario result QML files.

`dump_excel` writes a summary Excel file.

## Override Plan Structure

```json
{
  "scenarios": [
    {
      "scenario_id": "scenario_name",
      "description": "Optional human description",
      "overrides": []
    }
  ]
}
```

Rules:

- `scenario_id` must be unique inside a plan.
- Override `name` must be unique inside a scenario.
- A scenario can contain multiple overrides.
- Overrides are applied in list order.
- Scenarios are independent.

## Target Types

`target_type` decides which artifact is changed.

```text
marketdata
product
pricingparams
request
instructionset
```

### marketdata

Targets market data QMLs.

For full QML mode, `target_id` is the local market data key after normal naming.

For OT mode, `target_id` is a market data key in the remote set.

### product

Targets product QML.

For full QML mode, `target_id` is the local trade id from the product file name.

For OT mode, `target_id` is a trade id in the remote trade set.

### pricingparams

Targets pricing parameters QML for a trade.

`target_id` follows the same rule as `product`.

### request

Targets request QML.

`target_id` is not required because there is one request QML selected by the runner.

### instructionset

Targets instructionset QML.

`target_id` is not required because there is one instructionset QML selected by the runner.

## Target Selection

For mapping targets like `marketdata`, `product`, and `pricingparams`, select either one target:

```json
{
  "target_id": "MODEL_304_48_172|BASE"
}
```

or a selected list of targets:

```json
{
  "target_ids": ["price-28405308-product"]
}
```

or a selected list where each target has its own replacement source:

```json
{
  "target_sources": [
    {
      "target_id": "price-28405308-product",
      "source": {
        "file_name": "price-28405308-pricingparam.xml"
      }
    }
  ]
}
```

or all available targets:

```json
{
  "apply_to_all": true
}
```

Set only one of `target_id`, `target_ids`, `target_sources`, and `apply_to_all`.

Use `target_ids` when all selected targets receive the same `source`.

Use `target_sources` when each target receives a different `source`.

Use `apply_to_all` when every target in the container receives the same `source`.

For `request` and `instructionset`, omit `target_id`.

## Source Types

Operations that need replacement QML use `source` or `sources`.

Exactly one field is allowed in each source:

```json
{
  "inline_xml": "<curve><enabled>true</enabled></curve>"
}
```

```json
{
  "file_name": "replacement_curve.xml"
}
```

```json
{
  "file_path": "inputs/data/replacement_curve.xml"
}
```

Source resolution:

- `inline_xml`: uses the QML directly.
- `file_name`: resolves by target type.
- `file_path`: relative paths resolve from the working dir; absolute paths are accepted.

Default `file_name` directories:

```text
marketdata     -> inputs/data
product        -> inputs/trade
pricingparams  -> inputs/trade
request        -> inputs/data
instructionset -> inputs/data
```

## Operations

### add_file

Add one market data QML file to a scenario.

This operation is only supported for `target_type=marketdata`.

In OT override mode, Pyrds creates a new market data set, adds the local QML to it, and sends both market data sets to pricing:

```text
marketDataSetIds = [added_local_market_data_set_id, base_or_overridden_ot_market_data_set_id]
```

Use this when the callback needs market data that is not already present in the OT market data set.

Example:

```json
{
  "name": "add_static_data",
  "target_type": "marketdata",
  "operation": "add_file",
  "target_id": "static_data",
  "source": {
    "file_path": "inputs/data/static_data.xml"
  }
}
```

Validation:

- `source` is required.
- `target_type` must be `marketdata`.
- `target_id` is recommended because it is the market data key sent to the remote set.
- If `target_id` is omitted, it can only be derived for file-based sources.
- Inline QML requires `target_id`.

### add_files

Add several market data QML files to a scenario.

This operation is only supported for `target_type=marketdata`.

The files do not have to be classic curve/model market data. If pricing expects pricing-param QML files to be available through the market data container, add them with `target_type=marketdata` and explicit `target_id` values.

Use `target_sources` when you want to explicitly control each market data key:

```json
{
  "name": "add_local_qmls_as_marketdata",
  "target_type": "marketdata",
  "operation": "add_files",
  "target_sources": [
    {
      "target_id": "MODEL_304_48_172|BASE",
      "source": {
        "file_path": "inputs/data/MODEL_304_48_172_BASE.xml"
      }
    },
    {
      "target_id": "CALIBRATOR_304_USD|BASE",
      "source": {
        "file_path": "inputs/data/CALIBRATOR_304_USD_BASE.xml"
      }
    }
  ]
}
```

Use `sources` when keys can be derived from file names:

```json
{
  "name": "add_extra_market_data",
  "target_type": "marketdata",
  "operation": "add_files",
  "sources": [
    {
      "file_name": "YCSETUP_BASE.xml"
    },
    {
      "file_name": "static_data.xml"
    }
  ]
}
```

Example key derivation:

```text
YCSETUP_BASE.xml -> YCSETUP|BASE
```

Validation:

- `sources` or `target_sources` is required.
- `target_type` must be `marketdata`.
- Inline QML should use `target_sources` so the market data key is explicit.

### replace_file

Replace the entire QML file/content with another QML document.

Use for:

- Swap full market data file.
- Swap full product QML.
- Swap full pricing params QML.
- Replace full request/instructionset QML.

Example:

```json
{
  "name": "replace_market_data_file",
  "target_type": "marketdata",
  "operation": "replace_file",
  "target_id": "MODEL_304_48_172|BASE",
  "source": {
    "file_name": "MODEL_304_48_172_BASE.xml"
  }
}
```

Validation:

- Existing QML must be valid QML.
- Replacement QML must be valid QML.
- `source` is required.

### replace_block

Replace the first child block whose QML tag matches the source block root tag.

Use for:

- Replace a `<curves>` block.
- Replace a `<payoff>` block.
- Replace a `<manageOption>` block.

Example:

```json
{
  "name": "replace_product_payoff",
  "target_type": "product",
  "operation": "replace_block",
  "target_id": "price-28405308-product",
  "source": {
    "inline_xml": "<payoff><type>UPDATED</type></payoff>"
  }
}
```

Validation:

- `source` is required.
- The source QML root tag must exist as a child block in the target QML.
- If the tag is not found, the scenario fails.

### replace_blocks

Replace multiple blocks in the same target QML.

Use for:

- Update several independent sections in one product.
- Update several market data sections in one scenario.

Example:

```json
{
  "name": "replace_multiple_pricing_blocks",
  "target_type": "pricingparams",
  "operation": "replace_blocks",
  "target_id": "price-28405308-product",
  "sources": [
    {
      "inline_xml": "<model><name>MODEL_A</name></model>"
    },
    {
      "inline_xml": "<calibration><enabled>true</enabled></calibration>"
    }
  ]
}
```

Validation:

- `sources` must contain at least one source.
- Duplicate source root tags are rejected unless `allow_duplicate_tags=true`.

### replace_xpath

Replace QML nodes selected by XPath with a replacement QML node.

Use for:

- Replace a nested node that is not convenient to target by block tag alone.
- Replace one exact node under a repeated structure.

Example:

```json
{
  "name": "replace_request_instruction",
  "target_type": "request",
  "operation": "replace_xpath",
  "xpath": "./base_request/instruction",
  "source": {
    "inline_xml": "<instruction>PRICE</instruction>"
  },
  "match_policy": "exactly_one"
}
```

Validation:

- `xpath` is required.
- `source` is required.
- XPath must match according to `match_policy`.

### set_xpath_text

Set text on nodes selected by XPath.

Use for:

- Change a scalar value.
- Change a date.
- Change a boolean flag.
- Change a config key.

Example:

```json
{
  "name": "set_instruction_valdate",
  "target_type": "instructionset",
  "operation": "set_xpath_text",
  "xpath": "./instructions/item[@type='PRICE']/valdate",
  "value": "2024/06/26",
  "match_policy": "exactly_one"
}
```

Validation:

- `xpath` is required.
- `value` is required.
- XPath must match according to `match_policy`.
- XPath must select QML elements, not attributes.

### set_xpath_attribute

Set an attribute on QML elements selected by XPath.

Use for:

- Change `type="PRICE"` to another instruction type.
- Set or update `version`.
- Change QML metadata stored as attributes.

Example:

```json
{
  "name": "change_price_instruction_type",
  "target_type": "instructionset",
  "operation": "set_xpath_attribute",
  "xpath": "./instructions/item[@type='PRICE']",
  "attribute": "type",
  "value": "BACKPRICE",
  "match_policy": "exactly_one"
}
```

Validation:

- `xpath` is required.
- `attribute` is required.
- `value` is required.
- XPath must select QML elements.
- Do not use `/@type`; use the `attribute` field.
- XPath must match according to `match_policy`.

## XPath Rules

Override XPath is evaluated with `lxml`, so it supports normal XPath predicates and attribute filters.

Select child elements with `/`:

```text
./instructions/item/valdate
```

Filter elements by attribute with brackets:

```text
./instructions/item[@type='PRICE']/valdate
```

Set element text with `set_xpath_text`:

```json
{
  "operation": "set_xpath_text",
  "xpath": "./instructions/item[@type='PRICE']/valdate",
  "value": "2024/03/26"
}
```

Set an attribute with `set_xpath_attribute`:

```json
{
  "operation": "set_xpath_attribute",
  "xpath": "./instructions/item[@type='PRICE']",
  "attribute": "type",
  "value": "BACKPRICE"
}
```

Avoid this for `set_xpath_text`:

```text
./instructions/item/@type
```

That XPath selects an attribute value, not a QML element. Attribute updates should use `set_xpath_attribute`.

## Match Policies

`match_policy` controls how XPath matches are validated.

### exactly_one

Default.

The XPath must match exactly one node.

Use when changing one specific field.

### one_or_more

The XPath must match at least one node.

Use when setting the same value on several known nodes.

### all

Currently behaves like `one_or_more`.

Use when the intent is to apply to every node matched by the XPath.

## Common Scenarios

### Scenario 1: Replace One Market Data File

Use `marketdata + replace_file + target_id`.

Example file:

```text
examples/api_payloads/overrides/marketdata_replace_file.json
```

### Scenario 2: Replace One Market Data Block

Use `marketdata + replace_block + target_id`.

Example file:

```text
examples/api_payloads/overrides/marketdata_apply_to_all_replace_block.json
```

### Scenario 2a: Add Extra Pricing Params Beside OT Market Data

Use `marketdata + add_file` or `marketdata + add_files`.

This is useful when the first OT pricing returns a market data set, but the second pricing also needs local pricing-param QML files referenced through market data keys.

This does not mutate the OT market data set. Pyrds creates an additional market data set and adds it before the OT/cloned set in `marketDataSetIds`.

Typical flow:

- `pricingparams + replace_file + apply_to_all=true` replaces every non-empty trade pricing params with `price-28405308-pricingparam.xml`.
- `marketdata + add_files` adds local files such as `MODEL_304_48_172_BASE.xml`, `CALIBRATOR_304_USD_BASE.xml`, `YCSETUP_BASE.xml`, and `VOLIRSETUP_BASE.xml` to an extra market data set.
- The recompute uses both market data sets: `[extra_local_set_id, base_or_cloned_ot_set_id]`.

Example file:

```text
examples/api_payloads/overrides/ot_replace_pricingparams_add_marketdata.json
```

### Scenario 3: Change Product Value By XPath

Use `product + set_xpath_text + target_id`.

Example file:

```text
examples/api_payloads/overrides/product_set_xpath_text.json
```

### Scenario 4: Replace Pricing Params Blocks

Use `pricingparams + replace_blocks + target_id`.

Example file:

```text
examples/api_payloads/overrides/pricingparams_replace_blocks.json
```

### Scenario 4a: Replace Pricing Params For Every Trade

Use `pricingparams + replace_file + apply_to_all=true`.

This loops over the trade container:

```text
[(price-28405308-product, price-28405308-pricingparam), ...]
```

and replaces every pricing params QML with one common file:

```text
[(price-28405308-product, price-28405308-pricingparam), ...]
```

Trades with product QML and empty or missing pricing params are normal. In structured overrides, those trades are cloned with empty pricing params and pricingparams overrides skip them instead of failing QML parsing.

If the common file refers to extra pricing-param QMLs by market data key, add those files in the same override scenario:

```json
{
  "name": "add_local_data_as_marketdata",
  "target_type": "marketdata",
  "operation": "add_files",
  "target_sources": [
    {
      "target_id": "MODEL_304_48_172|BASE",
      "source": {
        "file_path": "inputs/data/MODEL_304_48_172_BASE.xml"
      }
    },
    {
      "target_id": "YCSETUP|BASE",
      "source": {
        "file_path": "inputs/data/YCSETUP_BASE.xml"
      }
    }
  ]
}
```

Example file:

```text
examples/api_payloads/overrides/pricingparams_replace_file_all_trades.json
```

If the common file is under `inputs/data`, use:

```json
{
  "source": {
    "file_path": "inputs/data/price-28405308-pricingparam.xml"
  }
}
```

If the common file is under `inputs/trade`, use:

```json
{
  "source": {
    "file_name": "price-28405308-pricingparam.xml"
  }
}
```

### Scenario 4b: Replace Pricing Params For Selected Trades

Use `pricingparams + replace_file + target_ids`.

Example file:

```text
examples/api_payloads/overrides/pricingparams_replace_file_selected_trades.json
```

### Scenario 4c: Replace Pricing Params Per Trade/Product Pair

Use `pricingparams + replace_file + target_sources`.

This covers a trade container like:

```text
[(price-28405308-product, old_pricingparams), ...]
```

replaced with:

```text
[(price-28405308-product, price-28405308-pricingparam), ...]
```

Example file:

```text
examples/api_payloads/overrides/pricingparams_replace_file_per_trade.json
```

### Scenario 5: Change Request Configuration

Use `request + set_xpath_text`.

Example file:

```text
examples/api_payloads/overrides/request_set_xpath_text.json
```

### Scenario 6: Change Instruction Set Date

Use `instructionset + set_xpath_text`.

Example file:

```text
examples/api_payloads/overrides/instructionset_set_xpath_text.json
```

### Scenario 7: Multi-Scenario Comparison

Put several scenarios in one plan.

Example file:

```text
examples/api_payloads/overrides/multi_scenario_override_plan.json
```

### Scenario 8: Change A QML Attribute

Use `set_xpath_attribute`.

Example file:

```text
examples/api_payloads/overrides/instructionset_set_xpath_attribute.json
```

## Output

Each scenario returns:

```json
{
  "currency": "...",
  "price": "...",
  "duration": 123,
  "parsed_result_price": {},
  "raw_data": {},
  "response": {}
}
```

With `dump=true`, raw QML result files are written to:

```text
results/<scenario_id>_result_<timestamp>.xml
```

With `dump_excel=true`, a summary Excel is written to:

```text
results/override_<mode>_summary_<timestamp>.xlsx
```

## Error Behavior

Invalid override specs raise `OverrideValidationError`.

Failures while applying an override raise `OverrideApplicationError`.

Examples:

- Missing `target_id` for a market data override.
- Setting more than one of `target_id`, `target_ids`, `target_sources`, and `apply_to_all`.
- XPath matches zero nodes when `match_policy=exactly_one`.
- `set_xpath_text` is used with an attribute XPath instead of `set_xpath_attribute`.
- Replacement block tag does not exist in the target QML.
- Source QML is invalid.

The API maps these to structured error responses through the global exception handlers.

## Design Rule

Expose override workflows, not low-level QML helpers.

Swagger exposes workflows:

```text
POST /overrides/ot
POST /overrides/full-qml
```

Avoid exposing low-level methods like:

```text
replace_block
replace_xpath
set_xpath_text
```

Those are operations inside the override plan, not separate API endpoints.
