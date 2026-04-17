# Override Payloads

Overrides let you run one base request with controlled QML changes. Each scenario is independent, so you can compare prices across several changes without editing XML files by hand.

Use these endpoints:

```text
POST /overrides/ot
POST /overrides/full-qml
```

## Request Shape

Every override API payload has this wrapper:

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

Keys:

| Key | Meaning |
| --- | --- |
| `dir` | Working directory name under `pyrds_api.pyrds_dir`. |
| `ps_request` | Normal Pyrds pricing request. |
| `override_plan` | The scenario plan to run. |
| `dump` | Write raw XML result files under `results/`. |
| `dump_excel` | Write a summary Excel under `results/`. |

## Plan Shape

```json
{
  "scenarios": [
    {
      "scenario_id": "change_model",
      "description": "Optional note",
      "overrides": []
    }
  ]
}
```

Keys:

| Key | Meaning |
| --- | --- |
| `scenarios` | List of independent scenarios. |
| `scenario_id` | Unique scenario name in this plan. Used in result output. |
| `description` | Optional human note. |
| `overrides` | Ordered list of changes for this scenario. |

Rules:

- Scenario ids must be unique.
- Override names must be unique inside one scenario.
- Overrides run in the order listed.

## Override Shape

Most overrides look like this:

```json
{
  "name": "set_product_notional",
  "target_type": "product",
  "operation": "set_xpath_text",
  "target_id": "price-28405308-product",
  "xpath": "./notional/val",
  "value": "10000000",
  "match_policy": "exactly_one"
}
```

Keys:

| Key | Meaning |
| --- | --- |
| `name` | Unique name for this change inside the scenario. |
| `target_type` | Which QML family to change. |
| `operation` | What kind of change to apply. |
| `target_id` | One target key or trade id. Use only one target selector. |
| `target_ids` | Several targets receiving the same change. Use only one target selector. |
| `target_sources` | Several targets, each with its own source XML. Use only one target selector. |
| `apply_to_all` | Apply the change to every available target. Use only one target selector. |
| `source` | Replacement XML source for one target or all targets. |
| `sources` | Several replacement XML sources, used by `replace_blocks` or `add_files`. |
| `xpath` | XPath used by XPath operations. |
| `value` | New text value for `set_xpath_text` or attribute value for `set_xpath_attribute`. |
| `attribute` | Attribute name for `set_xpath_attribute`. |
| `match_policy` | How strict XPath matching should be. Default is `exactly_one`. |
| `allow_duplicate_tags` | Allow duplicate source root tags in `replace_blocks`. Default is `false`. |
| `metadata` | Optional free-form notes. Not used by the runner. |

## Target Types

| `target_type` | Changes |
| --- | --- |
| `marketdata` | Market data QML files. |
| `product` | Product QML by trade id. |
| `pricingparams` | Pricing params QML by trade id. |
| `request` | Request QML. No target id needed. |
| `instructionset` | Instruction set QML. No target id needed. |

For market data files ending in `_BASE`, keys use a pipe:

```text
MODEL_304_48_172_BASE.xml -> MODEL_304_48_172|BASE
YCSETUP_BASE.xml          -> YCSETUP|BASE
```

For product and pricing params, examples use:

```text
price-28405308-product
```

## Target Selectors

For `marketdata`, `product`, and `pricingparams`, pick exactly one selector.

```json
{ "target_id": "MODEL_304_48_172|BASE" }
```

```json
{ "target_ids": ["price-28405308-product"] }
```

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

```json
{ "apply_to_all": true }
```

| Selector | Use when |
| --- | --- |
| `target_id` | One target gets one change. |
| `target_ids` | Several targets get the same change. |
| `target_sources` | Each target gets a different source XML. |
| `apply_to_all` | Every available target gets the same change. |

For `request` and `instructionset`, omit target selectors because there is only one selected QML.

## Source XML

Operations that replace XML need `source` or `sources`.

Use inline XML:

```json
{
  "source": {
    "inline_xml": "<advancedSettings version=\"2\"><toleranceNotio>0.02</toleranceNotio></advancedSettings>"
  }
}
```

Use a file in the default folder for the target type:

```json
{
  "source": {
    "file_name": "price-28405308-pricingparam.xml"
  }
}
```

Use a path from the working dir:

```json
{
  "source": {
    "file_path": "inputs/data/MODEL_304_48_172_BASE.xml"
  }
}
```

Default `file_name` folders:

| Target type | Folder |
| --- | --- |
| `marketdata` | `inputs/data` |
| `product` | `inputs/trade` |
| `pricingparams` | `inputs/trade` |
| `request` | `inputs/data` |
| `instructionset` | `inputs/data` |

Each source must set exactly one of `inline_xml`, `file_name`, or `file_path`.

## Operations

