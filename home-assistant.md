# Home Assistant Integration Development Guide

This document defines project-specific engineering guidance for the Mijn Liander custom integration. Follow the repository's declared Python/Home Assistant compatibility and the current implementation; do not assume the latest upstream API is available unless the project supports it.

## Architecture

- Integration domain: `mijn_liander`.
- Integration display name: `Mijn Liander`.
- Integration type: cloud polling.
- Entry point: `custom_components/mijn_liander/`.
- Keep the existing config-flow and data-coordinator architecture.
- Use `ConfigEntry`-scoped runtime state. Store coordinator and client state under the corresponding `entry.entry_id`; never combine accounts or config entries.
- Reuse the coordinator's fetched data for entities. Do not create an API request per entity or add independent polling loops.
- Keep API access, parsing, coordination, entity descriptions, migration, and presentation responsibilities separated.

## Supported Python and Home Assistant APIs

- Use the Python version declared by repository metadata and CI. The current README's development instructions specify Python **3.14.2 or newer**; keep code and dependencies compatible with the project's actual CI runtime.
- Follow the Home Assistant version targeted by the current manifest, dependency lock, and CI. Check current upstream documentation or source when API behavior is uncertain.
- Use current config-entry APIs and entity properties. Avoid deprecated Home Assistant APIs and migration patterns.
- Use modern type annotations, including `X | None`, and built-in generic types such as `list[str]` and `dict[str, object]`. Do not import `List` or `Dict`.
- Avoid `Any` for untrusted or heterogeneous API payloads. Prefer `object` at unvalidated boundaries and narrow values with explicit runtime checks or typed parsing structures.
- Add type hints and meaningful docstrings to modules, classes, functions, and methods.
- Use `snake_case` consistently. Prefix class-internal helper methods with an underscore.
- Use two blank lines before top-level function definitions.
- Use lazy logging formatting: `_LOGGER.debug("Received %s records", count)`, not f-strings in logging calls.
- Avoid shadowing function parameters and outer-scope names with local variables.

## Asynchronous operation and lifecycle

- Use async APIs for network access and Home Assistant operations. Never perform blocking I/O on the event loop.
- Reuse Home Assistant's managed HTTP session (normally `async_get_clientsession(hass)`) where the integration's HTTP client needs one.
- Use `asyncio.timeout()` for timeout handling when compatible with the supported Python version; do not add `async_timeout` solely for this purpose.
- Use the existing coordinator's first-refresh and update lifecycle. Map connection and authentication failures to the appropriate Home Assistant errors so config flow and entity availability behave predictably.
- Register coordinator listeners, callbacks, and background tasks with clear lifecycle ownership. Remove listeners and cancel or clean up resources on unload.
- Ensure setup failure leaves no partially registered runtime data or listeners. Keep unload and reload behavior safe and repeatable.
- Do not create untracked background tasks where a Home Assistant task API or lifecycle-managed mechanism is appropriate.
- Avoid unnecessary refreshes and avoid blocking or long-running work in coordinator update callbacks.

## API data and error handling

- Treat all remote API data as untrusted. Validate mappings, lists, identifiers, timestamps, numeric values, and nullable fields before use.
- Distinguish a missing field from a legitimate `None`, zero, or empty collection where the API semantics require it.
- Avoid broad exception handling. Catch the narrowest practical exception types, preserve causes, and translate errors at the correct integration boundary.
- Do not silently swallow parsing errors or convert invalid data into plausible-looking measurements.
- Use actionable error messages without logging credentials, authentication headers, tokens, account identifiers, or unnecessary raw account payloads.
- Use timezone-aware datetimes and Home Assistant's timezone utilities where appropriate. Never introduce naive timestamps for UTC or local-time data.
- Do not compare floating-point measurements for exact equality. Use a tolerance or appropriate numeric comparison when equality is actually required.
- Keep unavailable data scoped to affected entities; a malformed optional field should not unnecessarily disable unrelated sensors.

## Entities and device registry

- Use stable unique IDs derived from stable API identifiers or established integration identity. Do not include mutable display names, current measurements, or other unstable values.
- Use correct `device_info` identifiers and valid `via_device` references. A referenced parent device must exist and belong to the appropriate config entry.
- Avoid accidental device merging across different config entries or accounts.
- Keep entity names, icons, units, device classes, state classes, and suggested display precision consistent with Home Assistant's entity model.
- Use native Home Assistant entity properties and enums where supported.
- Use `available` and native coordinator entity behavior consistently; do not hide permanent setup or authentication errors behind fabricated states.
- Only create gas entities when the account has an active gas contract.
- When gas-contract status changes, reload or update the relevant platforms safely. Remove only obsolete gas registry entries belonging to the relevant integration/config entry; never delete unrelated electricity entities or another account's entities.
- Test contract activation, contract removal, and config-entry reloads, including stale registry cases.

## Config flow, options, and migrations

- Validate user input and remote authentication responses before creating a config entry.
- Provide useful Home Assistant errors for invalid credentials, connection failures, rate limits, and unexpected API responses without exposing secrets.
- Prevent unintended duplicate config entries using the appropriate stable account identity when available.
- Keep options flow changes consistent with the coordinator and entity lifecycle. If an option changes coordinates, account context, or another identity-affecting value, do not leave stale identity or device metadata.
- Make migrations idempotent and safe when fields are absent or already migrated.
- Do not rename entity unique IDs without a deliberate migration plan and regression tests.
- Preserve compatibility with existing users and stored config entries.

## Tests and quality gates

Use the repository's current CI workflows and README as the source of truth for exact commands and dependency versions. The README currently documents:

```shell
python -m pip install --require-hashes --only-binary=:all: --no-binary=pyric -r requirements_test.txt
python -m pytest -q
python -m pip install ruff==0.16.10
ruff check --config ruff.toml custom_components/mijn_liander tests
```

- The dependency installation intentionally allows the hash-verified PyRIC source archive because PyRIC has no published wheel; do not remove hash verification or change this exception casually.
- Add focused regression tests for parsing, nullable fields, error mapping, migrations, entity identity, gas-contract behavior, and multiple config entries as applicable.
- Test negative and boundary cases, not only the happy path.
- Run HACS validation and Home Assistant `hassfest` when manifest metadata, translations, integration discovery, or packaging changes.
- Check translations for every user-visible string change.
- Run the relevant checks after edits and report results accurately. If checks cannot run, state which ones remain unverified.
- Keep the test suite deterministic; do not depend on live Liander credentials or production account data in ordinary unit tests.

## Privacy and diagnostics

- Treat energy consumption, meter readings, account details, and authentication data as sensitive.
- Never store credentials or real personal account responses in fixtures, test snapshots, logs, or documentation.
- Diagnostics must redact credentials, tokens, and personal identifiers and should expose only the minimum information needed for troubleshooting.
- Do not add telemetry or send account data to third parties.

## Reference documentation

- Home Assistant integration quality scale: https://developers.home-assistant.io/docs/quality_scale/
- Integration development checklist: https://developers.home-assistant.io/docs/core/integration-quality-scale/checklist/
- Config entries: https://developers.home-assistant.io/docs/config_entries_index/
- Data update coordinator: https://developers.home-assistant.io/docs/integration_fetching_data/
- Entity registry: https://developers.home-assistant.io/docs/entity_registry_index/
- HACS integration requirements: https://www.hacs.xyz/docs/publish/integration/
