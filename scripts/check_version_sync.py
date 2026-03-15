"""Verify that release metadata stays aligned."""

from __future__ import annotations

import argparse
import json
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path


class VersionSyncError(RuntimeError):
    """Raised when release metadata drifts out of sync."""


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST_PATH = ROOT / "custom_components" / "elisa_kotiakku" / "manifest.json"
DEFAULT_PYPROJECT_PATH = ROOT / "pyproject.toml"


@dataclass(frozen=True, slots=True)
class Versions:
    """Relevant release versions sourced from tracked metadata files."""

    manifest: str
    pyproject: str


def load_versions(
    *,
    manifest_path: Path = DEFAULT_MANIFEST_PATH,
    pyproject_path: Path = DEFAULT_PYPROJECT_PATH,
) -> Versions:
    """Load release versions from the manifest and pyproject."""
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    pyproject = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))

    manifest_version = manifest.get("version")
    if not isinstance(manifest_version, str) or not manifest_version:
        raise VersionSyncError(
            f"Manifest version is missing or invalid in {manifest_path}"
        )

    project = pyproject.get("project")
    if not isinstance(project, dict):
        raise VersionSyncError(
            f"Project metadata is missing or invalid in {pyproject_path}"
        )

    pyproject_version = project.get("version")
    if not isinstance(pyproject_version, str) or not pyproject_version:
        raise VersionSyncError(
            f"Pyproject version is missing or invalid in {pyproject_path}"
        )

    return Versions(manifest=manifest_version, pyproject=pyproject_version)


def validate_versions(versions: Versions, *, tag: str | None = None) -> None:
    """Raise when tracked release metadata does not match."""
    if versions.manifest != versions.pyproject:
        raise VersionSyncError(
            "Version mismatch: "
            f"manifest.json={versions.manifest} "
            f"pyproject.toml={versions.pyproject}"
        )

    if tag is not None:
        expected_tag = f"v{versions.manifest}"
        if tag != expected_tag:
            raise VersionSyncError(
                f"Tag mismatch: expected {expected_tag}, got {tag}"
            )


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""
    parser = argparse.ArgumentParser(
        description="Check that release metadata stays aligned."
    )
    parser.add_argument(
        "--tag",
        help="Optional git tag to validate against the manifest version.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the version-sync check."""
    args = build_parser().parse_args(argv)
    versions = load_versions()
    validate_versions(versions, tag=args.tag)
    print(
        "Version metadata is in sync:",
        f"manifest.json={versions.manifest}",
        f"pyproject.toml={versions.pyproject}",
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except VersionSyncError as err:
        print(f"Version sync check failed: {err}", file=sys.stderr)
        raise SystemExit(1) from err
