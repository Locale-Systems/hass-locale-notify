"""Fixtures: a household of people, their Companion-app registrations, and
notify actions that record what they were sent."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

DOMAIN = "locale_notify"

# user_id -> registrations (device_name, os_name, model)
APPS = {
    "u-alice": [
        ("Alice iPhone", "iOS", "iPhone18,2"),
        ("Alice iPad", "iPadOS", "iPad15,3"),
    ],
    "u-bob": [("Bob Pixel", "Android", "Pixel 9")],
    # A shared wall tablet signed in as its own user, which no person links to.
    "u-kiosk": [("Kitchen Kiosk", "iPadOS", "iPad14,1")],
}
ALICE_PHONE = "mobile_app_alice_iphone"
ALICE_TABLET = "mobile_app_alice_ipad"
BOB_PHONE = "mobile_app_bob_pixel"
KIOSK = "mobile_app_kitchen_kiosk"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Load integrations from custom_components."""


@dataclass
class Household:
    hass: HomeAssistant
    sent: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    failing: set[str] = field(default_factory=set)

    def person(self, name: str, state: str, user_id: str | None) -> None:
        attrs = {"user_id": user_id} if user_id else {}
        self.hass.states.async_set(f"person.{name}", state, attrs)

    def register_notify(self, action: str) -> None:
        self.sent[action] = []

        async def handler(call: ServiceCall) -> None:
            if action in self.failing:
                raise HomeAssistantError(f"{action} is unreachable")
            self.sent[action].append(dict(call.data))

        self.hass.services.async_register("notify", action, handler)

    def reached(self) -> set[str]:
        return {action for action, calls in self.sent.items() if calls}


@pytest.fixture
def household(hass: HomeAssistant) -> Household:
    """Alice and Bob home, every app registered with a working notify action."""
    h = Household(hass)
    for user_id, apps in APPS.items():
        for device_name, os_name, model in apps:
            MockConfigEntry(
                domain="mobile_app",
                title=device_name,
                data={
                    "user_id": user_id,
                    "device_name": device_name,
                    "os_name": os_name,
                    "model": model,
                },
            ).add_to_hass(hass)
    for action in (ALICE_PHONE, ALICE_TABLET, BOB_PHONE, KIOSK):
        h.register_notify(action)
    h.person("alice", "home", "u-alice")
    h.person("bob", "home", "u-bob")
    return h


async def setup(hass: HomeAssistant, conf: dict | None = None) -> None:
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: conf})
    await hass.async_block_till_done()


async def send(hass: HomeAssistant, **data: Any) -> dict:
    data.setdefault("message", "hello")
    return await hass.services.async_call(
        DOMAIN, "send", data, blocking=True, return_response=True
    )
