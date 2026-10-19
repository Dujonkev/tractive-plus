"""Coordinateur Tractive Plus : interroge les endpoints ignores par le core."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import TractivePlusApi, TractivePlusAuthError, TractivePlusError
from .const import DOMAIN, SLOW_EVERY, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)


class TractivePlusCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Recupere les donnees Tractive non exposees par le composant officiel."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialise le coordinateur."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
            config_entry=entry,
        )
        self.api = TractivePlusApi(
            async_get_clientsession(hass),
            entry.data[CONF_EMAIL],
            entry.data[CONF_PASSWORD],
        )
        self._cycle = 0
        self._cache: dict[str, Any] = {}
        self._trackables: list[dict[str, Any]] | None = None

    async def request(self, uri: str, aps: bool = False) -> Any:
        """Appel brut a l'API Tractive avec la session de Tractive Plus."""
        return await self.api.request(uri, aps=aps)

    async def _safe(self, uri: str, aps: bool = False) -> Any:
        """Appel tolerant : None si l'endpoint echoue (sauf erreur d'auth)."""
        try:
            return await self.request(uri, aps=aps)
        except TractivePlusAuthError:
            raise
        except TractivePlusError as err:
            _LOGGER.debug("Endpoint %s indisponible: %s", uri, err)
            return None

    async def _fetch_trackables(self, user_id: str) -> list[dict[str, Any]]:
        """Animaux du compte ayant un tracker associe."""
        trackables: list[dict[str, Any]] = []
        for obj in await self.request("user/%s/trackable_objects" % user_id) or []:
            pet = await self._safe("trackable_object/%s" % obj["_id"])
            if not pet or not pet.get("device_id") or not pet.get("details"):
                continue
            trackables.append({"pet": pet, "tracker_id": pet["device_id"]})
        return trackables

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
        try:
            return await self._update()
        except TractivePlusAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except TractivePlusError as err:
            raise UpdateFailed(str(err)) from err

    async def _update(self) -> dict[str, Any]:
        user_id = await self.api.user_id()

        slow = self._cycle % SLOW_EVERY == 0
        self._cycle += 1

        if slow or self._trackables is None:
            self._trackables = await self._fetch_trackables(user_id)

        out: dict[str, Any] = {"trackers": {}, "pets": {}}

        for item in self._trackables:
            tracker_id = item["tracker_id"]
            pet = item["pet"]
            pet_id = pet["_id"]

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
                "pet_id": pet_id,
                "pet_name": (pet.get("details") or {}).get("name"),
            }

            overview = await self._safe("pet/%s/health/overview" % pet_id, aps=True)
            overview = (overview or {}).get("content", overview) or {}

            out["pets"][pet_id] = {
                "overview": overview,
                "trackable": pet,
                "tracker_id": tracker_id,
            }

        return out

    def device_info(self, tracker_id: str) -> DeviceInfo:
        """Appareil Tractive Plus (un par tracker, nomme d'apres l'animal)."""
        tracker = (self.data or {}).get("trackers", {}).get(tracker_id, {})
        details = tracker.get("details") or {}
        return DeviceInfo(
            identifiers={(DOMAIN, tracker_id)},
            name=tracker.get("pet_name") or "Tracker %s" % tracker_id,
            manufacturer="Tractive",
            model=details.get("model_number") or details.get("hw_edition"),
            sw_version=details.get("fw_version"),
            serial_number=tracker_id,
        )

    def pet_tracker_id(self, pet_id: str) -> str | None:
        """Tracker associe a un animal."""
        return (self.data or {}).get("pets", {}).get(pet_id, {}).get("tracker_id")

    def geofences(self, tracker_id: str) -> dict[str, Any]:
        """Liste des cloture virtuelles connues pour un tracker."""
        return (self.data or {}).get("trackers", {}).get(tracker_id, {}).get(
            "geofences", {}
        )
