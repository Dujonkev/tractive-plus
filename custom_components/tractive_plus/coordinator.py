"""Coordinateur Tractive Plus : interroge les endpoints ignores par le core."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, SLOW_EVERY, TRACTIVE_DOMAIN, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)


def resolve_tractive(hass: HomeAssistant) -> tuple[Any, Any]:
    """Retourne (api, tractive_data) depuis l'entree Tractive officielle."""
    for entry in hass.config_entries.async_entries(TRACTIVE_DOMAIN):
        data = getattr(entry, "runtime_data", None)
        if data is None:
            continue
        api = data.client._client._api
        return api, data
    raise UpdateFailed("L'integration Tractive n'est pas chargee")


class TractivePlusCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Recupere les donnees Tractive non exposees par le composant officiel."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialise le coordinateur."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
            config_entry=entry,
        )
        self._cycle = 0
        self._cache: dict[str, Any] = {}

    async def request(self, uri: str, aps: bool = False) -> Any:
        """Appel brut a l'API Tractive."""
        api, _ = resolve_tractive(self.hass)
        kwargs: dict[str, Any] = {}
        if aps:
            kwargs["base_url"] = api.APS_API_URL
        return await api.request(uri, **kwargs)

    async def _safe(self, uri: str, aps: bool = False) -> Any:
        try:
            return await self.request(uri, aps=aps)
        except Exception as err:
            _LOGGER.debug("Endpoint %s indisponible: %s", uri, err)
            return None

    async def _slow_tracker_data(self, tracker_id: str, user_id: str) -> None:
        """Donnees peu changeantes : details, abonnement, zones."""
        self._cache["details_%s" % tracker_id] = await self._safe(
            "tracker/%s" % tracker_id
        )

        sub = None
        for item in await self._safe("user/%s/subscriptions" % user_id) or []:
            detail = await self._safe("subscription/%s" % item["_id"])
            if detail and detail.get("tracker_id") in (None, tracker_id):
                sub = detail
                break
        self._cache["sub_%s" % tracker_id] = sub

        self._cache["gf_ids_%s" % tracker_id] = [
            g["_id"] for g in await self._safe("tracker/%s/geofences" % tracker_id) or []
        ]

        zones: dict[str, Any] = {}
        for zone in await self._safe("tracker/%s/power_saving_zones" % tracker_id) or []:
            detail = await self._safe("power_saving_zone/%s" % zone["_id"])
            if detail:
                zones[zone["_id"]] = detail
        self._cache["psz_%s" % tracker_id] = zones

    async def _async_update_data(self) -> dict[str, Any]:
        _api, tdata = resolve_tractive(self.hass)
        user_id = tdata.client.user_id
        slow = self._cycle % SLOW_EVERY == 0
        self._cycle += 1

        out: dict[str, Any] = {"trackers": {}, "pets": {}}

        for item in tdata.trackables:
            tracker_id = item.tracker_details["_id"]
            pet_id = item.trackable["_id"]

            if slow or "details_%s" % tracker_id not in self._cache:
                await self._slow_tracker_data(tracker_id, user_id)

            hw = await self._safe("device_hw_report/%s/" % tracker_id)
            pos = await self._safe("device_pos_report/%s" % tracker_id)

            geofences: dict[str, Any] = {}
            for gid in self._cache.get("gf_ids_%s" % tracker_id, []):
                detail = await self._safe("geofence/%s" % gid)
                if detail and not detail.get("deleted_at"):
                    geofences[gid] = detail

            out["trackers"][tracker_id] = {
                "hw": hw or {},
                "pos": pos or {},
                "details": self._cache.get("details_%s" % tracker_id) or {},
                "subscription": self._cache.get("sub_%s" % tracker_id) or {},
                "geofences": geofences,
                "psz": self._cache.get("psz_%s" % tracker_id) or {},
            }

            overview = await self._safe("pet/%s/health/overview" % pet_id, aps=True)
            overview = (overview or {}).get("content", overview) or {}

            out["pets"][pet_id] = {
                "overview": overview,
                "trackable": item.trackable,
            }

        return out

    def geofences(self, tracker_id: str) -> dict[str, Any]:
        """Liste des cloture virtuelles connues pour un tracker."""
        return (self.data or {}).get("trackers", {}).get(tracker_id, {}).get(
            "geofences", {}
        )
