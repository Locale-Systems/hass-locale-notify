"""The actions, loaded into Home Assistant and called the way an automation would."""

from __future__ import annotations

import pytest
import voluptuous as vol

from homeassistant.config_entries import ConfigEntryDisabler
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from .conftest import (
    ALICE_PHONE,
    ALICE_TABLET,
    BOB_PHONE,
    DOMAIN,
    KIOSK,
    Household,
    send,
    setup,
)


async def test_all_reaches_every_device_of_every_person(
    hass: HomeAssistant, household: Household
) -> None:
    await setup(hass)
    res = await send(hass, who="all")
    assert household.reached() == {ALICE_PHONE, ALICE_TABLET, BOB_PHONE}
    assert res["targets"] == {
        f"notify.{ALICE_PHONE}": "phone",
        f"notify.{ALICE_TABLET}": "tablet",
        f"notify.{BOB_PHONE}": "phone",
    }


async def test_kiosk_user_without_a_person_is_never_notified(
    hass: HomeAssistant, household: Household
) -> None:
    await setup(hass)
    await send(hass, who="all")
    assert household.sent[KIOSK] == []


async def test_home_skips_people_who_are_away(
    hass: HomeAssistant, household: Household
) -> None:
    household.person("bob", "not_home", "u-bob")
    await setup(hass)
    await send(hass, who="home")
    assert household.reached() == {ALICE_PHONE, ALICE_TABLET}


async def test_a_zone_counts_as_away(hass: HomeAssistant, household: Household) -> None:
    household.person("bob", "Work", "u-bob")
    await setup(hass)
    await send(hass, who="away")
    assert household.reached() == {BOB_PHONE}


async def test_devices_narrows_to_phones(
    hass: HomeAssistant, household: Household
) -> None:
    await setup(hass)
    await send(hass, who="all", devices=["phone"])
    assert household.reached() == {ALICE_PHONE, BOB_PHONE}


async def test_configured_default_devices_apply_when_a_call_names_none(
    hass: HomeAssistant, household: Household
) -> None:
    await setup(hass, {"devices": ["tablet"]})
    await send(hass, who="all")
    assert household.reached() == {ALICE_TABLET}


async def test_a_call_overrides_the_configured_default(
    hass: HomeAssistant, household: Household
) -> None:
    await setup(hass, {"devices": ["tablet"]})
    await send(hass, who="all", devices=["phone"])
    assert household.reached() == {ALICE_PHONE, BOB_PHONE}


async def test_fallback_used_only_when_who_reaches_nobody(
    hass: HomeAssistant, household: Household
) -> None:
    household.person("alice", "not_home", "u-alice")
    household.person("bob", "not_home", "u-bob")
    await setup(hass)
    res = await send(hass, who="home", fallback="all", devices=["phone"])
    assert res["used_fallback"] is True
    assert household.reached() == {ALICE_PHONE, BOB_PHONE}


async def test_fallback_ignored_when_who_reaches_someone(
    hass: HomeAssistant, household: Household
) -> None:
    household.person("bob", "not_home", "u-bob")
    await setup(hass)
    res = await send(hass, who="home", fallback="all")
    assert res["used_fallback"] is False
    assert BOB_PHONE not in household.reached()


async def test_nobody_matched_and_no_fallback_sends_nothing(
    hass: HomeAssistant, household: Household
) -> None:
    household.person("alice", "not_home", "u-alice")
    household.person("bob", "not_home", "u-bob")
    await setup(hass)
    res = await send(hass, who="home")
    assert res["targets"] == {}
    assert household.reached() == set()


async def test_explicit_people_and_an_unknown_one(
    hass: HomeAssistant, household: Household
) -> None:
    await setup(hass)
    res = await send(hass, who=["person.bob", "person.carol"])
    assert household.reached() == {BOB_PHONE}
    assert res["skipped"] == {"person.carol": "no such person"}


