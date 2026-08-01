"""Binary sensors Tractive Plus."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import TractivePlusConfigEntry
from .const import TRACTIVE_DOMAIN
from .coordinator import TractivePlusCoordinator

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class TPBinaryDescription(BinarySensorEntityDescription):
    """Description d'un binary sensor Tractive Plus."""

    value_fn: Callable[[dict[str, Any]], Any]


TRACKER_BINARY: tuple[TPBinaryDescription, ...] = (
    TPBinaryDescription(
        key="in_power_saving_zone",
        translation_key="in_power_saving_zone",
        icon="mdi:home-map-marker",
        value_fn=lambda d: bool(d["pos"].get("power_saving_zone_id")),
    ),
    TPBinaryDescription(
        key="insurance_active",
        translation_key="insurance_active",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:shield-check",
        value_fn=lambda d: d["subscription"].get("insurance_active"),
    ),
    TPBinaryDescription(
        key="subscription_recurring",
        translation_key="subscription_recurring",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:autorenew",
        value_fn=lambda d: d["subscription"].get("recurring"),
    ),
)

PET_BINARY: tuple[TPBinaryDescription, ...] = (
    TPBinaryDescription(
        key="separation_phase",
        translation_key="separation_phase",
        icon="mdi:account-arrow-right",
        value_fn=lambda d: (
            (d.get("overview") or {}).get("separationPhaseStatus") or {}
        ).get("isPhaseOngoing"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TractivePlusConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Ajoute les binary sensors Tractive Plus."""
    coordinator = entry.runtime_data
    entities: list[BinarySensorEntity] = []
    for tracker_id, tdata in coordinator.data["trackers"].items():
        entities.extend(
            TractivePlusBinarySensor(coordinator, "trackers", tracker_id, desc)
            for desc in TRACKER_BINARY
        )
        entities.extend(
            TractiveGeofenceBinarySensor(coordinator, tracker_id, gid, gdata)
            for gid, gdata in (tdata.get("geofences") or {}).items()
        )
    for pet_id in coordinator.data["pets"]:
        entities.extend(
            TractivePlusBinarySensor(coordinator, "pets", pet_id, desc)
            for desc in PET_BINARY
        )
    async_add_entities(entities)


class TractivePlusBinarySensor(
    CoordinatorEntity[TractivePlusCoordinator], BinarySensorEntity
):
    """Binary sensor Tractive Plus."""

    _attr_has_entity_name = True
    entity_description: TPBinaryDescription

    def __init__(
        self,
        coordinator: TractivePlusCoordinator,
        kind: str,
        obj_id: str,
        description: TPBinaryDescription,
    ) -> None:
        """Initialise le binary sensor."""
        super().__init__(coordinator)
        self._kind = kind
        self._obj_id = obj_id
        self.entity_description = description
        self._attr_unique_id = "%s_plus_%s" % (obj_id, description.key)
        self._attr_device_info = DeviceInfo(identifiers={(TRACTIVE_DOMAIN, obj_id)})

    @property
    def is_on(self) -> bool | None:
        """Etat du binary sensor."""
        obj = self.coordinator.data.get(self._kind, {}).get(self._obj_id, {})
        try:
            value = self.entity_description.value_fn(obj)
        except (KeyError, TypeError, ValueError):
            return None
        return None if value is None else bool(value)


class TractiveGeofenceBinarySensor(
    CoordinatorEntity[TractivePlusCoordinator], BinarySensorEntity
):
    """Presence dans une cloture virtuelle Tractive."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:map-marker-radius"

    def __init__(
        self,
        coordinator: TractivePlusCoordinator,
        tracker_id: str,
        geofence_id: str,
        geofence: dict[str, Any],
    ) -> None:
        """Initialise le capteur de cloture."""
        super().__init__(coordinator)
        self._tracker_id = tracker_id
        self._geofence_id = geofence_id
        name = (geofence.get("name") or geofence_id).strip()
        self._attr_name = "Zone %s" % name
        self._attr_unique_id = "%s_plus_geofence_%s" % (tracker_id, geofence_id)
        self._attr_device_info = DeviceInfo(
            identifiers={(TRACTIVE_DOMAIN, tracker_id)}
        )

    @property
    def _geofence(self) -> dict[str, Any]:
        return self.coordinator.geofences(self._tracker_id).get(self._geofence_id, {})

    @property
    def is_on(self) -> bool | None:
        """Vrai si l'animal est dans la zone."""
        if not self._geofence:
            return None
        return self._geofence.get("entered_at") is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Details de la cloture."""
        gf = self._geofence
        return {
            "active": gf.get("active"),
            "fence_type": gf.get("fence_type"),
            "trigger": gf.get("trigger"),
            "radius": gf.get("radius"),
            "shape": gf.get("shape"),
            "home_flag": gf.get("home_flag"),
            "entered_at": gf.get("entered_at"),
        }
