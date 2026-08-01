"""Capteurs Tractive Plus."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfLength,
    UnitOfSpeed,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from . import TractivePlusConfigEntry
from .const import TRACTIVE_DOMAIN
from .coordinator import TractivePlusCoordinator

PARALLEL_UPDATES = 0


def _ts(value: Any) -> datetime | None:
    """Convertit un timestamp epoch ou ISO en datetime aware."""
    if value in (None, 0, ""):
        return None
    if isinstance(value, str):
        return dt_util.parse_datetime(value)
    return dt_util.utc_from_timestamp(int(value))


def _ov(d: dict[str, Any], *path: str) -> Any:
    """Navigue dans le payload health/overview."""
    cur: Any = d.get("overview") or {}
    for key in path:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur


def _settings(d: dict[str, Any]) -> dict[str, Any]:
    return ((d.get("trackable") or {}).get("details") or {}).get(
        "activity_settings"
    ) or {}


@dataclass(frozen=True, kw_only=True)
class TPSensorDescription(SensorEntityDescription):
    """Description d'un capteur Tractive Plus."""

    value_fn: Callable[[dict[str, Any]], Any]
    attrs_fn: Callable[[dict[str, Any]], dict[str, Any]] | None = None


def _psz_name(d: dict[str, Any]) -> Any:
    zid = d["pos"].get("power_saving_zone_id") or d["details"].get(
        "power_saving_zone_id"
    )
    zone = (d.get("psz") or {}).get(zid) or {}
    return zone.get("name")


TRACKER_SENSORS: tuple[TPSensorDescription, ...] = (
    TPSensorDescription(
        key="altitude",
        translation_key="altitude",
        native_unit_of_measurement=UnitOfLength.METERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d["pos"].get("altitude"),
    ),
    TPSensorDescription(
        key="position_accuracy",
        translation_key="position_accuracy",
        native_unit_of_measurement=UnitOfLength.METERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d["pos"].get("pos_uncertainty") or d["pos"].get("accuracy"),
    ),
    TPSensorDescription(
        key="sensor_used",
        translation_key="sensor_used",
        icon="mdi:crosshairs-gps",
        value_fn=lambda d: d["pos"].get("sensor_used"),
    ),
    TPSensorDescription(
        key="position_time",
        translation_key="position_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda d: _ts(d["pos"].get("time")),
    ),
    TPSensorDescription(
        key="speed",
        translation_key="speed",
        native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
        device_class=SensorDeviceClass.SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d["pos"].get("speed"),
    ),
    TPSensorDescription(
        key="course",
        translation_key="course",
        native_unit_of_measurement="deg",
        icon="mdi:compass",
        value_fn=lambda d: d["pos"].get("course"),
    ),
    TPSensorDescription(
        key="battery_state",
        translation_key="battery_state",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:battery-heart-variant",
        value_fn=lambda d: d["details"].get("battery_state"),
    ),
    TPSensorDescription(
        key="state_reason",
        translation_key="state_reason",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:information-outline",
        value_fn=lambda d: d["details"].get("state_reason"),
    ),
    TPSensorDescription(
        key="hw_status",
        translation_key="hw_status",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d["hw"].get("hw_status"),
    ),
    TPSensorDescription(
        key="hw_report_time",
        translation_key="hw_report_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: _ts(d["hw"].get("time")),
    ),
    TPSensorDescription(
        key="clip_mounted_state",
        translation_key="clip_mounted_state",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:paperclip",
        value_fn=lambda d: d["hw"].get("clip_mounted_state"),
    ),
    TPSensorDescription(
        key="temperature_state",
        translation_key="temperature_state",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d["hw"].get("temperature_state"),
    ),
    TPSensorDescription(
        key="fw_version",
        translation_key="fw_version",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d["details"].get("fw_version"),
    ),
    TPSensorDescription(
        key="hw_edition",
        translation_key="hw_edition",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d["details"].get("hw_edition"),
    ),
    TPSensorDescription(
        key="battery_save_mode",
        translation_key="battery_save_mode",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:battery-clock",
        value_fn=lambda d: d["details"].get("battery_save_mode"),
    ),
    TPSensorDescription(
        key="geofence_sensitivity",
        translation_key="geofence_sensitivity",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:tune",
        value_fn=lambda d: d["details"].get("geofence_sensitivity"),
    ),
    TPSensorDescription(
        key="zone_name",
        translation_key="zone_name",
        icon="mdi:home-map-marker",
        value_fn=_psz_name,
    ),
    TPSensorDescription(
        key="zone_type",
        translation_key="zone_type",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d["details"].get("prioritized_zone_type"),
    ),
    TPSensorDescription(
        key="zone_entered_at",
        translation_key="zone_entered_at",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda d: _ts(d["details"].get("prioritized_zone_entered_at")),
    ),
    TPSensorDescription(
        key="zone_last_seen_at",
        translation_key="zone_last_seen_at",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: _ts(d["details"].get("prioritized_zone_last_seen_at")),
    ),
    TPSensorDescription(
        key="subscription_status",
        translation_key="subscription_status",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:card-account-details-outline",
        value_fn=lambda d: d["subscription"].get("status"),
    ),
    TPSensorDescription(
        key="subscription_end",
        translation_key="subscription_end",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda d: _ts(d["subscription"].get("valid_to")),
    ),
    TPSensorDescription(
        key="subscription_plan",
        translation_key="subscription_plan",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d["subscription"].get("plan_type_used"),
    ),
    TPSensorDescription(
        key="subscription_interval",
        translation_key="subscription_interval",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d["subscription"].get("billing_interval"),
    ),
)


