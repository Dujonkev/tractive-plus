"""Tractive Plus : capteurs Tractive supplementaires."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN
from .coordinator import TractivePlusCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]

type TractivePlusConfigEntry = ConfigEntry[TractivePlusCoordinator]

PROBE_SCHEMA = vol.Schema(
    {
        vol.Required("path"): cv.string,
        vol.Optional("aps", default=False): cv.boolean,
    }
)


async def async_setup_entry(
    hass: HomeAssistant, entry: TractivePlusConfigEntry
) -> bool:
    """Configure Tractive Plus."""
    coordinator = TractivePlusCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    async def _probe(call: ServiceCall) -> dict[str, Any]:
        """Interroge n'importe quel endpoint Tractive et renvoie la reponse."""
        result = await coordinator.request(
            call.data["path"], aps=call.data.get("aps", False)
        )
        _LOGGER.info("Tractive Plus probe %s -> %s", call.data["path"], result)
        return {"result": result}

    hass.services.async_register(
        DOMAIN,
        "probe",
        _probe,
        schema=PROBE_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: TractivePlusConfigEntry
) -> bool:
    """Decharge Tractive Plus."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