async def test_person_without_a_login_is_reported(
    hass: HomeAssistant, household: Household
) -> None:
    household.person("guest", "home", None)
    await setup(hass)
    res = await send(hass, who="home")
    assert res["skipped"] == {"person.guest": "person has no linked user"}
    assert household.reached() == {ALICE_PHONE, ALICE_TABLET, BOB_PHONE}


async def test_app_without_a_notify_action_is_reported_and_others_still_sent(
    hass: HomeAssistant, household: Household
) -> None:
    hass.services.async_remove("notify", ALICE_TABLET)
    del household.sent[ALICE_TABLET]
    await setup(hass)
    res = await send(hass, who="all")
    assert res["missing"] == [ALICE_TABLET]
    assert household.reached() == {ALICE_PHONE, BOB_PHONE}


async def test_message_title_and_data_pass_through(
    hass: HomeAssistant, household: Household
) -> None:
    await setup(hass)
    data = {"push": {"interruption-level": "time-sensitive"}, "tag": "washer"}
    await send(hass, who=["person.bob"], title="Laundry", message="Done", data=data)
    assert household.sent[BOB_PHONE] == [
        {"title": "Laundry", "message": "Done", "data": data}
    ]


async def test_one_failing_device_does_not_stop_the_others(
    hass: HomeAssistant, household: Household
) -> None:
    household.failing.add(ALICE_PHONE)
    await setup(hass)
    res = await send(hass, who="all")
    assert set(res["failed"]) == {f"notify.{ALICE_PHONE}"}
    assert household.reached() == {ALICE_TABLET, BOB_PHONE}


async def test_every_device_failing_raises(
    hass: HomeAssistant, household: Household
) -> None:
    household.failing.update({ALICE_PHONE, ALICE_TABLET, BOB_PHONE})
    await setup(hass)
    with pytest.raises(HomeAssistantError, match="every notification failed"):
        await send(hass, who="all")


async def test_send_works_without_asking_for_a_response(
    hass: HomeAssistant, household: Household
) -> None:
    await setup(hass)
    await hass.services.async_call(
        DOMAIN, "send", {"who": "home", "message": "hi"}, blocking=True
    )
    assert household.reached() == {ALICE_PHONE, ALICE_TABLET, BOB_PHONE}


async def test_targets_sends_nothing(hass: HomeAssistant, household: Household) -> None:
    await setup(hass)
    res = await hass.services.async_call(
        DOMAIN, "targets", {"who": "all", "devices": ["tablet"]},
        blocking=True, return_response=True,
    )
    assert res["targets"] == {f"notify.{ALICE_TABLET}": "tablet"}
    assert res["skipped"] == {"person.bob": "signed-in apps are not tablet"}
    assert household.reached() == set()


async def test_disabled_registration_is_ignored(
    hass: HomeAssistant, household: Household
) -> None:
    entry = next(
        e for e in hass.config_entries.async_entries("mobile_app")
        if e.data["device_name"] == "Alice iPad"
    )
    await hass.config_entries.async_set_disabled_by(
        entry.entry_id, ConfigEntryDisabler.USER
    )
    await setup(hass)
    await send(hass, who="all")
    assert household.reached() == {ALICE_PHONE, BOB_PHONE}


@pytest.mark.parametrize(
    "data",
    [
        {"who": "everyone"},
        {"who": "light.kitchen"},
        {"who": "all", "devices": ["watch"]},
        {"who": "all", "devices": []},
    ],
)
async def test_invalid_calls_are_refused(
    hass: HomeAssistant, household: Household, data: dict
) -> None:
    await setup(hass)
    with pytest.raises((vol.Invalid, ServiceValidationError)):
        await send(hass, **data)
    assert household.reached() == set()


async def test_invalid_yaml_devices_fails_setup(hass: HomeAssistant) -> None:
    from homeassistant.setup import async_setup_component

    assert not await async_setup_component(hass, DOMAIN, {DOMAIN: {"devices": ["watch"]}})
