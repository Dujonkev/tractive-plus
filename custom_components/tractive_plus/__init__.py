"""Tractive Plus : capteurs Tractive supplementaires."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.service import async_register_admin_service
from homeassistant.helpers.typing import ConfigType

from .api import TractivePlusError
from .const import DOMAIN
from .coordinator import TractivePlusCoordinator

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type TractivePlusConfigEntry = ConfigEntry[TractivePlusCoordinator]

PROBE_SCHEMA = vol.Schema(
    {
        vol.Required("path"): cv.string,
        vol.Optional("aps", default=False): cv.boolean,
        vol.Optional("config_entry_id"): cv.string,
    }
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Enregistre le service probe (reserve aux administrateurs)."""

    async def _probe(call: ServiceCall) -> dict[str, Any]:
        """Interroge un endpoint Tractive et renvoie la reponse (jamais journalisee)."""
        entry_id = call.data.get("config_entry_id")
        entries = [
            e
            for e in hass.config_entries.async_entries(DOMAIN)
            if e.state is ConfigEntryState.LOADED
            and (entry_id is None or e.entry_id == entry_id)
        ]
        if not entries:
            raise HomeAssistantError("Aucune entrée Tractive Plus chargée")
        coordinator: TractivePlusCoordinator = entries[0].runtime_data
        path = call.data["path"]
        try:
            result = await coordinator.request(path, aps=call.data["aps"])
        except TractivePlusError as err:
            raise HomeAssistantError(
                f"Appel à l'endpoint Tractive « {path} » impossible : {err}"
            ) from err
        return {"result": result}

    async_register_admin_service(
        hass,
        DOMAIN,
        "probe",
        _probe,
        schema=PROBE_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: TractivePlusConfigEntry
) -> bool:
    """Configure Tractive Plus."""
    if CONF_EMAIL not in entry.data or CONF_PASSWORD not in entry.data:
        # Entree creee par une version < 0.3.0 (sans identifiants) :
        # Home Assistant propose alors de saisir les identifiants Tractive.
        raise ConfigEntryAuthFailed("Identifiants Tractive requis")

    coordinator = TractivePlusCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: TractivePlusConfigEntry
) -> bool:
    """Decharge Tractive Plus."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
