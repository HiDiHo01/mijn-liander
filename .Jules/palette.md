## 2025-02-17 - Home Assistant Config Flow Password Selectors & Binary Sensor Inactive Icons
**Learning:** Home Assistant config flow forms default to plaintext inputs unless `TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))` is explicitly declared. Additionally, binary sensors without explicit `icon_inactive` retain active icons even in `off` states.
**Action:** Always use `TextSelector` with `TextSelectorType.PASSWORD` for sensitive credential fields in config flows and ensure binary sensors have matching active/inactive icon pairs (`icon` and `icon_inactive`).

## 2026-10-31 - Installation count icons
**Learning:** Generation and storage installation counts need distinct icons for zero and positive counts. Missing coordinator data or electricity connections produce unknown counts and must not select the zero-count icon.
**Action:** Use catalog-verified outlined icons for known zero installation counts and retain the default icon for unknown counts. Keep this behavior scoped to the generation and storage descriptions that define `icon_inactive`, and test every selected icon against the pinned MDI catalog.

## 2026-10-31 - External service credential autocomplete
**Learning:** Typed email/password selectors can request `autocomplete="off"` without advertising origin-login autofill. Browsers and password managers can override this hint, so it does not provide credential isolation.
**Action:** Follow the detailed credential-selector guidance in [AGENTS.md](../AGENTS.md), including its browser-override limitation.

## 2026-11-01 - Config Flow Numeric Selectors
**Learning:** Using raw Voluptuous integer validators in Home Assistant config flow schemas renders generic unassisted text inputs. Providing a typed `NumberSelector` with `min`, `max`, `step`, `unit_of_measurement`, and `NumberSelectorMode.BOX` provides immediate visual bounds, proper units, and spin controls in the UI while retaining backend schema validation.
**Action:** Declare `NumberSelector` for numeric parameters in config and options flows, specifying `min`, `max`, `step`, and `unit_of_measurement` to guide users with clear limits and units.

## 2026-11-02 - Monetary Sensor Display Precision
**Learning:** Home Assistant does not define a default display precision in `UNITS_PRECISION` for `SensorDeviceClass.MONETARY`. Without an explicit `suggested_display_precision`, currency sensors display varying or unpadded decimal places (e.g. `€8.1` or `€500.0` instead of standard currency formats like `€8.10` or `€500.00`). Specifying `suggested_display_precision=2` ensures numbers with currency units cleanly format to two decimal places by default in frontend cards while still allowing user customization in entity settings.
**Action:** Always specify `suggested_display_precision=2` on `SensorEntityDescription` definitions that use `SensorDeviceClass.MONETARY` or currency units.
