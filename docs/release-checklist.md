# Release Checklist

Use this checklist before creating a new GitHub release.

## 1) Versioning and metadata

- Update `custom_components/elisa_kotiakku/manifest.json` version.
- Keep `pyproject.toml` metadata aligned for local tooling visibility.
- Run `python scripts/check_version_sync.py` before tagging.
- Ensure release notes/changelog mention notable behavior or entity changes.

## 2) Quality gates

- Run full test suite:

```bash
pytest -q
```

- Run lint and type-check:

```bash
ruff check .
mypy --explicit-package-bases custom_components/elisa_kotiakku
```

## 3) Integration sanity checks

- Confirm config flow and options flow still load correctly.
- Confirm sensor/entity IDs and translation keys remain stable unless intentionally changed.
- Confirm diagnostics still redact API key.
- If tariff/economics behavior changed, test `elisa_kotiakku.rebuild_economics` in a dev HA instance.

## 4) Docs and localization

- Update user-facing README sections affected by behavior changes.
- Validate translation JSON files.
- Update architecture notes when module boundaries or responsibilities change.

## 5) GitHub release

- Tag and title match `manifest.json` version.
- GitHub release workflow is triggered by a `v*` tag and re-checks version sync.
- After the workflow creates the release, edit the auto-generated notes to match `.github/release-notes-template.md`.
- Use sections: **Fixed**, **Added**, **Changed**, **Removed** (omit empty ones).
- Add **Upgrade Notes** section when user action is needed (option changes, entity renames, `rebuild_economics` recommendations).
