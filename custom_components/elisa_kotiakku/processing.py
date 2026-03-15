"""Batch measurement processing helpers shared by coordinator paths."""

from __future__ import annotations

from dataclasses import dataclass

from .analytics import AnalyticsState
from .api import MeasurementData
from .economics_engine import EconomicsEngine
from .energy_store import EnergyStore
from .tariff import TariffConfig


@dataclass(slots=True)
class WindowProcessingStats:
    """Summary of one batch processing run."""

    processed_count: int = 0
    deduped_count: int = 0
    energy_changed: bool = False
    economics_changed: bool = False
    analytics_changed: bool = False
    latest_processed_measurement: MeasurementData | None = None

    def as_counts(self) -> dict[str, int]:
        """Return diagnostics-friendly processed/deduped counters."""
        return {
            "processed": self.processed_count,
            "deduped": self.deduped_count,
        }


def apply_measurements(
    measurements: list[MeasurementData],
    *,
    energy_state: EnergyStore,
    economics_state: EconomicsEngine,
    analytics_state: AnalyticsState,
    tariff_config: TariffConfig,
) -> WindowProcessingStats:
    """Apply one or more measurement windows to all runtime stores."""
    stats = WindowProcessingStats()

    for measurement in sorted(measurements, key=lambda item: item.period_end):
        measurement_processed = False

        if energy_state.process_measurement(measurement):
            stats.energy_changed = True
            measurement_processed = True

        if economics_state.process_measurement(
            measurement,
            tariff_config=tariff_config,
        ):
            stats.economics_changed = True
            measurement_processed = True

        if analytics_state.is_unprocessed_period(measurement.period_end):
            analytics_state.process_measurement(measurement)
            analytics_state.mark_processed(measurement.period_end)
            stats.analytics_changed = True
            measurement_processed = True

        if measurement_processed:
            stats.processed_count += 1
            stats.latest_processed_measurement = measurement
        else:
            stats.deduped_count += 1

    return stats


def rebuild_economics_range(
    measurements: list[MeasurementData],
    *,
    economics_state: EconomicsEngine,
    analytics_state: AnalyticsState,
    tariff_config: TariffConfig,
) -> WindowProcessingStats:
    """Replay a historical range into economics and analytics state only."""
    stats = WindowProcessingStats()

    for measurement in sorted(measurements, key=lambda item: item.period_end):
        if not economics_state.process_measurement(
            measurement,
            tariff_config=tariff_config,
        ):
            stats.deduped_count += 1
            continue

        analytics_state.process_measurement(measurement)
        analytics_state.mark_processed(measurement.period_end)
        stats.processed_count += 1
        stats.economics_changed = True
        stats.analytics_changed = True
        stats.latest_processed_measurement = measurement

    return stats
