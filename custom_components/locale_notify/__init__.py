"""Notify people (not devices) via the Companion apps they are signed in to."""

from __future__ import annotations

import asyncio
import logging

import voluptuous as vol

from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import slugify

from .resolve import DEVICE_TYPES, GROUPS, resolve_who

_LOGGER = logging.getLogger(__name__)

DOMAIN = "locale_notify"
CONF_DEVICES = "devices"
DEFAULT_DEVICES = list(DEVICE_TYPES)  # every device unless narrowed

DEVICES = vol.All(cv.ensure_list, [vol.In(DEVICE_TYPES)], vol.Length(min=1))
WHO = vol.Any(vol.In(GROUPS), cv.entities_domain("person"))

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Any(
            None,
            vol.Schema({vol.Optional(CONF_DEVICES, default=DEFAULT_DEVICES): DEVICES}),
        )
    },
    extra=vol.ALLOW_EXTRA,
)

SEND_SCHEMA = vol.Schema(
    {
        vol.Required("who"): WHO,
        vol.Optional("fallback"): WHO,
        vol.Optional(CONF_DEVICES): DEVICES,
        vol.Required("message"): cv.string,
        vol.Optional("title"): cv.string,
        vol.Optional("data"): dict,
    }
)

TARGETS_SCHEMA = vol.Schema(
    {vol.Required("who"): WHO, vol.Optional(CONF_DEVICES): DEVICES}
)


def _report(res) -> dict:
    return {
        "persons": res.persons,
        "targets": {f"notify.{t}": kind for t, kind in res.targets.items()},
        "skipped": res.skipped,
        "missing": res.missing,
    }


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    conf = config.get(DOMAIN) or {}
    default_devices = conf.get(CONF_DEVICES, DEFAULT_DEVICES)

    def _resolve(who, devices):
        return resolve_who(
            who,
            hass.states.async_all("person"),
            hass.config_entries.async_entries("mobile_app"),
            slugify,
            lambda action: hass.services.has_service("notify", action),
            devices,
        )

    async def _send(call: ServiceCall) -> ServiceResponse:
        who = call.data["who"]
        devices = call.data.get(CONF_DEVICES, default_devices)
        res = _resolve(who, devices)
        used_fallback = False
        if not res.targets and "fallback" in call.data:
            used_fallback = True
            res = _resolve(call.data["fallback"], devices)

        payload = {"message": call.data["message"]}
        if "title" in call.data:
            payload["title"] = call.data["title"]
        if "data" in call.data:
            payload["data"] = call.data["data"]

        targets = list(res.targets)
        results = await asyncio.gather(
            *(
                hass.services.async_call("notify", t, payload, blocking=True)
                for t in targets
            ),
            return_exceptions=True,
        )
        failed = {}
        for target, result in zip(targets, results):
            if isinstance(result, Exception):
                failed[f"notify.{target}"] = str(result)
                _LOGGER.warning("notify.%s failed: %s", target, result)

        _LOGGER.info(
            "send who=%s%s devices=%s persons=%s targets=%s skipped=%s",
            who,
            f" (fallback {call.data['fallback']})" if used_fallback else "",
            devices,
            res.persons,
            res.targets,
            res.skipped,
        )
        if res.missing:
            _LOGGER.warning(
                "signed-in apps with no notify action (skipped): %s", res.missing
            )

        if targets and len(failed) == len(targets):
            raise HomeAssistantError(f"every notification failed: {failed}")

        if not call.return_response:
            return None
        return {**_report(res), "used_fallback": used_fallback, "failed": failed}

    async def _targets(call: ServiceCall) -> ServiceResponse:
        devices = call.data.get(CONF_DEVICES, default_devices)
        return {**_report(_resolve(call.data["who"], devices)), "devices": devices}

    hass.services.async_register(
        DOMAIN, "send", _send, schema=SEND_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN, "targets", _targets, schema=TARGETS_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    _LOGGER.info("default devices: %s", default_devices)
    return True
