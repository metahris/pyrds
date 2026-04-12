# Mock Pricing Workflow

This folder is disposable. It mocks the local QML directory, the Market Data API,
the Trades API, the Pricing Service API, and pricing responses so you can test
the SDK orchestration without calling real services.

Run from the repository root:

```bash
python3 examples/mock_pricing_workflow/run_mock_workflows.py
```

The project runtime dependencies must be installed first, especially `pydantic`.
For example:

```bash
python3 -m pip install -e .
```

What it exercises:

- `GenericRunner.compute_ot`
- `GenericRunner.compute_full_qml`
- `GenericRunner.compute_custom_mkt_data`
- `SimplePricingRunner.run`
- `FullQmlPricingRunner.run`
- async batch pricing through the mock pricing API

The mocked QML input directory is:

```text
examples/mock_pricing_workflow/workdir
```

You can delete this whole `examples/mock_pricing_workflow` folder after testing.
