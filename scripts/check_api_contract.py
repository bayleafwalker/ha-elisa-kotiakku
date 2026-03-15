"""Run a live smoke check against the Gridle public measurements API."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib import error, parse, request

API_KEY_ENV_VAR = "GRIDLE_API_KEY"
ENV_FILE = ".env"
DEFAULT_BASE_URL = "https://residential.gridle.com/api/public/measurements"
DEFAULT_LOOKBACK_HOURS = 2
REQUEST_TIMEOUT_SECONDS = 30
REQUIRED_FIELDS = ("period_start", "period_end")
OPTIONAL_NUMBER_FIELDS = (
    "battery_power_kw",
    "state_of_charge_percent",
    "solar_power_kw",
    "grid_power_kw",
    "house_power_kw",
    "solar_to_house_kw",
    "solar_to_battery_kw",
    "solar_to_grid_kw",
    "grid_to_house_kw",
    "grid_to_battery_kw",
    "battery_to_house_kw",
    "battery_to_grid_kw",
    "spot_price_cents_per_kwh",
    "battery_temperature_celsius",
)

Urlopen = Callable[..., Any]


class ContractError(RuntimeError):
    """Raised when the live API response does not match expectations."""


def build_parser() -> argparse.ArgumentParser:
    """Return the CLI parser."""
    parser = argparse.ArgumentParser(
        description="Check the live Gridle measurements API contract."
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help="Measurements endpoint to query.",
    )
    parser.add_argument(
        "--lookback-hours",
        type=int,
        default=DEFAULT_LOOKBACK_HOURS,
        help="Recent range size for the second validation request.",
    )
    return parser


def build_recent_range_params(
    now: datetime, *, lookback_hours: int = DEFAULT_LOOKBACK_HOURS
) -> dict[str, str]:
    """Build a short recent time range with timezone-aware timestamps."""
    if now.tzinfo is None:
        raise ContractError("Expected an aware datetime for range generation")
    if lookback_hours <= 0:
        raise ContractError("lookback_hours must be positive")

    end = now.astimezone(UTC).replace(microsecond=0)
    start = end - timedelta(hours=lookback_hours)
    return {
        "start_time": start.isoformat(),
        "end_time": end.isoformat(),
    }


def fetch_payload(
    api_key: str,
    *,
    base_url: str,
    params: dict[str, str] | None = None,
    timeout: int = REQUEST_TIMEOUT_SECONDS,
    urlopen: Urlopen = request.urlopen,
) -> object:
    """Fetch a JSON payload from the live API."""
    url = base_url
    if params:
        url = f"{base_url}?{parse.urlencode(params)}"

    req = request.Request(url, headers={"x-api-key": api_key})
    try:
        with urlopen(req, timeout=timeout) as response:
            status = getattr(response, "status", 200)
            if status != 200:
                raise ContractError(f"Unexpected HTTP status {status} for {url}")
            body = response.read().decode("utf-8")
    except error.HTTPError as err:
        body = err.read().decode("utf-8", "replace")[:200]
        raise ContractError(
            f"HTTP {err.code} for {base_url}: {body or err.reason}"
        ) from err
    except error.URLError as err:
        raise ContractError(f"Request failed for {base_url}: {err.reason}") from err

    try:
        return json.loads(body)
    except json.JSONDecodeError as err:
        raise ContractError(f"Response was not valid JSON for {base_url}") from err


def validate_timestamp(value: object, *, field_name: str) -> str:
    """Validate one ISO 8601 timestamp field."""
    if not isinstance(value, str) or not value:
        raise ContractError(f"{field_name} must be a non-empty string")

    try:
        datetime.fromisoformat(value)
    except ValueError as err:
        raise ContractError(f"{field_name} is not valid ISO 8601: {value}") from err

    return value


def normalize_timestamp(value: object, *, field_name: str) -> str:
    """Normalize one timestamp to canonical UTC `Z` output."""
    validated = validate_timestamp(value, field_name=field_name)
    timestamp = datetime.fromisoformat(validated)
    if timestamp.tzinfo is None:
        raise ContractError(f"{field_name} must include timezone info")
    return timestamp.astimezone(UTC).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def validate_measurement_item(
    item: object,
    *,
    index: int,
    label: str,
) -> dict[str, Any]:
    """Validate one measurement object."""
    if not isinstance(item, dict):
        raise ContractError(f"{label}[{index}] is not an object")

    for field_name in REQUIRED_FIELDS:
        if field_name not in item:
            raise ContractError(f"{label}[{index}] is missing {field_name}")
        validate_timestamp(item[field_name], field_name=field_name)

    for field_name in OPTIONAL_NUMBER_FIELDS:
        value = item.get(field_name)
        if value is not None and not isinstance(value, int | float):
            raise ContractError(
                f"{label}[{index}].{field_name} must be a number or null"
            )

    return item


def validate_payload(payload: object, *, label: str) -> list[dict[str, Any]]:
    """Validate the full API payload."""
    if not isinstance(payload, list):
        raise ContractError(f"{label} response is not a list")
    if not payload:
        raise ContractError(f"{label} response is empty")
    return [
        validate_measurement_item(item, index=index, label=label)
        for index, item in enumerate(payload)
    ]


def summarize_measurements(measurements: list[dict[str, Any]]) -> dict[str, str | int]:
    """Return sanitized summary information for logging."""
    period_ends = [
        normalize_timestamp(item["period_end"], field_name="period_end")
        for item in measurements
    ]
    return {
        "item_count": len(measurements),
        "oldest_period_end": min(period_ends),
        "newest_period_end": max(period_ends),
    }


def run_contract_check(
    api_key: str,
    *,
    base_url: str = DEFAULT_BASE_URL,
    lookback_hours: int = DEFAULT_LOOKBACK_HOURS,
    now: datetime | None = None,
    urlopen: Urlopen = request.urlopen,
) -> list[tuple[str, dict[str, str | int]]]:
    """Run both latest and recent-range contract checks."""
    current_time = now or datetime.now(UTC)
    responses = [
        ("latest", fetch_payload(api_key, base_url=base_url, urlopen=urlopen)),
        (
            "recent_range",
            fetch_payload(
                api_key,
                base_url=base_url,
                params=build_recent_range_params(
                    current_time, lookback_hours=lookback_hours
                ),
                urlopen=urlopen,
            ),
        ),
    ]

    return [
        (label, summarize_measurements(validate_payload(payload, label=label)))
        for label, payload in responses
    ]


def _load_env_file() -> None:
    """Load KEY=VALUE pairs from .env into os.environ (no overwrite)."""
    env_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ENV_FILE
    )
    try:
        with open(env_path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
    except FileNotFoundError:
        pass


def main(argv: list[str] | None = None) -> int:
    """Run the live contract check."""
    _load_env_file()
    args = build_parser().parse_args(argv)
    api_key = os.environ.get(API_KEY_ENV_VAR)
    if not api_key:
        raise ContractError(
            f"{API_KEY_ENV_VAR} is required for the live contract check"
        )

    for label, summary in run_contract_check(
        api_key,
        base_url=args.base_url,
        lookback_hours=args.lookback_hours,
    ):
        print(
            f"{label}:",
            f"item_count={summary['item_count']}",
            f"oldest_period_end={summary['oldest_period_end']}",
            f"newest_period_end={summary['newest_period_end']}",
        )

    print("API contract check passed.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ContractError as err:
        print(f"API contract check failed: {err}", file=sys.stderr)
        raise SystemExit(1) from err
