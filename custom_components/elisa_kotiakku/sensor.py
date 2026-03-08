"""Sensor platform for Elisa Kotiakku."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    CURRENCY_EURO,
    PERCENTAGE,
    EntityCategory,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ElisaKotiakkuConfigEntry
from .api import MeasurementData
from .coordinator import ElisaKotiakkuCoordinator
from .entity import ElisaKotiakkuEntity

UNIT_CENTS_PER_KWH = "c/kWh"
UNIT_CYCLES = "cycles"

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class ElisaKotiakkuSensorDescription(SensorEntityDescription):
    """Describe a measurement-based Elisa Kotiakku sensor."""

    value_fn: Callable[[MeasurementData], float | None]


@dataclass(frozen=True, kw_only=True)
class ElisaKotiakkuEnergySensorDescription(SensorEntityDescription):
    """Describe a cumulative energy sensor."""


@dataclass(frozen=True, kw_only=True)
class ElisaKotiakkuCoordinatorSensorDescription(SensorEntityDescription):
    """Describe a coordinator-derived sensor."""

    value_fn: Callable[[ElisaKotiakkuCoordinator], str | int | float | None]


SENSOR_DESCRIPTIONS: tuple[ElisaKotiakkuSensorDescription, ...] = (
    ElisaKotiakkuSensorDescription(
        key="battery_power",
        translation_key="battery_power",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.battery_power_kw,
    ),
    ElisaKotiakkuSensorDescription(
        key="state_of_charge",
        translation_key="state_of_charge",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.state_of_charge_percent,
    ),
    ElisaKotiakkuSensorDescription(
        key="battery_temperature",
        translation_key="battery_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.battery_temperature_celsius,
    ),
    ElisaKotiakkuSensorDescription(
        key="solar_power",
        translation_key="solar_power",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.solar_power_kw,
    ),
    ElisaKotiakkuSensorDescription(
        key="grid_power",
        translation_key="grid_power",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.grid_power_kw,
    ),
    ElisaKotiakkuSensorDescription(
        key="house_power",
        translation_key="house_power",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.house_power_kw,
    ),
    ElisaKotiakkuSensorDescription(
        key="solar_to_house",
        translation_key="solar_to_house",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda d: d.solar_to_house_kw,
    ),
    ElisaKotiakkuSensorDescription(
        key="solar_to_battery",
        translation_key="solar_to_battery",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda d: d.solar_to_battery_kw,
    ),
    ElisaKotiakkuSensorDescription(
        key="solar_to_grid",
        translation_key="solar_to_grid",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda d: d.solar_to_grid_kw,
    ),
    ElisaKotiakkuSensorDescription(
        key="grid_to_house",
        translation_key="grid_to_house",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda d: d.grid_to_house_kw,
    ),
    ElisaKotiakkuSensorDescription(
        key="grid_to_battery",
        translation_key="grid_to_battery",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda d: d.grid_to_battery_kw,
    ),
    ElisaKotiakkuSensorDescription(
        key="battery_to_house",
        translation_key="battery_to_house",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda d: d.battery_to_house_kw,
    ),
    ElisaKotiakkuSensorDescription(
        key="battery_to_grid",
        translation_key="battery_to_grid",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda d: d.battery_to_grid_kw,
    ),
    ElisaKotiakkuSensorDescription(
        key="spot_price",
        translation_key="spot_price",
        native_unit_of_measurement=UNIT_CENTS_PER_KWH,
        device_class=SensorDeviceClass.MONETARY,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.spot_price_cents_per_kwh,
    ),
)

ENERGY_SENSOR_DESCRIPTIONS: tuple[ElisaKotiakkuEnergySensorDescription, ...] = (
    ElisaKotiakkuEnergySensorDescription(
        key="grid_import_energy",
        translation_key="grid_import_energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    ElisaKotiakkuEnergySensorDescription(
        key="grid_export_energy",
        translation_key="grid_export_energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    ElisaKotiakkuEnergySensorDescription(
        key="solar_production_energy",
        translation_key="solar_production_energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    ElisaKotiakkuEnergySensorDescription(
        key="house_consumption_energy",
        translation_key="house_consumption_energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),
    ElisaKotiakkuEnergySensorDescription(
        key="battery_charge_energy",
        translation_key="battery_charge_energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),
    ElisaKotiakkuEnergySensorDescription(
        key="battery_discharge_energy",
        translation_key="battery_discharge_energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
    ),
)

COORDINATOR_SENSOR_DESCRIPTIONS: tuple[
    ElisaKotiakkuCoordinatorSensorDescription, ...
] = (
    ElisaKotiakkuCoordinatorSensorDescription(
        key="configured_tariff_preset",
        translation_key="configured_tariff_preset",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda c: c.tariff_config.tariff_preset,
    ),
    ElisaKotiakkuCoordinatorSensorDescription(
        key="active_tariff_mode",
        translation_key="active_tariff_mode",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda c: _active_rate_value(c, "tariff_mode"),
    ),
    ElisaKotiakkuCoordinatorSensorDescription(
        key="active_tariff_period",
        translation_key="active_tariff_period",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda c: _active_rate_value(c, "tariff_period"),
    ),
    ElisaKotiakkuCoordinatorSensorDescription(
        key="configured_power_fee_rule",
        translation_key="configured_power_fee_rule",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda c: c.tariff_config.power_fee_rule,
    ),
    ElisaKotiakkuCoordinatorSensorDescription(
        key="active_import_retailer_margin",
        translation_key="active_import_retailer_margin",
        native_unit_of_measurement=UNIT_CENTS_PER_KWH,
        device_class=SensorDeviceClass.MONETARY,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda c: _active_rate_value(
            c, "import_retailer_margin_cents_per_kwh"
        ),
    ),
    ElisaKotiakkuCoordinatorSensorDescription(
        key="active_import_transfer_fee",
        translation_key="active_import_transfer_fee",
        native_unit_of_measurement=UNIT_CENTS_PER_KWH,
        device_class=SensorDeviceClass.MONETARY,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda c: _active_rate_value(
            c, "import_transfer_fee_cents_per_kwh"
        ),
    ),
    ElisaKotiakkuCoordinatorSensorDescription(
        key="active_export_retailer_adjustment",
        translation_key="active_export_retailer_adjustment",
        native_unit_of_measurement=UNIT_CENTS_PER_KWH,
        device_class=SensorDeviceClass.MONETARY,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda c: _active_rate_value(
            c, "export_retailer_adjustment_cents_per_kwh"
        ),
    ),
    ElisaKotiakkuCoordinatorSensorDescription(
        key="active_export_transfer_fee",
        translation_key="active_export_transfer_fee",
        native_unit_of_measurement=UNIT_CENTS_PER_KWH,
        device_class=SensorDeviceClass.MONETARY,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda c: _active_rate_value(
            c, "export_transfer_fee_cents_per_kwh"
        ),
    ),
    ElisaKotiakkuCoordinatorSensorDescription(
        key="active_electricity_tax_fee",
        translation_key="active_electricity_tax_fee",
        native_unit_of_measurement=UNIT_CENTS_PER_KWH,
        device_class=SensorDeviceClass.MONETARY,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda c: _active_rate_value(
            c, "electricity_tax_cents_per_kwh"
        ),
    ),
    ElisaKotiakkuCoordinatorSensorDescription(
        key="active_import_unit_price",
        translation_key="active_import_unit_price",
        native_unit_of_measurement=UNIT_CENTS_PER_KWH,
        device_class=SensorDeviceClass.MONETARY,
        value_fn=lambda c: _active_rate_value(
            c, "import_unit_price_cents_per_kwh"
        ),
    ),
    ElisaKotiakkuCoordinatorSensorDescription(
        key="active_export_unit_price",
        translation_key="active_export_unit_price",
        native_unit_of_measurement=UNIT_CENTS_PER_KWH,
        device_class=SensorDeviceClass.MONETARY,
        value_fn=lambda c: _active_rate_value(
            c, "export_unit_price_cents_per_kwh"
        ),
    ),
    ElisaKotiakkuCoordinatorSensorDescription(
        key="total_purchase_cost",
        translation_key="total_purchase_cost",
        native_unit_of_measurement=CURRENCY_EURO,
        device_class=SensorDeviceClass.MONETARY,
        value_fn=lambda c: c.get_economics_total("purchase_cost"),
    ),
    ElisaKotiakkuCoordinatorSensorDescription(
        key="total_import_transfer_cost",
        translation_key="total_import_transfer_cost",
        native_unit_of_measurement=CURRENCY_EURO,
        device_class=SensorDeviceClass.MONETARY,
        value_fn=lambda c: c.get_economics_total("import_transfer_cost"),
    ),
    ElisaKotiakkuCoordinatorSensorDescription(
        key="total_electricity_tax_cost",
        translation_key="total_electricity_tax_cost",
        native_unit_of_measurement=CURRENCY_EURO,
        device_class=SensorDeviceClass.MONETARY,
        value_fn=lambda c: c.get_economics_total("electricity_tax_cost"),
    ),
    ElisaKotiakkuCoordinatorSensorDescription(
        key="total_export_revenue",
        translation_key="total_export_revenue",
        native_unit_of_measurement=CURRENCY_EURO,
        device_class=SensorDeviceClass.MONETARY,
        value_fn=lambda c: c.get_economics_total("export_revenue"),
    ),
    ElisaKotiakkuCoordinatorSensorDescription(
        key="total_export_transfer_cost",
        translation_key="total_export_transfer_cost",
        native_unit_of_measurement=CURRENCY_EURO,
        device_class=SensorDeviceClass.MONETARY,
        value_fn=lambda c: c.get_economics_total("export_transfer_cost"),
    ),
    ElisaKotiakkuCoordinatorSensorDescription(
        key="total_power_fee_cost",
        translation_key="total_power_fee_cost",
        native_unit_of_measurement=CURRENCY_EURO,
        device_class=SensorDeviceClass.MONETARY,
        value_fn=lambda c: c.get_economics_total("power_fee_cost"),
    ),
    ElisaKotiakkuCoordinatorSensorDescription(
        key="total_net_site_electricity_cost",
        translation_key="total_net_site_electricity_cost",
        native_unit_of_measurement=CURRENCY_EURO,
        device_class=SensorDeviceClass.MONETARY,
        value_fn=lambda c: c.get_economics_total("net_site_cost"),
    ),
    ElisaKotiakkuCoordinatorSensorDescription(
        key="total_battery_savings",
        translation_key="total_battery_savings",
        native_unit_of_measurement=CURRENCY_EURO,
        device_class=SensorDeviceClass.MONETARY,
        value_fn=lambda c: c.get_economics_total("battery_savings"),
    ),
    ElisaKotiakkuCoordinatorSensorDescription(
        key="total_solar_used_in_house_value",
        translation_key="total_solar_used_in_house_value",
        native_unit_of_measurement=CURRENCY_EURO,
        device_class=SensorDeviceClass.MONETARY,
        value_fn=lambda c: c.get_economics_total("solar_used_in_house_value"),
    ),
    ElisaKotiakkuCoordinatorSensorDescription(
        key="total_solar_export_net_value",
        translation_key="total_solar_export_net_value",
        native_unit_of_measurement=CURRENCY_EURO,
        device_class=SensorDeviceClass.MONETARY,
        value_fn=lambda c: c.get_economics_total("solar_export_net_value"),
    ),
    ElisaKotiakkuCoordinatorSensorDescription(
        key="total_battery_house_supply_value",
        translation_key="total_battery_house_supply_value",
        native_unit_of_measurement=CURRENCY_EURO,
        device_class=SensorDeviceClass.MONETARY,
        value_fn=lambda c: c.get_economics_total("battery_house_supply_value"),
    ),
    ElisaKotiakkuCoordinatorSensorDescription(
        key="total_avoided_grid_import_energy",
        translation_key="total_avoided_grid_import_energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda c: c.get_analytics_value("total_avoided_grid_import_energy"),
    ),
    ElisaKotiakkuCoordinatorSensorDescription(
        key="current_month_power_peak",
        translation_key="current_month_power_peak",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda c: c.get_current_month_power_peak(),
    ),
    ElisaKotiakkuCoordinatorSensorDescription(
        key="current_month_power_fee_estimate",
        translation_key="current_month_power_fee_estimate",
        native_unit_of_measurement=CURRENCY_EURO,
        device_class=SensorDeviceClass.MONETARY,
        value_fn=lambda c: c.get_current_month_power_fee_estimate(),
    ),
    ElisaKotiakkuCoordinatorSensorDescription(
        key="estimated_usable_battery_capacity",
        translation_key="estimated_usable_battery_capacity",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda c: c.get_analytics_value(
            "estimated_usable_battery_capacity"
        ),
    ),
    ElisaKotiakkuCoordinatorSensorDescription(
        key="estimated_battery_health",
        translation_key="estimated_battery_health",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda c: c.get_analytics_value("estimated_battery_health"),
    ),
    ElisaKotiakkuCoordinatorSensorDescription(
        key="battery_equivalent_full_cycles",
        translation_key="battery_equivalent_full_cycles",
        native_unit_of_measurement=UNIT_CYCLES,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda c: c.get_analytics_value(
            "battery_equivalent_full_cycles"
        ),
    ),
    ElisaKotiakkuCoordinatorSensorDescription(
        key="battery_temperature_average_30d",
        translation_key="battery_temperature_average_30d",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda c: c.get_analytics_value(
            "battery_temperature_average_30d"
        ),
    ),
    ElisaKotiakkuCoordinatorSensorDescription(
        key="battery_high_temperature_hours_30d",
        translation_key="battery_high_temperature_hours_30d",
        native_unit_of_measurement=UnitOfTime.HOURS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda c: c.get_analytics_value(
            "battery_high_temperature_hours_30d"
        ),
    ),
    ElisaKotiakkuCoordinatorSensorDescription(
        key="battery_low_soc_hours_30d",
        translation_key="battery_low_soc_hours_30d",
        native_unit_of_measurement=UnitOfTime.HOURS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda c: c.get_analytics_value("battery_low_soc_hours_30d"),
    ),
    ElisaKotiakkuCoordinatorSensorDescription(
        key="battery_high_soc_hours_30d",
        translation_key="battery_high_soc_hours_30d",
        native_unit_of_measurement=UnitOfTime.HOURS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda c: c.get_analytics_value("battery_high_soc_hours_30d"),
    ),
    ElisaKotiakkuCoordinatorSensorDescription(
        key="self_sufficiency_ratio_30d",
        translation_key="self_sufficiency_ratio_30d",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda c: c.get_analytics_value("self_sufficiency_ratio_30d"),
    ),
    ElisaKotiakkuCoordinatorSensorDescription(
        key="solar_self_consumption_ratio_30d",
        translation_key="solar_self_consumption_ratio_30d",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda c: c.get_analytics_value(
            "solar_self_consumption_ratio_30d"
        ),
    ),
    ElisaKotiakkuCoordinatorSensorDescription(
        key="battery_house_supply_ratio_30d",
        translation_key="battery_house_supply_ratio_30d",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda c: c.get_analytics_value(
            "battery_house_supply_ratio_30d"
        ),
    ),
    ElisaKotiakkuCoordinatorSensorDescription(
        key="battery_charge_from_solar_ratio_30d",
        translation_key="battery_charge_from_solar_ratio_30d",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda c: c.get_analytics_value(
            "battery_charge_from_solar_ratio_30d"
        ),
    ),
    ElisaKotiakkuCoordinatorSensorDescription(
        key="estimated_backup_runtime_hours",
        translation_key="estimated_backup_runtime_hours",
        native_unit_of_measurement=UnitOfTime.HOURS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda c: c.get_analytics_value(
            "estimated_backup_runtime_hours"
        ),
    ),
    ElisaKotiakkuCoordinatorSensorDescription(
        key="usable_capacity_candidate_count",
        translation_key="usable_capacity_candidate_count",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda c: c.get_analytics_debug_value(
            "usable_capacity_candidate_count"
        ),
    ),
    ElisaKotiakkuCoordinatorSensorDescription(
        key="analytics_processed_periods",
        translation_key="analytics_processed_periods",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda c: c.get_analytics_debug_value(
            "analytics_processed_periods"
        ),
    ),
    ElisaKotiakkuCoordinatorSensorDescription(
        key="analytics_total_day_buckets",
        translation_key="analytics_total_day_buckets",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda c: c.get_analytics_debug_value(
            "analytics_total_day_buckets"
        ),
    ),
    ElisaKotiakkuCoordinatorSensorDescription(
        key="analytics_rolling_day_buckets",
        translation_key="analytics_rolling_day_buckets",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda c: c.get_analytics_debug_value(
            "analytics_rolling_day_buckets"
        ),
    ),
    ElisaKotiakkuCoordinatorSensorDescription(
        key="skipped_savings_windows",
        translation_key="skipped_savings_windows",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda c: c.get_economics_debug_value("skipped_savings_windows"),
    ),
    ElisaKotiakkuCoordinatorSensorDescription(
        key="economics_processed_periods",
        translation_key="economics_processed_periods",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda c: c.get_economics_debug_value(
            "economics_processed_periods"
        ),
    ),
)

_ECONOMICS_SENSOR_KEYS = {
    "active_import_retailer_margin",
    "active_import_transfer_fee",
    "active_export_retailer_adjustment",
    "active_export_transfer_fee",
    "active_electricity_tax_fee",
    "active_import_unit_price",
    "active_export_unit_price",
    "total_purchase_cost",
    "total_import_transfer_cost",
    "total_electricity_tax_cost",
    "total_export_revenue",
    "total_export_transfer_cost",
    "total_power_fee_cost",
    "total_net_site_electricity_cost",
    "total_battery_savings",
    "total_solar_used_in_house_value",
    "total_solar_export_net_value",
    "total_battery_house_supply_value",
    "current_month_power_peak",
    "current_month_power_fee_estimate",
    "skipped_savings_windows",
    "economics_processed_periods",
}

_ANALYTICS_SENSOR_KEYS = {
    "estimated_usable_battery_capacity",
    "estimated_battery_health",
    "battery_equivalent_full_cycles",
    "battery_temperature_average_30d",
    "battery_high_temperature_hours_30d",
    "battery_low_soc_hours_30d",
    "battery_high_soc_hours_30d",
    "self_sufficiency_ratio_30d",
    "solar_self_consumption_ratio_30d",
    "battery_house_supply_ratio_30d",
    "battery_charge_from_solar_ratio_30d",
    "estimated_backup_runtime_hours",
    "total_avoided_grid_import_energy",
    "usable_capacity_candidate_count",
    "analytics_processed_periods",
    "analytics_total_day_buckets",
    "analytics_rolling_day_buckets",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ElisaKotiakkuConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Elisa Kotiakku sensor entities."""
    coordinator = entry.runtime_data
    async_add_entities(
        [
            ElisaKotiakkuSensor(coordinator, description)
            for description in SENSOR_DESCRIPTIONS
        ]
        + [
            ElisaKotiakkuEnergySensor(coordinator, description)
            for description in ENERGY_SENSOR_DESCRIPTIONS
        ]
        + [
            ElisaKotiakkuCoordinatorSensor(coordinator, description)
            for description in COORDINATOR_SENSOR_DESCRIPTIONS
        ]
    )


