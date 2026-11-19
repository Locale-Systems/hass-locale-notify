# Locale Notify

A Home Assistant integration that sends notifications to **people**, not
devices. Say who should hear about something: whoever is home, whoever is
away, or everyone. It finds the Companion apps each of those people is signed
in to and notifies them.

```yaml
# The washer finished: tell whoever is home, or everyone if nobody is.
- action: locale_notify.send
  data:
    who: home
    fallback: all
    title: Laundry
    message: Washer cycle finished
```

A phone or tablet counts as soon as someone signs in to the Companion app on
it. There are no lists of `notify.mobile_app_*` actions to maintain, and
nothing to edit or restart when someone gets a new phone.

## How people map to devices

Home Assistant already holds the link, but templates can't follow it:

1. Each **person** can be linked to a Home Assistant **user**: Settings →
   People → *person* → "Allow person to login".
2. When the Companion app is signed in, its registration records that user.
3. The app's notify action is named after the device name it registered
   with: `notify.mobile_app_<device name>`.

Locale Notify follows person → user → signed-in apps → notify actions every
time it sends, so the list is never stale. It does not use the person's
`device_trackers`, so presence can come from anything (Wi-Fi, GPS, BLE)
without affecting who gets notified.

Some things to know:

- **Shared devices.** Wall panels and kiosks should sign in as their own user,
  one that no person is linked to. They are then never notified.
- **People without a login** have no devices and are skipped (the response
  and log say so).
- **Device type** comes from the app registration. Apple devices are
  exact: iOS → `phone`, iPadOS → `tablet`, macOS → `computer`. Android does not
  report a form factor, so Android devices count as `phone`. Anything else
  (watchOS, unknown) is `other`.

## Actions

### `locale_notify.send`

| Field | Required | |
|---|---|---|
| `who` | yes | `home`, `away`, `all`, or one or more `person.*` entities. `away` is any state other than `home`, so zones (`Work`) count as away. |
| `fallback` | no | Who to notify instead when `who` reaches no devices, e.g. `all` when nobody is home. No default: without it, nothing is sent in that case. It uses the same `devices`. |
| `devices` | no | Device types to notify: `phone`, `tablet`, `computer`, `other`. Default: all of them (or the `devices` setting below). |
| `title` | no | |
| `message` | yes | |
| `data` | no | Passed through to the Companion app unchanged: actionable notifications, `tag`, `group`, `push` options and so on. |

The notifications go out in parallel. One device failing does not stop the
others. The call fails only when every device failed.

Asked for a response (`response_variable:` in an automation, or "Response"
in Developer Tools), it returns who it matched and what it sent:

```yaml
persons: [person.alice, person.bob]
targets:
  notify.mobile_app_alice_iphone: phone
  notify.mobile_app_bob_pixel: phone
skipped: {}          # person -> why nothing was sent to them
missing: []          # signed-in apps with no notify action
used_fallback: false
failed: {}           # notify action -> error
```

### `locale_notify.targets`

Takes `who` and `devices` like `send`, sends nothing, and returns the same
report plus the device types used. Use it to check who a call would reach,
or to work out why someone didn't get a notification.

## More examples

```yaml
# Doors unlocked and nobody home: every phone and tablet.
- action: locale_notify.send
  data:
    who: all
    title: Security
    message: Front door is unlocked and nobody is home

# Side gate opened: phones only.
- action: locale_notify.send
  data:
    who: all
    devices: [phone]
    title: Side Gate
    message: "Entry: {{ actor }}"

# One person, wherever they are.
- action: locale_notify.send
  data:
    who: person.alice
    message: Your package was delivered
```

## Setup

1. Install it:
   - **With HACS:** HACS → ⋮ → Custom repositories → add
     `https://github.com/Locale-Systems/hass-locale-notify` as type
     **Integration**, then find **Locale Notify** and download it.
   - **By hand:** copy `custom_components/locale_notify` from the
     [latest release](https://github.com/Locale-Systems/hass-locale-notify/releases/latest)
     into your Home Assistant `config/custom_components/`.
2. Add to `configuration.yaml`:

   ```yaml
   locale_notify:
   ```

   To change the default device types for calls that don't name any:

   ```yaml
   locale_notify:
     devices: [phone]
   ```

3. Restart Home Assistant.
4. Check it in Developer Tools → Actions: run `locale_notify.targets` with
   `who: all`. Every person's signed-in devices should be listed.

## Development

```bash
uv venv --python 3.14 .venv
uv pip install --python .venv/bin/python -r requirements-dev.txt
.venv/bin/python -m pytest -q
```

The tests run against Home Assistant 2026.10, pinned through
`pytest-homeassistant-custom-component` in `requirements-dev.txt`.
`resolve.py` has no Home Assistant imports, so the matching logic can also be
tested on its own.

The icon is drawn by `tools/draw_icon.py`.

### Releasing

Bump `version` in `custom_components/locale_notify/manifest.json` on master,
then push a matching tag (`git tag v0.2.0 && git push origin v0.2.0`). The
Release workflow checks the tag matches the manifest, runs the tests and
publishes the GitHub release that HACS offers as an update.

## License

MIT. See [LICENSE](LICENSE).
