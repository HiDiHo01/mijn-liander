# Mijn Liander

Home Assistant integration for Mijn Liander.

## Install via Home Assistant Marketplace

Starting with Home Assistant 2026.11, Mijn Liander can be installed from the built-in Marketplace. Use the button below to open the repository in your Home Assistant instance:

[![Open your Home Assistant instance and show the Mijn Liander repository in the Marketplace.](https://my.home-assistant.io/badges/marketplace_repository.svg)](https://my.home-assistant.io/redirect/marketplace_repository/?owner=HiDiHo01&repository=mijn-liander&category=integration)

If Mijn Liander is not yet in the public catalog, the Marketplace offers to add it as a custom repository. Confirm that step, then download the integration. Restart Home Assistant and go to **Settings > Devices & services > Add integration**, find **Mijn Liander**, and sign in with your Mijn Liander account.

For Home Assistant versions before 2026.11, install Mijn Liander through HACS. Use the [HACS repository link](https://my.home-assistant.io/redirect/hacs_repository/?owner=HiDiHo01&repository=mijn-liander&category=integration), or add `https://github.com/HiDiHo01/mijn-liander` manually under **HACS > Integrations > Custom repositories** with the **Integration** category. Download the integration and restart Home Assistant.

Gas entities are created only while the account has an active gas contract. If the contract is added or removed later, the integration refreshes its entities when the account data next updates.

The User device includes the combined Address sensor and separate Postal code,
Street, House number, House number addition, and City sensors. They share the
same account address and update with coordinator data. Missing or invalid fields
are unknown; an explicitly empty house number addition remains empty. House
numbers are text, preserving leading zeros.

You can add multiple Mijn Liander accounts by adding the integration again for each
email address. Each account has its own data and devices. The same email address
can only be configured once; capitalization and surrounding whitespace do not
create a separate account. Re-authentication renews credentials for the existing
account; add another integration entry to use a different email address.

Use your Mijn Liander credentials in the login fields. The integration requests
that automatic completion be disabled, but browsers and password managers can
override this request. Check that suggested credentials belong to Mijn Liander
before submitting the form.

The generation and storage installation sensors use outlined icons when their
count is zero and filled icons for positive counts. Unknown counts keep their
default icon. This visual distinction applies to these two installation sensors.

Maximum power and network costs accept decimal commas from Mijn Liander, such as
`8,1`, and expose numeric values to Home Assistant. Missing or invalid measurements
appear as unknown. Network costs default to two displayed decimals for currency
formatting. Maximum power defaults to one displayed decimal when its raw
API value contains a comma, and zero decimals otherwise. This display default
follows data updates and respects a display precision set by the user; it does not
round the underlying measurement.

Maximum gas capacity is an integer sensor in cubic meters per hour (`m³/h`),
displayed with zero decimals. It accepts decimal commas and truncates fractional
parts toward zero (`8,9` becomes `8`). Missing or invalid values remain unknown.

Additional sensors show electricity/gas meter types, contractless-case counts,
and total registered generation and solar-panel ratings in kW. Rating totals
require every installation to have a finite, non-negative value and a known kW
unit; incomplete data is unknown rather than a partial total. Explicitly empty
installation lists yield zero, while missing/malformed lists are unknown.
The generation-installation count also exposes the allowlisted registration,
inverter, source, identifier and rating fields in its `installations` attribute.
The feed-in start sensor is a timezone-aware timestamp.

Binary sensors initialize from the first API payload and update through one
coordinator listener. Explicit `false` remains off; absent/malformed flags are
unknown. The deprecated analog-meter binary sensor is removed, including its
existing registry entries. Binary attributes and debug logs no
longer duplicate raw account payloads or login credentials.

Registry migration uses Home Assistant's public entity-ID lookup. When both a
legacy and current unique ID exist for the same account, the current entry keeps
its entity ID, settings and device assignment; the redundant legacy entry is
removed. Inactive gas cleanup recognizes owned gas unique IDs even when their
device is missing or differs from the gas device. Entries from other config
entries and devices with remaining entities are preserved.

## Manual installation

1. Download the [latest version of this repository](https://github.com/HiDiHo01/mijn-liander/archive/refs/heads/main.zip).
2. Copy the `custom_components/mijn_liander` directory to `<config>/custom_components/mijn_liander` in Home Assistant.
3. Restart Home Assistant.
4. Add **Mijn Liander** through **Settings > Devices & services > Add integration** and sign in with your Mijn Liander account.

## Development checks

CI validates HACS metadata, Home Assistant integration metadata and translations
(hassfest), Python lint, and the regression tests. HACS requires the repository
to have the `home-assistant` topic.

With Python 3.14.2 or newer, install the locked test dependencies and run the tests:

```shell
bash .github/scripts/install-test-dependencies.sh
python -m pytest -q
```

The shared installer keeps binary-only installation as the default and explicitly allows hash-verified source distributions for PyRIC and mock-open. The dependency-update workflows run the same installer after compiling the lock file, so an unexpected source-only dependency fails validation before a pull request is created.
To run the lint check, install Ruff 0.16.10 with `python -m pip install ruff==0.16.10` and run `ruff check --config ruff.toml custom_components/mijn_liander tests`.
To update the dependency lock, edit `requirements_test.in` and run the `uv pip compile`
command recorded at the top of `requirements_test.txt`.