class ElisaKotiakkuSensor(ElisaKotiakkuEntity, SensorEntity):
    """Representation of an Elisa Kotiakku measurement sensor."""

    entity_description: ElisaKotiakkuSensorDescription

    def __init__(
        self,
        coordinator: ElisaKotiakkuCoordinator,
        description: ElisaKotiakkuSensorDescription,
    ) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> float | None:
        """Return the sensor value."""
        if self.coordinator.data is None:
            return None
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, str] | None:
        """Return extra state attributes (measurement period)."""
        if self.coordinator.data is None:
            return None
        return {
            "period_start": self.coordinator.data.period_start,
            "period_end": self.coordinator.data.period_end,
        }


class ElisaKotiakkuEnergySensor(ElisaKotiakkuEntity, SensorEntity):
    """Representation of a cumulative energy sensor."""

    entity_description: ElisaKotiakkuEnergySensorDescription

    def __init__(
        self,
        coordinator: ElisaKotiakkuCoordinator,
        description: ElisaKotiakkuEnergySensorDescription,
    ) -> None:
        """Initialise the energy sensor."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> float | None:
        """Return cumulative energy in kWh."""
        return self.coordinator.get_energy_total(self.entity_description.key)

    @property
    def extra_state_attributes(self) -> dict[str, str] | None:
        """Expose the latest period included in the cumulative counter."""
        if self.coordinator.energy_last_period_end is None:
            return None
        return {"last_period_end": self.coordinator.energy_last_period_end}


class ElisaKotiakkuCoordinatorSensor(ElisaKotiakkuEntity, SensorEntity):
    """Representation of a coordinator-derived tariff or economics sensor."""

    entity_description: ElisaKotiakkuCoordinatorSensorDescription

    def __init__(
        self,
        coordinator: ElisaKotiakkuCoordinator,
        description: ElisaKotiakkuCoordinatorSensorDescription,
    ) -> None:
        """Initialise the coordinator-backed sensor."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> str | int | float | None:
        """Return coordinator-derived state."""
        return self.entity_description.value_fn(self.coordinator)

    @property
    def extra_state_attributes(self) -> dict[str, str | int | float | bool] | None:
        """Expose domain-specific processing state and heuristic context."""
        key = self.entity_description.key
        attrs: dict[str, str | int | float] = {}

        if key in _ECONOMICS_SENSOR_KEYS:
            if self.coordinator.economics_last_period_end is None:
                return None
            attrs["last_period_end"] = self.coordinator.economics_last_period_end
            attrs["power_fee_rule"] = self.coordinator.tariff_config.power_fee_rule
            rates = self.coordinator.get_active_tariff_rates()
            if rates is not None:
                attrs["tariff_mode"] = rates.tariff_mode
                attrs["tariff_period"] = rates.tariff_period

            if key in {"total_battery_savings", "skipped_savings_windows"}:
                attrs["skipped_windows"] = (
                    self.coordinator.skipped_savings_window_count
                )

            if key in {
                "total_solar_used_in_house_value",
                "total_battery_house_supply_value",
            }:
                attrs["value_basis"] = "full_avoided_import"
                attrs["includes_power_fee"] = False
                attrs["includes_electricity_tax"] = True
                internal_key = key.removeprefix("total_")
                attrs["skipped_directional_windows"] = (
                    self.coordinator.get_attribution_skipped_window_count(
                        internal_key
                    )
                )

            if key == "total_solar_export_net_value":
                attrs["value_basis"] = "net_export_after_transfer"
                attrs["includes_power_fee"] = False
                attrs["includes_electricity_tax"] = False
                attrs["skipped_directional_windows"] = (
                    self.coordinator.get_attribution_skipped_window_count(
                        "solar_export_net_value"
                    )
                )

            if key == "total_battery_house_supply_value":
                attrs["interpretation"] = (
                    "gross_avoided_import_not_net_savings"
                )

        if key in _ANALYTICS_SENSOR_KEYS:
            if self.coordinator.analytics_last_period_end is None:
                return None
            attrs["last_period_end"] = self.coordinator.analytics_last_period_end

            if key == "estimated_battery_health":
                attrs["method"] = "heuristic"
                attrs["usable_capacity_candidate_count"] = (
                    self.coordinator.analytics_state.candidate_count
                )
                attrs["configured_expected_usable_capacity_kwh"] = (
                    self.coordinator.expected_usable_capacity_kwh
                )
            elif key == "estimated_usable_battery_capacity":
                attrs["usable_capacity_candidate_count"] = (
                    self.coordinator.analytics_state.candidate_count
                )

            if key in {
                "self_sufficiency_ratio_30d",
                "solar_self_consumption_ratio_30d",
                "battery_house_supply_ratio_30d",
                "battery_charge_from_solar_ratio_30d",
                "battery_temperature_average_30d",
                "battery_high_temperature_hours_30d",
                "battery_low_soc_hours_30d",
                "battery_high_soc_hours_30d",
                "analytics_rolling_day_buckets",
            }:
                attrs["rolling_window_days"] = 30
                attrs["rolling_bucket_count"] = (
                    self.coordinator.analytics_state.rolling_bucket_count()
                )

            if key == "total_avoided_grid_import_energy":
                attrs["interpretation"] = "solar_to_house_plus_battery_to_house"

        return attrs or None


def _active_rate_value(
    coordinator: ElisaKotiakkuCoordinator,
    attribute: str,
) -> str | float | None:
    """Extract one attribute from active tariff rates."""
    rates = coordinator.get_active_tariff_rates()
    if rates is None:
        return None
    return getattr(rates, attribute)
