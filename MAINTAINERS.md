# Maintainers

## API contract

- Runtime HTTP access is limited to `GET https://residential.gridle.com/api/public/measurements`.
- Auth uses the `x-api-key` header only.
- Live contract monitoring is handled by `python scripts/check_api_contract.py` and `.github/workflows/api-contract.yml`.
- The contract check validates response shape and timestamp parsing only. It intentionally does not assert live import/export or charge/discharge sign outcomes.

## Domain invariants

- `period_end` is the dedupe key for energy, economics, and analytics processing.
- `grid_power_kw` is positive for import and negative for export.
- `battery_power_kw` is positive for discharge and negative for charge.
- Five-minute averages are integrated to `kWh` using `measurement_duration_hours`, with the default fallback window defined in `const.py`.
- `rebuild_economics` may reset and replay economics and analytics state, but it must never mutate cumulative energy totals.

## Tariff presets

- Bundled presets are dated snapshots, not live tariff feeds.
- Presets now carry `valid_from` and `valid_until` metadata. Repairs issues warn when a non-`custom` preset is near expiry or expired.
- When updating a preset, keep README notes, translations, and repair copy aligned with the new dates.

## Branching and commits

- Branch names follow `<type>/<slug>` convention:
  - `feature/` — new capability or sensor
  - `fix/` — bug fix
  - `refactor/` — structural improvement
  - `chore/` — CI, deps, tooling
  - `docs/` — documentation only
- Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/):
  - Format: `<type>(<scope>): <subject>` (scope optional)
  - Types: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`, `style`, `perf`
  - Subject: imperative mood, lowercase, no trailing period, ≤ 72 chars
  - The `.gitmessage` template is set via `git config commit.template .gitmessage`
- Release notes are maintained on GitHub Releases (no separate `CHANGELOG.md`).
  - After `gh release create --generate-notes`, edit the body to match `.github/release-notes-template.md`.
  - Use sections: Fixed, Added, Changed, Removed. Omit empty sections.

## CI and releases

- GitHub-hosted runners are the only supported runners for this public repo.
- Scheduled workflows run only from the default branch. GitHub may disable schedules on inactive public repositories after 60 days.
- `python scripts/check_version_sync.py` is the release gate for `manifest.json`, `pyproject.toml`, and tag alignment.
- Releases are created by `.github/workflows/release.yml` from `v*` tags with generated GitHub notes.

## Secret handling

- For local development, store `GRIDLE_API_KEY` in a `.env` file at the repo root (gitignored). The contract-check script loads it automatically.
- In CI, `GRIDLE_API_KEY` is stored as a GitHub Actions secret.
- Diagnostics must always redact the integration API key.
- Contract-check output must stay sanitized: counts and timestamps are fine, raw live payloads are not.
- Rotate `GRIDLE_API_KEY` if workflow logs, Actions history, or test fixtures ever risk exposing it.
