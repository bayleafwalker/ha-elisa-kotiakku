"""Tests for maintainer helper scripts."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

from scripts.check_api_contract import (
    ContractError,
    _load_env_file,
    build_recent_range_params,
    normalize_timestamp,
    run_contract_check,
    validate_payload,
)
from scripts.check_version_sync import (
    Versions,
    VersionSyncError,
    load_versions,
    validate_versions,
)


class _FakeResponse:
    """Simple context-manager response wrapper for urllib-based tests."""

    def __init__(self, payload: object) -> None:
        self.status = 200
        self._payload = payload

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")


def test_load_versions_reads_manifest_and_pyproject(tmp_path: Path) -> None:
    """Version loader should read both metadata files."""
    manifest = tmp_path / "manifest.json"
    pyproject = tmp_path / "pyproject.toml"
    manifest.write_text('{"version": "1.3.3"}', encoding="utf-8")
    pyproject.write_text(
        '[project]\nname = "ha-elisa-kotiakku"\nversion = "1.3.3"\n',
        encoding="utf-8",
    )

    versions = load_versions(manifest_path=manifest, pyproject_path=pyproject)

    assert versions.manifest == "1.3.3"
    assert versions.pyproject == "1.3.3"


def test_validate_versions_rejects_mismatched_metadata() -> None:
    """Version validation should fail when manifest and pyproject drift."""
    with pytest.raises(VersionSyncError, match="Version mismatch"):
        validate_versions(Versions(manifest="1.3.3", pyproject="1.3.2"))


def test_validate_versions_rejects_wrong_tag() -> None:
    """Tag validation should enforce the `v` prefix plus manifest version."""
    with pytest.raises(VersionSyncError, match="Tag mismatch"):
        validate_versions(Versions(manifest="1.3.3", pyproject="1.3.3"), tag="v1.3.2")


def test_build_recent_range_params_returns_aware_iso_timestamps() -> None:
    """Recent range helper should produce timezone-aware ISO datetimes."""
    params = build_recent_range_params(
        datetime(2026, 3, 15, 12, 0, tzinfo=UTC),
        lookback_hours=2,
    )

    assert params["start_time"] == "2026-03-15T10:00:00+00:00"
    assert params["end_time"] == "2026-03-15T12:00:00+00:00"


def test_validate_payload_rejects_invalid_optional_field_type() -> None:
    """Optional number fields must be numeric or null."""
    payload = [
        {
            "period_start": "2026-03-15T10:00:00+00:00",
            "period_end": "2026-03-15T10:05:00+00:00",
            "grid_power_kw": "bad",
        }
    ]

    with pytest.raises(ContractError, match="grid_power_kw"):
        validate_payload(payload, label="latest")


def test_normalize_timestamp_outputs_canonical_utc_z() -> None:
    """Timestamp normalization should emit one UTC representation."""
    assert (
        normalize_timestamp("2026-03-15T22:20:00+02:00", field_name="period_end")
        == "2026-03-15T20:20:00Z"
    )
    assert (
        normalize_timestamp("2026-03-15T20:20:00Z", field_name="period_end")
        == "2026-03-15T20:20:00Z"
    )


def test_run_contract_check_fetches_latest_and_recent_range() -> None:
    """Contract check should validate both endpoint variants."""
    payload = [
        {
            "period_start": "2026-03-15T10:00:00+00:00",
            "period_end": "2026-03-15T10:05:00+00:00",
            "grid_power_kw": 1.5,
        }
    ]
    calls: list[str] = []

    def _fake_urlopen(req, timeout=30):  # noqa: ANN001
        calls.append(req.full_url)
        return _FakeResponse(payload)

    summaries = run_contract_check(
        "test-api-key",
        now=datetime(2026, 3, 15, 12, 0, tzinfo=UTC),
        urlopen=_fake_urlopen,
    )

    assert [label for label, _summary in summaries] == ["latest", "recent_range"]
    assert len(calls) == 2
    assert urlparse(calls[0]).query == ""
    range_query = parse_qs(urlparse(calls[1]).query)
    assert "start_time" in range_query
    assert "end_time" in range_query


def test_run_contract_check_normalizes_mixed_offsets_in_summary() -> None:
    """Summaries should normalize mixed ISO offsets before reporting min/max."""
    payload = [
        {
            "period_start": "2026-03-15T20:00:00Z",
            "period_end": "2026-03-15T22:20:00+02:00",
            "grid_power_kw": 1.5,
        },
        {
            "period_start": "2026-03-15T20:05:00Z",
            "period_end": "2026-03-15T20:25:00Z",
            "grid_power_kw": 1.2,
        },
    ]

    def _fake_urlopen(req, timeout=30):  # noqa: ANN001
        return _FakeResponse(payload)

    summaries = run_contract_check(
        "test-api-key",
        now=datetime(2026, 3, 15, 12, 0, tzinfo=UTC),
        urlopen=_fake_urlopen,
    )

    for _label, summary in summaries:
        assert summary["oldest_period_end"] == "2026-03-15T20:20:00Z"
        assert summary["newest_period_end"] == "2026-03-15T20:25:00Z"


class TestLoadEnvFile:
    """Tests for .env file loading."""

    def test_loads_key_from_env_file(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Key=Value pairs are loaded into os.environ."""
        env_file = tmp_path / ".env"
        env_file.write_text("GRIDLE_API_KEY=test-key-123\n", encoding="utf-8")
        monkeypatch.setattr(
            "scripts.check_api_contract.ENV_FILE", ".env"
        )
        monkeypatch.delenv("GRIDLE_API_KEY", raising=False)
        # Point the loader at tmp_path
        monkeypatch.setattr(
            "scripts.check_api_contract.os.path.dirname",
            lambda p: str(tmp_path),
        )
        _load_env_file()
        assert os.environ.get("GRIDLE_API_KEY") == "test-key-123"
        monkeypatch.delenv("GRIDLE_API_KEY", raising=False)

    def test_does_not_overwrite_existing_env(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Existing environment variables take precedence."""
        env_file = tmp_path / ".env"
        env_file.write_text("GRIDLE_API_KEY=from-file\n", encoding="utf-8")
        monkeypatch.setenv("GRIDLE_API_KEY", "from-env")
        monkeypatch.setattr(
            "scripts.check_api_contract.os.path.dirname",
            lambda p: str(tmp_path),
        )
        _load_env_file()
        assert os.environ["GRIDLE_API_KEY"] == "from-env"

    def test_missing_env_file_is_silent(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Missing .env file does not raise."""
        monkeypatch.setattr(
            "scripts.check_api_contract.os.path.dirname",
            lambda p: "/nonexistent",
        )
        _load_env_file()  # should not raise

    def test_skips_comments_and_blank_lines(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Comments and blank lines are ignored."""
        env_file = tmp_path / ".env"
        env_file.write_text("# comment\n\nGRIDLE_API_KEY=val\n", encoding="utf-8")
        monkeypatch.delenv("GRIDLE_API_KEY", raising=False)
        monkeypatch.setattr(
            "scripts.check_api_contract.os.path.dirname",
            lambda p: str(tmp_path),
        )
        _load_env_file()
        assert os.environ.get("GRIDLE_API_KEY") == "val"
        monkeypatch.delenv("GRIDLE_API_KEY", raising=False)
