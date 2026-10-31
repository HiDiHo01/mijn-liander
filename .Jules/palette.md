## 2025-02-17 - Home Assistant Config Flow Password Selectors & Binary Sensor Inactive Icons
**Learning:** Home Assistant config flow forms default to plaintext inputs unless `TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))` is explicitly declared. Additionally, binary sensors without explicit `icon_inactive` retain active icons even in `off` states.
**Action:** Always use `TextSelector` with `TextSelectorType.PASSWORD` for sensitive credential fields in config flows and ensure binary sensors have matching active/inactive icon pairs (`icon` and `icon_inactive`).

## 2025-02-17 - External Service Config Flows and Autocomplete Isolation
**Learning:** Home Assistant config flows for external services run under Home Assistant's local origin. Using `autocomplete="username"` / `current-password"` can cause browsers or password managers to treat Home Assistant's origin as the login endpoint or misassociate credentials. Setting `autocomplete="off"` while preserving `type=TextSelectorType.EMAIL` and `PASSWORD` preserves mobile keyboard layouts and masking without requesting origin-login autofill.
**Action:** In external-service config flow credential selectors, retain typed selectors (`EMAIL`, `PASSWORD`) for keyboard/masking UX, but explicitly declare `autocomplete="off"` to prevent unintentional origin credential association.
