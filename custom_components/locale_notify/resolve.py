"""Resolve people to Companion-app notify actions.

Kept free of Home Assistant imports (slugify is passed in) so the logic can be
exercised outside HA.

Chain: person state -> attributes.user_id -> mobile_app config entries whose
data.user_id matches -> notify action "mobile_app_<slugify(device_name)>",
which is how mobile_app names its legacy notify targets.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Iterable

GROUPS = ("home", "away", "all")
DEVICE_TYPES = ("phone", "tablet", "computer", "other")


def classify(data: dict) -> str:
    """Device type from a mobile_app registration.

    Apple is exact (os_name iOS / iPadOS / macOS, confirmed by the model
    prefix). Android reports no form factor, so it counts as a phone.
    """
    os_name = (data.get("os_name") or "").lower()
    model = (data.get("model") or "").lower()
    if os_name == "ipados" or model.startswith("ipad"):
        return "tablet"
    if os_name == "ios" or model.startswith("iphone"):
        return "phone"
    if os_name == "macos" or model.startswith("mac"):
        return "computer"
    if os_name == "android":
        return "phone"
    return "other"


@dataclass
class Resolution:
    persons: list[str] = field(default_factory=list)
    # notify action (without "notify.") -> device type, in send order
    targets: dict[str, str] = field(default_factory=dict)
    # person entity_id -> reason nothing was found for them
    skipped: dict[str, str] = field(default_factory=dict)
    # registrations whose notify action does not exist (no push support,
    # or mobile_app's naming changed upstream)
    missing: list[str] = field(default_factory=list)


def select_persons(who: str | list[str], person_states: Iterable) -> list:
    """Pick person states by group name or explicit entity ids."""
    states = list(person_states)
    if isinstance(who, str) and who in GROUPS:
        if who == "all":
            return states
        if who == "home":
            return [s for s in states if s.state == "home"]
        # away: anything that isn't home -- zones, not_home, unknown
        return [s for s in states if s.state != "home"]
    wanted = [who] if isinstance(who, str) else list(who)
    by_id = {s.entity_id: s for s in states}
    return [by_id[e] for e in wanted if e in by_id]


def resolve(
    persons: Iterable,
    mobile_app_entries: Iterable,
    slugify: Callable[[str], str],
    has_notify: Callable[[str], bool],
    devices: Iterable[str] = DEVICE_TYPES,
) -> Resolution:
    """Map person states to the notify actions of their signed-in apps."""
    wanted = set(devices)
    entries = [e for e in mobile_app_entries if not getattr(e, "disabled_by", None)]
    out = Resolution()
    for person in persons:
        out.persons.append(person.entity_id)
        user_id = person.attributes.get("user_id")
        if not user_id:
            out.skipped[person.entity_id] = "person has no linked user"
            continue
        signed_in = filtered = 0
        for entry in entries:
            if entry.data.get("user_id") != user_id:
                continue
            name = entry.data.get("device_name")
            if not name:
                continue
            action = f"mobile_app_{slugify(name)}"
            if not has_notify(action):
                if action not in out.missing:
                    out.missing.append(action)
                continue
            signed_in += 1
            kind = classify(entry.data)
            if kind not in wanted:
                filtered += 1
                continue
            out.targets.setdefault(action, kind)
        if signed_in == 0:
            out.skipped[person.entity_id] = "no signed-in Companion app with push"
        elif signed_in == filtered:
            out.skipped[person.entity_id] = (
                f"signed-in apps are not {'/'.join(sorted(wanted))}"
            )
    return out


def resolve_who(
    who: str | list[str],
    person_states: Iterable,
    mobile_app_entries: Iterable,
    slugify: Callable[[str], str],
    has_notify: Callable[[str], bool],
    devices: Iterable[str] = DEVICE_TYPES,
) -> Resolution:
    """select_persons + resolve, recording explicit ids that don't exist."""
    states = list(person_states)
    out = resolve(
        select_persons(who, states), mobile_app_entries, slugify, has_notify, devices
    )
    if not (isinstance(who, str) and who in GROUPS):
        known = {s.entity_id for s in states}
        for eid in [who] if isinstance(who, str) else who:
            if eid not in known:
                out.skipped[eid] = "no such person"
    return out
