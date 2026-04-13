# Override Payload Examples

These files document `override_plan` shapes for the structured override runner.

They are intentionally grouped under `examples/api_payloads/overrides/` because override plans can become large.

Override endpoints use this API wrapper:

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

Each example includes the full request shape expected by the override endpoints.

Files:

- `marketdata_replace_file.json`
- `marketdata_apply_to_all_replace_block.json`
- `product_set_xpath_text.json`
- `pricingparams_replace_file_all_trades.json`
- `pricingparams_replace_file_selected_trades.json`
- `pricingparams_replace_file_per_trade.json`
- `pricingparams_replace_blocks.json`
- `request_set_xpath_text.json`
- `instructionset_set_xpath_text.json`
- `instructionset_set_xpath_attribute.json`
- `replace_xpath_node.json`
- `multi_scenario_override_plan.json`

See `docs/overrides.md` for the full contract and validation rules.

## Light XML Examples

### Market Data: Fixing

Input file in `inputs/data/fixing_usd.xml`:

```xml
<fixing>
  <name>USD_FIXING</name>
  <value>1.10</value>
</fixing>
```

Override the value:

```json
{
  "name": "set_fixing_value",
  "target_type": "marketdata",
  "operation": "set_xpath_text",
  "target_id": "fixing_usd",
  "xpath": "./value",
  "value": "1.12",
  "match_policy": "exactly_one"
}
```

### Market Data: Model Block

Input file in `inputs/data/model_rates.xml`:

```xml
<model>
  <name>RATE_MODEL</name>
  <parameters>
    <meanReversion>0.01</meanReversion>
  </parameters>
</model>
```

Replace the `<parameters>` block:

```json
{
  "name": "replace_model_parameters",
  "target_type": "marketdata",
  "operation": "replace_block",
  "target_id": "model_rates",
  "source": {
    "inline_xml": "<parameters><meanReversion>0.02</meanReversion></parameters>"
  }
}
```

### Product

Input file in `inputs/trade/TRADE_001.xml`:

```xml
<product>
  <notional>
    <val>5000000</val>
  </notional>
  <currency>USD</currency>
</product>
```

Set the notional:

```json
{
  "name": "set_product_notional",
  "target_type": "product",
  "operation": "set_xpath_text",
  "target_id": "TRADE_001",
  "xpath": "./notional/val",
  "value": "10000000",
  "match_policy": "exactly_one"
}
```

### Pricing Params

Input pricing params:

```xml
<pricingparams>
  <model>
    <name>MODEL_A</name>
  </model>
  <calibration>
    <enabled>false</enabled>
  </calibration>
</pricingparams>
```

Replace both blocks:

```json
{
  "name": "replace_pricingparams_blocks",
  "target_type": "pricingparams",
  "operation": "replace_blocks",
  "target_id": "TRADE_001",
  "sources": [
    {
      "inline_xml": "<model><name>MODEL_B</name></model>"
    },
    {
      "inline_xml": "<calibration><enabled>true</enabled></calibration>"
    }
  ]
}
```

Replace pricing params for every trade in the trade container with the same file:

```json
{
  "name": "replace_all_pricingparams",
  "target_type": "pricingparams",
  "operation": "replace_file",
  "apply_to_all": true,
  "source": {
    "file_path": "inputs/data/ppm_to_replace.xml"
  }
}
```

This loops through all trades in the trade container:

```text
[(P1, ppm1), (P12, ppm2), ...]
```

and replaces every pricing params QML with:

```text
ppm_to_replace.xml
```

Use `file_path` when the replacement file is in `inputs/data`. Use `file_name` when it is in the default pricing params folder, `inputs/trade`.

Replace pricing params for a selected list of trades with one common file:

```json
{
  "name": "replace_selected_pricingparams",
  "target_type": "pricingparams",
  "operation": "replace_file",
  "target_ids": ["TRADE_001", "TRADE_002", "TRADE_003"],
  "source": {
    "file_name": "common_pricingparams.xml"
  }
}
```

`common_pricingparams.xml` is resolved from `inputs/trade`.

Replace pricing params per trade/product pair:

```json
{
  "name": "replace_each_trade_pricingparams",
  "target_type": "pricingparams",
  "operation": "replace_file",
  "target_sources": [
    {
      "target_id": "P1",
      "source": {
        "file_name": "ppm_bis1.xml"
      }
    },
    {
      "target_id": "P12",
      "source": {
        "file_name": "ppm_bis2.xml"
      }
    }
  ]
}
```

Use `target_sources` when each trade receives a different replacement file.

### Request

Input request:

```xml
<request>
  <product>!{PRODUCT}</product>
  <instructionset>!{INSTRUCTIONSET}</instructionset>
  <pricingparam>!{PRICINGPARAM}</pricingparam>
  <gridConfiguration>
    <distribute>false</distribute>
  </gridConfiguration>
</request>
```

Set `distribute`:

```json
{
  "name": "set_request_distribute",
  "target_type": "request",
  "operation": "set_xpath_text",
  "xpath": "./gridConfiguration/distribute",
  "value": "true",
  "match_policy": "exactly_one"
}
```

### Instruction Set

Input instructionset:

```xml
<instructionset>
  <instructions>
    <item type="PRICE">
      <valdate>2024/03/25</valdate>
      <mktdataenv>BASE</mktdataenv>
    </item>
  </instructions>
</instructionset>
```

Set the valuation date:

```json
{
  "name": "set_instruction_valdate",
  "target_type": "instructionset",
  "operation": "set_xpath_text",
  "xpath": "./instructions/item[@type='PRICE']/valdate",
  "value": "2024/03/26",
  "match_policy": "exactly_one"
}
```

Change the `type` attribute:

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

### Full File Replacement

Replace the whole target QML:

```json
{
  "name": "replace_full_fixing_file",
  "target_type": "marketdata",
  "operation": "replace_file",
  "target_id": "fixing_usd",
  "source": {
    "inline_xml": "<fixing><name>USD_FIXING</name><value>1.15</value></fixing>"
  }
}
```