PET_SENSORS: tuple[TPSensorDescription, ...] = (
    TPSensorDescription(
        key="resting_heart_rate_status",
        translation_key="resting_heart_rate_status",
        icon="mdi:heart-pulse",
        value_fn=lambda d: _ov(d, "restingHeartRate", "status"),
        attrs_fn=lambda d: {"day_offset": _ov(d, "restingHeartRate", "dayOffset")},
    ),
    TPSensorDescription(
        key="resting_respiratory_rate_status",
        translation_key="resting_respiratory_rate_status",
        icon="mdi:lungs",
        value_fn=lambda d: _ov(d, "restingRespiratoryRate", "status"),
        attrs_fn=lambda d: {
            "day_offset": _ov(d, "restingRespiratoryRate", "dayOffset")
        },
    ),
    TPSensorDescription(
        key="bark_status",
        translation_key="bark_status",
        icon="mdi:dog-side",
        value_fn=lambda d: _ov(d, "bark", "status"),
        attrs_fn=lambda d: {"day_offset": _ov(d, "bark", "dayOffset")},
    ),
    TPSensorDescription(
        key="scratch_status",
        translation_key="scratch_status",
        icon="mdi:paw",
        value_fn=lambda d: _ov(d, "scratch", "status"),
        attrs_fn=lambda d: {"day_offset": _ov(d, "scratch", "dayOffset")},
    ),
    TPSensorDescription(
        key="health_alerts",
        translation_key="health_alerts",
        icon="mdi:alert-decagram",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: _ov(d, "healthAlerts", "unseenCount"),
    ),
    TPSensorDescription(
        key="activity_goal_progress",
        translation_key="activity_goal_progress",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:target",
        value_fn=lambda d: round(
            100
            * (_ov(d, "activity", "minutesActive") or 0)
            / _ov(d, "activity", "minutesGoal")
        )
        if _ov(d, "activity", "minutesGoal")
        else None,
    ),
    TPSensorDescription(
        key="sleep_total",
        translation_key="sleep_total",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:sleep",
        value_fn=lambda d: (_ov(d, "sleep", "minutesDaySleep") or 0)
        + (_ov(d, "sleep", "minutesNightSleep") or 0),
    ),
    TPSensorDescription(
        key="activity_current_hour",
        translation_key="activity_current_hour",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:chart-timeline-variant",
        value_fn=lambda d: (_ov(d, "activity", "hourlyDistribution") or [None] * 24)[
            dt_util.now().hour
        ],
        attrs_fn=lambda d: {
            "hourly_distribution": _ov(d, "activity", "hourlyDistribution")
        },
    ),
    TPSensorDescription(
        key="activity_synced_at",
        translation_key="activity_synced_at",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: _ts(_ov(d, "activityDataSyncedAt")),
    ),
    TPSensorDescription(
        key="daily_distance_goal",
        translation_key="daily_distance_goal",
        native_unit_of_measurement=UnitOfLength.METERS,
        device_class=SensorDeviceClass.DISTANCE,
        icon="mdi:map-marker-distance",
        value_fn=lambda d: _settings(d).get("daily_distance_goal"),
    ),
    TPSensorDescription(
        key="daily_points_goal",
        translation_key="daily_points_goal",
        icon="mdi:trophy-outline",
        value_fn=lambda d: _settings(d).get("daily_goal"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TractivePlusConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Ajoute les capteurs Tractive Plus."""
    coordinator = entry.runtime_data
    entities: list[TractivePlusSensor] = []
    for tracker_id in coordinator.data["trackers"]:
        entities.extend(
            TractivePlusSensor(coordinator, "trackers", tracker_id, desc)
            for desc in TRACKER_SENSORS
        )
    for pet_id in coordinator.data["pets"]:
        entities.extend(
            TractivePlusSensor(coordinator, "pets", pet_id, desc)
            for desc in PET_SENSORS
        )
    async_add_entities(entities)


class TractivePlusSensor(CoordinatorEntity[TractivePlusCoordinator], SensorEntity):
    """Capteur rattache aux appareils Tractive existants."""

    _attr_has_entity_name = True
    entity_description: TPSensorDescription

    def __init__(
        self,
        coordinator: TractivePlusCoordinator,
        kind: str,
        obj_id: str,
        description: TPSensorDescription,
    ) -> None:
        """Initialise le capteur."""
        super().__init__(coordinator)
        self._kind = kind
        self._obj_id = obj_id
        self.entity_description = description
        self._attr_unique_id = "%s_plus_%s" % (obj_id, description.key)
        self._attr_device_info = DeviceInfo(identifiers={(TRACTIVE_DOMAIN, obj_id)})

    @property
    def _obj(self) -> dict[str, Any]:
        return self.coordinator.data.get(self._kind, {}).get(self._obj_id, {})

    @property
    def native_value(self) -> Any:
        """Valeur du capteur."""
        try:
            return self.entity_description.value_fn(self._obj)
        except (KeyError, TypeError, ValueError, ZeroDivisionError, IndexError):
            return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Attributs supplementaires."""
        if self.entity_description.attrs_fn is None:
            return None
        try:
            return self.entity_description.attrs_fn(self._obj)
        except (KeyError, TypeError, ValueError):
            return None