| `operation` | Meaning | Typical target |
| --- | --- | --- |
| `add_file` | Add one local market data QML file. | `marketdata` |
| `add_files` | Add several local market data QML files. | `marketdata` |
| `replace_file` | Replace the whole QML document. | Any target |
| `replace_block` | Replace the first XML child block with the same tag as the source XML root. | Any target |
| `replace_blocks` | Replace several blocks in one QML. | Any target |
| `replace_xpath` | Replace XML nodes selected by XPath. | Any target |
| `set_xpath_text` | Set text on XML nodes selected by XPath. | Any target |
| `set_xpath_attribute` | Set one attribute on XML nodes selected by XPath. | Any target |

## XPath Match Policy

| `match_policy` | Meaning |
| --- | --- |
| `exactly_one` | XPath must match exactly one node. This is the default. |
| `one_or_more` | XPath must match at least one node. |
| `all` | Same behavior as `one_or_more`; use when the intent is every matched node. |

## QML Checks

Request QML must contain these exact values:

```xml
<product>!{PRODUCT}</product>
<instructionset>!{INSTRUCTIONSET}</instructionset>
<pricingparam>!{PRICINGPARAM}</pricingparam>
<distribute>true</distribute>
```

The `<instruction/>` content is not constrained by this check.

Instructionset QML must have:

- `<instructionset>` root.
- `<instructions>` block.
- At least one `<item>`.
- Every `PRICE` item must contain `valdate`, `filterDateCCF`, and `mktdataenv`.
- `valdate` and `filterDateCCF` must match `ps_request.valuationDate`.
- Any present `mktdataenv` must be `BASE`.

## Empty Pricing Params

Some trades have product QML and no pricing params. This is valid. Pricingparams overrides change trades with real pricing params and leave empty or missing pricing params empty.

## Common Examples

### Change One Product Value

```json
{
  "name": "set_product_notional",
  "target_type": "product",
  "operation": "set_xpath_text",
  "target_id": "price-28405308-product",
  "xpath": "./notional/val",
  "value": "10000000",
  "match_policy": "exactly_one"
}
```

### Replace One Market Data Block

```json
{
  "name": "replace_model_advanced_settings",
  "target_type": "marketdata",
  "operation": "replace_block",
  "target_id": "MODEL_304_48_172|BASE",
  "source": {
    "inline_xml": "<advancedSettings version=\"2\"><toleranceNotio>0.02</toleranceNotio></advancedSettings>"
  }
}
```

### Replace Pricing Params For Every Trade

```json
{
  "name": "replace_all_pricingparams",
  "target_type": "pricingparams",
  "operation": "replace_file",
  "apply_to_all": true,
  "source": {
    "file_name": "price-28405308-pricingparam.xml"
  }
}
```

### Replace Pricing Params Per Trade

```json
{
  "name": "replace_each_trade_pricingparams",
  "target_type": "pricingparams",
  "operation": "replace_file",
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

### Add Extra Local Market Data In OT Mode

Use this when an OT scenario needs local QML files added beside the base OT market data set.

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

### Change Request Text

```json
{
  "name": "set_request_verbose_false",
  "target_type": "request",
  "operation": "set_xpath_text",
  "xpath": "./gridConfiguration/verbose",
  "value": "false",
  "match_policy": "exactly_one"
}
```

### Change Instructionset Date

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

### Change An Attribute

```json
{
  "name": "change_price_type_to_backprice",
  "target_type": "instructionset",
  "operation": "set_xpath_attribute",
  "xpath": "./instructions/item[@type='PRICE']",
  "attribute": "type",
  "value": "BACKPRICE",
  "match_policy": "exactly_one"
}
```

## Example Files

| File | Shows |
| --- | --- |
| `marketdata_replace_file.json` | Replace one market data file. |
| `marketdata_apply_to_all_replace_block.json` | Replace one block in one market data file. |
| `ot_replace_pricingparams_add_marketdata.json` | Replace pricing params and add local market data in OT mode. |
| `product_set_xpath_text.json` | Change product XML text with XPath. |
| `pricingparams_replace_file_all_trades.json` | Replace pricing params for all non-empty trades. |
| `pricingparams_replace_file_selected_trades.json` | Replace pricing params for selected trades. |
| `pricingparams_replace_file_per_trade.json` | Replace pricing params per trade using `target_sources`. |
| `pricingparams_replace_blocks.json` | Replace several blocks in pricing params. |
| `request_set_xpath_text.json` | Change request XML text. |
| `instructionset_set_xpath_text.json` | Change instructionset XML text. |
| `instructionset_set_xpath_attribute.json` | Change instructionset XML attribute. |
| `replace_xpath_node.json` | Replace an XML node selected by XPath. |
| `multi_scenario_override_plan.json` | Run several independent scenarios. |

For the full contract and more validation details, see:

```text
docs/overrides.md
```
