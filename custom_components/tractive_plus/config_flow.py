"""Config flow Tractive Plus."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import DOMAIN


class TractivePlusConfigFlow(ConfigFlow, domain=DOMAIN):
    """Flow minimal: aucune saisie, on reutilise la session Tractive existante."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Etape unique."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        if user_input is None:
            return self.async_show_form(step_id="user")
        return self.async_create_entry(title="Tractive Plus", data={})
