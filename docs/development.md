# Development

## Scope and assumptions

- Python `3.12+`
- Home Assistant development environment with custom integrations enabled
- Repository root as working directory

## Local setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-test.txt
```

## Run tests

```bash
pytest --cov=custom_components/elisa_kotiakku --cov-fail-under=95 -q
```

For quick targeted verification during refactors:

```bash
pytest tests/test_sensor.py tests/test_coordinator.py tests/test_payback.py -q
```

## Lint and type-check

```bash
ruff check .
mypy --explicit-package-bases custom_components/elisa_kotiakku
```

## Validate metadata and translations

```bash
python scripts/check_version_sync.py
python -m json.tool custom_components/elisa_kotiakku/strings.json > /dev/null
python -m json.tool custom_components/elisa_kotiakku/translations/en.json > /dev/null
python -m json.tool custom_components/elisa_kotiakku/translations/fi.json > /dev/null
python -m json.tool custom_components/elisa_kotiakku/manifest.json > /dev/null
```

## Live API contract check

```bash
GRIDLE_API_KEY=... python scripts/check_api_contract.py
```

The script only prints sanitized metadata such as item counts and latest
`period_end`. It never writes or uploads live response payloads.

## Packaging metadata policy

- `pyproject.toml` exists for tooling and metadata only.
- This integration is not published as a Python package.
- Runtime release/version truth lives in `custom_components/elisa_kotiakku/manifest.json` and GitHub release tags.

## Release workflow

Use [release-checklist.md](release-checklist.md) for pre-release and publishing steps.
