## 2025-02-17 - Home Assistant Config Flow Password Selectors & Binary Sensor Inactive Icons
**Learning:** Home Assistant config flow forms default to plaintext inputs unless `TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))` is explicitly declared. Additionally, binary sensors without explicit `icon_inactive` retain active icons even in `off` states.
**Action:** Always use `TextSelector` with `TextSelectorType.PASSWORD` for sensitive credential fields in config flows and ensure binary sensors have matching active/inactive icon pairs (`icon` and `icon_inactive`).

## 2026-10-31 - Installation count icons
**Learning:** Generation and storage installation counts need distinct icons for zero and positive counts. Missing coordinator data or electricity connections produce unknown counts and must not select the zero-count icon.
**Action:** Use catalog-verified outlined icons for known zero installation counts and retain the default icon for unknown counts. Keep this behavior scoped to the generation and storage descriptions that define `icon_inactive`, and test every selected icon against the pinned MDI catalog.

## 2026-10-31 - External service credential autocomplete
**Learning:** Typed email/password selectors can request `autocomplete="off"` without advertising origin-login autofill. Browsers and password managers can override this hint, so it does not provide credential isolation.
**Action:** Follow the detailed credential-selector guidance in [AGENTS.md](../AGENTS.md), including its browser-override limitation.
