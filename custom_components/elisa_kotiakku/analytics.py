"""Historical analytics helpers for Elisa Kotiakku."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, time, timedelta
from statistics import median
from typing import Any, cast

from .api import MeasurementData

ROLLING_ANALYTICS_DAYS = 30
LOW_SOC_THRESHOLD_PERCENT = 20.0
HIGH_SOC_THRESHOLD_PERCENT = 80.0
HIGH_TEMPERATURE_THRESHOLD_C = 30.0
MIN_EPISODE_SOC_DELTA_PERCENT = 10.0
MIN_EPISODE_ENERGY_KWH = 0.5
MAX_EPISODE_DURATION_HOURS = 24.0
MAX_CAPACITY_CANDIDATES = 20
_MIN_ACTIVE_BATTERY_POWER_KW = 0.01


@dataclass(slots=True)
class DailyAnalyticsBucket:
    """Aggregated analytics values for one local calendar day."""

    house_consumption_kwh: float = 0.0
    grid_import_kwh: float = 0.0
    grid_export_kwh: float = 0.0
    solar_production_kwh: float = 0.0
    solar_to_house_kwh: float = 0.0
    solar_to_battery_kwh: float = 0.0
    solar_to_grid_kwh: float = 0.0
    grid_to_house_kwh: float = 0.0
    grid_to_battery_kwh: float = 0.0
    battery_to_house_kwh: float = 0.0
    battery_to_grid_kwh: float = 0.0
    battery_charge_kwh: float = 0.0
    battery_discharge_kwh: float = 0.0
    battery_temperature_weighted_sum: float = 0.0
    battery_temperature_hours: float = 0.0
    high_temperature_hours: float = 0.0
    low_soc_hours: float = 0.0
    high_soc_hours: float = 0.0


@dataclass(slots=True)
class AnalyticsEpisodeState:
    """Open usable-capacity estimation episode."""

    direction: str
    start_soc_percent: float
    last_soc_percent: float
    energy_kwh: float
    duration_hours: float
    last_period_end: str


class AnalyticsState:
    """Persisted historical analytics state."""

    def __init__(self) -> None:
        """Initialise empty analytics state."""
        self.reset()

    def reset(self) -> None:
        """Reset analytics runtime to an empty state."""
        self.daily_buckets: dict[str, DailyAnalyticsBucket] = {}
        self.usable_capacity_candidates_kwh: list[float] = []
        self.open_episode: AnalyticsEpisodeState | None = None
        self.last_period_end: str | None = None
        self._processed_period_ends: set[str] = set()

    def load(self, stored: Any) -> None:
        """Load analytics state from persisted data."""
        self.reset()
        if not isinstance(stored, dict):
            return

        last_period_end = stored.get("last_period_end")
        if isinstance(last_period_end, str):
            self.last_period_end = last_period_end

        processed_periods = stored.get("processed_period_ends")
        if isinstance(processed_periods, list):
            self._processed_period_ends = {
                item for item in processed_periods if isinstance(item, str)
            }

        candidates = stored.get("usable_capacity_candidates_kwh")
        if isinstance(candidates, list):
            self.usable_capacity_candidates_kwh = [
                float(value)
                for value in candidates
                if isinstance(value, int | float)
            ][-MAX_CAPACITY_CANDIDATES:]

        open_episode = stored.get("open_episode")
        if isinstance(open_episode, dict):
            self.open_episode = _load_episode(open_episode)

        daily_buckets = stored.get("daily_buckets")
        if isinstance(daily_buckets, dict):
            self.daily_buckets = _load_daily_buckets(daily_buckets)

    def as_store_data(self) -> dict[str, Any]:
        """Serialize analytics state for persistence."""
        return {
            "last_period_end": self.last_period_end,
            "processed_period_ends": list(self._processed_period_ends),
            "usable_capacity_candidates_kwh": self.usable_capacity_candidates_kwh,
            "open_episode": (
                asdict(self.open_episode)
                if self.open_episode is not None
                else None
            ),
            "daily_buckets": {
                key: asdict(bucket) for key, bucket in self.daily_buckets.items()
            },
        }

    def is_unprocessed_period(self, period_end: str) -> bool:
        """Return True if this period is not yet in analytics state."""
        return period_end not in self._processed_period_ends

    def mark_processed(self, period_end: str) -> None:
        """Mark one measurement window as processed for analytics."""
        self._processed_period_ends.add(period_end)
        self._update_last_period_end(period_end)

    @property
    def processed_period_count(self) -> int:
        """Return number of analytics-processed windows."""
        return len(self._processed_period_ends)

    @property
    def candidate_count(self) -> int:
        """Return number of retained usable-capacity candidates."""
        return len(self.usable_capacity_candidates_kwh)

    @property
    def total_day_bucket_count(self) -> int:
        """Return total number of persisted day buckets."""
        return len(self.daily_buckets)

    def process_measurement(self, measurement: MeasurementData) -> None:
        """Update analytics state from one measurement window."""
        hours = _measurement_duration_hours(
            measurement.period_start,
            measurement.period_end,
        )
        date_segments = _split_window_by_local_date(
            measurement.period_start,
            measurement.period_end,
            fallback_hours=hours,
        )
        self._update_daily_buckets(measurement, hours, date_segments)
        self._update_episode(measurement, hours)

    def estimated_usable_capacity_kwh(self) -> float | None:
        """Return the median usable-capacity estimate."""
        if not self.usable_capacity_candidates_kwh:
            return None
        return float(median(self.usable_capacity_candidates_kwh))

    def estimated_battery_health_percent(
        self,
        *,
        expected_usable_capacity_kwh: float,
    ) -> float | None:
        """Return heuristic health percentage against configured baseline."""
        estimated_capacity = self.estimated_usable_capacity_kwh()
        if (
            expected_usable_capacity_kwh <= 0
            or estimated_capacity is None
            or estimated_capacity <= 0
        ):
            return None
        return min(
            100.0,
            estimated_capacity / expected_usable_capacity_kwh * 100,
        )

    def battery_equivalent_full_cycles(
        self,
        *,
        expected_usable_capacity_kwh: float,
    ) -> float | None:
        """Return lifetime equivalent full cycles from throughput."""
        if expected_usable_capacity_kwh <= 0:
            return None

        throughput_kwh = sum(
            bucket.battery_charge_kwh + bucket.battery_discharge_kwh
            for bucket in self.daily_buckets.values()
        )
        if throughput_kwh <= 0:
            return None
        return throughput_kwh / (2 * expected_usable_capacity_kwh)

    def battery_temperature_average_30d(self) -> float | None:
        """Return rolling 30-day weighted average battery temperature."""
        buckets = self._rolling_buckets()
        weighted_sum = sum(
            bucket.battery_temperature_weighted_sum for bucket in buckets
        )
        total_hours = sum(bucket.battery_temperature_hours for bucket in buckets)
        if total_hours <= 0:
            return None
        return weighted_sum / total_hours

    def battery_high_temperature_hours_30d(self) -> float | None:
        """Return rolling 30-day hours above the high-temperature threshold."""
        return self._rolling_sum("high_temperature_hours")

    def battery_low_soc_hours_30d(self) -> float | None:
        """Return rolling 30-day hours at or below the low-SoC threshold."""
        return self._rolling_sum("low_soc_hours")

    def battery_high_soc_hours_30d(self) -> float | None:
        """Return rolling 30-day hours at or above the high-SoC threshold."""
        return self._rolling_sum("high_soc_hours")

    def self_sufficiency_ratio_30d(self) -> float | None:
        """Return rolling 30-day house self-sufficiency ratio as percent."""
        house_consumption = self._rolling_sum("house_consumption_kwh")
        grid_to_house = self._rolling_sum("grid_to_house_kwh")
        if house_consumption is None or house_consumption <= 0:
            return None
        return _ratio_percent(
            house_consumption - (grid_to_house or 0.0),
            house_consumption,
        )

    def solar_self_consumption_ratio_30d(self) -> float | None:
        """Return rolling 30-day solar self-consumption ratio as percent."""
        solar_production = self._rolling_sum("solar_production_kwh")
        if solar_production is None or solar_production <= 0:
            return None
        solar_self_consumed = (
            (self._rolling_sum("solar_to_house_kwh") or 0.0)
            + (self._rolling_sum("solar_to_battery_kwh") or 0.0)
        )
        return _ratio_percent(solar_self_consumed, solar_production)

    def battery_house_supply_ratio_30d(self) -> float | None:
        """Return rolling 30-day battery contribution to house load."""
        house_consumption = self._rolling_sum("house_consumption_kwh")
        if house_consumption is None or house_consumption <= 0:
            return None
        return _ratio_percent(
            self._rolling_sum("battery_to_house_kwh") or 0.0,
            house_consumption,
        )

    def battery_charge_from_solar_ratio_30d(self) -> float | None:
        """Return rolling 30-day solar share of battery charging."""
        battery_charge = self._rolling_sum("battery_charge_kwh")
        if battery_charge is None or battery_charge <= 0:
            return None
        return _ratio_percent(
            self._rolling_sum("solar_to_battery_kwh") or 0.0,
            battery_charge,
        )

    def total_avoided_grid_import_energy_kwh(self) -> float:
        """Return lifetime solar-plus-battery energy served locally."""
        return sum(
            bucket.solar_to_house_kwh + bucket.battery_to_house_kwh
            for bucket in self.daily_buckets.values()
        )

    def estimated_backup_runtime_hours(
        self,
        *,
        measurement: MeasurementData | None,
        expected_usable_capacity_kwh: float,
    ) -> float | None:
        """Return heuristic backup runtime from current load and battery energy."""
        if measurement is None or expected_usable_capacity_kwh <= 0:
            return None
        if measurement.state_of_charge_percent is None:
            return None

        house_load_kw = max(-(measurement.house_power_kw or 0.0), 0.0)
        if house_load_kw <= 0:
            return None

        estimated_capacity = self.estimated_usable_capacity_kwh()
        capacity_kwh = expected_usable_capacity_kwh
        if estimated_capacity is not None and estimated_capacity > 0:
            capacity_kwh = min(expected_usable_capacity_kwh, estimated_capacity)

        return capacity_kwh * measurement.state_of_charge_percent / 100 / house_load_kw

    def rolling_bucket_count(self) -> int:
        """Return number of day buckets represented in the 30-day window."""
        return len(self._rolling_buckets())

    def _rolling_buckets(self) -> list[DailyAnalyticsBucket]:
        """Return rolling 30-day buckets ending at latest analytics date."""
        reference_date = self._reference_date()
        if reference_date is None:
            return []

        buckets: list[DailyAnalyticsBucket] = []
        for day_offset in range(ROLLING_ANALYTICS_DAYS):
            day_key = (reference_date - timedelta(days=day_offset)).isoformat()
            bucket = self.daily_buckets.get(day_key)
            if bucket is not None:
                buckets.append(bucket)
        return buckets

    def _rolling_sum(self, field_name: str) -> float | None:
        """Return a rolling 30-day sum for one bucket field."""
        buckets = self._rolling_buckets()
        if not buckets:
            return None
        return sum(cast(float, getattr(bucket, field_name)) for bucket in buckets)

    def _reference_date(self) -> date | None:
        """Return latest analytics date."""
        if self.last_period_end is None:
            return None
        timestamp = _parse_iso8601(self.last_period_end)
        if timestamp is None:
            return None
        return timestamp.date()

    def _update_daily_buckets(
        self,
        measurement: MeasurementData,
        hours: float,
        date_segments: list[tuple[str, float]],
    ) -> None:
        """Fold one measurement into local-day buckets."""
        if hours <= 0:
            return

        house_consumption_kwh = max(-(measurement.house_power_kw or 0.0), 0.0) * hours
        grid_import_kwh = max(measurement.grid_power_kw or 0.0, 0.0) * hours
        grid_export_kwh = max(-(measurement.grid_power_kw or 0.0), 0.0) * hours
        solar_production_kwh = max(measurement.solar_power_kw or 0.0, 0.0) * hours
        solar_to_house_kwh = max(measurement.solar_to_house_kw or 0.0, 0.0) * hours
        solar_to_battery_kwh = max(
            measurement.solar_to_battery_kw or 0.0, 0.0
        ) * hours
        solar_to_grid_kwh = max(measurement.solar_to_grid_kw or 0.0, 0.0) * hours
        grid_to_house_kwh = max(measurement.grid_to_house_kw or 0.0, 0.0) * hours
        grid_to_battery_kwh = max(
            measurement.grid_to_battery_kw or 0.0, 0.0
        ) * hours
        battery_to_house_kwh = max(
            measurement.battery_to_house_kw or 0.0, 0.0
        ) * hours
        battery_to_grid_kwh = max(measurement.battery_to_grid_kw or 0.0, 0.0) * hours
        battery_charge_kwh = max(-(measurement.battery_power_kw or 0.0), 0.0) * hours
        battery_discharge_kwh = max(
            measurement.battery_power_kw or 0.0, 0.0
        ) * hours

        for date_key, segment_hours in date_segments:
            ratio = segment_hours / hours
            bucket = self.daily_buckets.setdefault(date_key, DailyAnalyticsBucket())

            bucket.house_consumption_kwh += house_consumption_kwh * ratio
            bucket.grid_import_kwh += grid_import_kwh * ratio
            bucket.grid_export_kwh += grid_export_kwh * ratio
            bucket.solar_production_kwh += solar_production_kwh * ratio
            bucket.solar_to_house_kwh += solar_to_house_kwh * ratio
            bucket.solar_to_battery_kwh += solar_to_battery_kwh * ratio
            bucket.solar_to_grid_kwh += solar_to_grid_kwh * ratio
            bucket.grid_to_house_kwh += grid_to_house_kwh * ratio
            bucket.grid_to_battery_kwh += grid_to_battery_kwh * ratio
            bucket.battery_to_house_kwh += battery_to_house_kwh * ratio
            bucket.battery_to_grid_kwh += battery_to_grid_kwh * ratio
            bucket.battery_charge_kwh += battery_charge_kwh * ratio
            bucket.battery_discharge_kwh += battery_discharge_kwh * ratio

            if measurement.battery_temperature_celsius is not None:
                bucket.battery_temperature_weighted_sum += (
                    measurement.battery_temperature_celsius * segment_hours
                )
                bucket.battery_temperature_hours += segment_hours
                if (
                    measurement.battery_temperature_celsius
                    >= HIGH_TEMPERATURE_THRESHOLD_C
                ):
                    bucket.high_temperature_hours += segment_hours

            if measurement.state_of_charge_percent is not None:
                if measurement.state_of_charge_percent <= LOW_SOC_THRESHOLD_PERCENT:
                    bucket.low_soc_hours += segment_hours
                if measurement.state_of_charge_percent >= HIGH_SOC_THRESHOLD_PERCENT:
                    bucket.high_soc_hours += segment_hours

    def _update_episode(
        self,
        measurement: MeasurementData,
        hours: float,
    ) -> None:
        """Update open usable-capacity estimation episode."""
        if (
            measurement.state_of_charge_percent is None
            or measurement.battery_power_kw is None
            or abs(measurement.battery_power_kw) < _MIN_ACTIVE_BATTERY_POWER_KW
        ):
            self._finalize_open_episode()
            self.open_episode = None
            return

        direction = (
            "charge" if measurement.battery_power_kw < 0 else "discharge"
        )
        soc_percent = measurement.state_of_charge_percent

        if self.open_episode is None:
            self.open_episode = AnalyticsEpisodeState(
                direction=direction,
                start_soc_percent=soc_percent,
                last_soc_percent=soc_percent,
                energy_kwh=0.0,
                duration_hours=0.0,
                last_period_end=measurement.period_end,
            )
            return

        delta_soc = soc_percent - self.open_episode.last_soc_percent
        monotonic = (
            direction == self.open_episode.direction
            and (
                (direction == "charge" and delta_soc >= 0)
                or (direction == "discharge" and delta_soc <= 0)
            )
            and self.open_episode.duration_hours + hours <= MAX_EPISODE_DURATION_HOURS
        )

        if not monotonic:
            self._finalize_open_episode()
            self.open_episode = AnalyticsEpisodeState(
                direction=direction,
                start_soc_percent=soc_percent,
                last_soc_percent=soc_percent,
                energy_kwh=0.0,
                duration_hours=0.0,
                last_period_end=measurement.period_end,
            )
            return

        self.open_episode.energy_kwh += abs(measurement.battery_power_kw) * hours
        self.open_episode.duration_hours += hours
        self.open_episode.last_soc_percent = soc_percent
        self.open_episode.last_period_end = measurement.period_end

    def _finalize_open_episode(self) -> None:
        """Finalize the current episode into a capacity candidate if valid."""
        if self.open_episode is None:
            return

        delta_soc_percent = (
            self.open_episode.last_soc_percent - self.open_episode.start_soc_percent
        )
        if (
            abs(delta_soc_percent) >= MIN_EPISODE_SOC_DELTA_PERCENT
            and self.open_episode.energy_kwh >= MIN_EPISODE_ENERGY_KWH
            and self.open_episode.duration_hours <= MAX_EPISODE_DURATION_HOURS
        ):
            candidate_kwh = self.open_episode.energy_kwh / (
                abs(delta_soc_percent) / 100
            )
            if candidate_kwh > 0:
                self.usable_capacity_candidates_kwh.append(candidate_kwh)
                self.usable_capacity_candidates_kwh = (
                    self.usable_capacity_candidates_kwh[
                        -MAX_CAPACITY_CANDIDATES:
                    ]
                )

    def _update_last_period_end(self, period_end: str) -> None:
        """Track latest analytics period end."""
        if self.last_period_end is None:
            self.last_period_end = period_end
            return

        current = _parse_iso8601(period_end)
        previous = _parse_iso8601(self.last_period_end)
        if current is not None and previous is not None:
            if current > previous:
                self.last_period_end = period_end
            return

        if period_end > self.last_period_end:
            self.last_period_end = period_end


def _ratio_percent(numerator: float, denominator: float) -> float | None:
    """Return a bounded percentage ratio."""
    if denominator <= 0:
        return None
    return max(0.0, min(100.0, numerator / denominator * 100))


def _load_daily_buckets(raw: dict[str, Any]) -> dict[str, DailyAnalyticsBucket]:
    """Load persisted daily buckets."""
    loaded: dict[str, DailyAnalyticsBucket] = {}
    for key, value in raw.items():
        if not isinstance(key, str) or not isinstance(value, dict):
            continue
        loaded[key] = DailyAnalyticsBucket(
            house_consumption_kwh=_float(value.get("house_consumption_kwh")),
            grid_import_kwh=_float(value.get("grid_import_kwh")),
            grid_export_kwh=_float(value.get("grid_export_kwh")),
            solar_production_kwh=_float(value.get("solar_production_kwh")),
            solar_to_house_kwh=_float(value.get("solar_to_house_kwh")),
            solar_to_battery_kwh=_float(value.get("solar_to_battery_kwh")),
            solar_to_grid_kwh=_float(value.get("solar_to_grid_kwh")),
            grid_to_house_kwh=_float(value.get("grid_to_house_kwh")),
            grid_to_battery_kwh=_float(value.get("grid_to_battery_kwh")),
            battery_to_house_kwh=_float(value.get("battery_to_house_kwh")),
            battery_to_grid_kwh=_float(value.get("battery_to_grid_kwh")),
            battery_charge_kwh=_float(value.get("battery_charge_kwh")),
            battery_discharge_kwh=_float(value.get("battery_discharge_kwh")),
            battery_temperature_weighted_sum=_float(
                value.get("battery_temperature_weighted_sum")
            ),
            battery_temperature_hours=_float(
                value.get("battery_temperature_hours")
            ),
            high_temperature_hours=_float(value.get("high_temperature_hours")),
            low_soc_hours=_float(value.get("low_soc_hours")),
            high_soc_hours=_float(value.get("high_soc_hours")),
        )
    return loaded


def _load_episode(raw: dict[str, Any]) -> AnalyticsEpisodeState | None:
    """Load persisted open episode."""
    direction = raw.get("direction")
    last_period_end = raw.get("last_period_end")
    if not isinstance(direction, str) or not isinstance(last_period_end, str):
        return None
    return AnalyticsEpisodeState(
        direction=direction,
        start_soc_percent=_float(raw.get("start_soc_percent")),
        last_soc_percent=_float(raw.get("last_soc_percent")),
        energy_kwh=_float(raw.get("energy_kwh")),
        duration_hours=_float(raw.get("duration_hours")),
        last_period_end=last_period_end,
    )


def _float(value: Any) -> float:
    """Return a float or zero for unsupported values."""
    if isinstance(value, int | float):
        return float(value)
    return 0.0


def _parse_iso8601(value: str) -> datetime | None:
    """Parse ISO 8601 timestamp and return None on malformed input."""
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _measurement_duration_hours(period_start: str, period_end: str) -> float:
    """Return measurement window duration in hours."""
    start = _parse_iso8601(period_start)
    end = _parse_iso8601(period_end)
    if start is None or end is None or end <= start:
        return 5 / 60
    return (end - start).total_seconds() / 3600


def _split_window_by_local_date(
    period_start: str,
    period_end: str,
    *,
    fallback_hours: float,
) -> list[tuple[str, float]]:
    """Split one window by local calendar date, preserving duration."""
    start = _parse_iso8601(period_start)
    end = _parse_iso8601(period_end)
    if start is None or end is None or end <= start:
        fallback_key = period_start.split("T", 1)[0]
        return [(fallback_key, fallback_hours)]

    segments: list[tuple[str, float]] = []
    cursor = start
    while cursor < end:
        next_midnight = datetime.combine(
            cursor.date() + timedelta(days=1),
            time.min,
            tzinfo=cursor.tzinfo,
        )
        segment_end = min(end, next_midnight)
        segment_hours = (segment_end - cursor).total_seconds() / 3600
        segments.append((cursor.date().isoformat(), segment_hours))
        cursor = segment_end

    return segments
