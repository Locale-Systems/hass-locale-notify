"""Device classification and the person -> app matching, without Home Assistant."""

from __future__ import annotations

from types import SimpleNamespace as NS

import pytest

from custom_components.locale_notify.resolve import classify, resolve_who


@pytest.mark.parametrize(
    ("os_name", "model", "kind"),
    [
        ("iOS", "iPhone18,2", "phone"),
        ("iPadOS", "iPad15,3", "tablet"),
        ("iOS", "iPad8,1", "tablet"),  # iPads before iPadOS reported iOS
        ("macOS", "MacBookPro18,3", "computer"),
        ("Android", "Pixel 9", "phone"),  # Android reports no form factor
        ("watchOS", "Watch7,1", "other"),
        (None, None, "other"),
    ],
)
def test_classify(os_name, model, kind) -> None:
    assert classify({"os_name": os_name, "model": model}) == kind


def _slug(s: str) -> str:
    return s.lower().replace(" ", "_")


def _entry(user_id, name, os_name="iOS", model="iPhone18,2", disabled=None):
    return NS(
        data={"user_id": user_id, "device_name": name, "os_name": os_name, "model": model},
        disabled_by=disabled,
    )


def test_targets_keep_order_and_are_not_repeated() -> None:
    people = [
        NS(entity_id="person.a", state="home", attributes={"user_id": "u"}),
        NS(entity_id="person.a2", state="home", attributes={"user_id": "u"}),
    ]
    entries = [_entry("u", "B Phone"), _entry("u", "A Phone")]
    res = resolve_who("all", people, entries, _slug, lambda a: True)
    assert list(res.targets) == ["mobile_app_b_phone", "mobile_app_a_phone"]


def test_registration_without_a_device_name_is_ignored() -> None:
    people = [NS(entity_id="person.a", state="home", attributes={"user_id": "u"})]
    entries = [NS(data={"user_id": "u"}, disabled_by=None)]
    res = resolve_who("all", people, entries, _slug, lambda a: True)
    assert res.targets == {}
    assert res.skipped == {"person.a": "no signed-in Companion app with push"}
