"""Config flow Tractive Plus."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import TractivePlusApi, TractivePlusAuthError, TractivePlusError
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

USER_SCHEMA = vol.Schema(
    {vol.Required(CONF_EMAIL): str, vol.Required(CONF_PASSWORD): str}
)


class TractivePlusConfigFlow(ConfigFlow, domain=DOMAIN):
    """Flow de configuration : identifiants Tractive propres a Tractive Plus."""

    VERSION = 1

    async def _validate(
        self, email: str, password: str, errors: dict[str, str]
    ) -> str | None:
        """Teste les identifiants et renvoie l'identifiant utilisateur Tractive."""
        api = TractivePlusApi(async_get_clientsession(self.hass), email, password)
        try:
            return await api.user_id()
        except TractivePlusAuthError:
            errors["base"] = "invalid_auth"
        except TractivePlusError:
            errors["base"] = "cannot_connect"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Erreur inattendue pendant la connexion Tractive")
            errors["base"] = "unknown"
        return None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Saisie des identifiants Tractive."""
        errors: dict[str, str] = {}
        if user_input is not None:
            user_id = await self._validate(
                user_input[CONF_EMAIL], user_input[CONF_PASSWORD], errors
            )
            if user_id:
                await self.async_set_unique_id(user_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input[CONF_EMAIL], data=user_input
                )
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(USER_SCHEMA, user_input),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Identifiants refuses (ou entree creee par une ancienne version)."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Redemande les identifiants Tractive."""
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()
        if user_input is not None:
            user_id = await self._validate(
                user_input[CONF_EMAIL], user_input[CONF_PASSWORD], errors
            )
            if user_id:
                # Les entrees creees avant la 0.3.0 ont DOMAIN comme unique_id.
                if entry.unique_id not in (None, DOMAIN, user_id):
                    return self.async_abort(reason="unique_id_mismatch")
                return self.async_update_reload_and_abort(
                    entry,
                    unique_id=user_id,
                    title=user_input[CONF_EMAIL],
                    data=user_input,
                )
        suggested = user_input or {CONF_EMAIL: entry.data.get(CONF_EMAIL, "")}
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=self.add_suggested_values_to_schema(USER_SCHEMA, suggested),
            errors=errors,
        )
