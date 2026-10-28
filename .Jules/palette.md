## 2025-02-17 - Home Assistant Config Flow Password Selectors & Binary Sensor Inactive Icons
**Learning:** Home Assistant config flow forms default to plaintext inputs unless `TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))` is explicitly declared. Additionally, binary sensors without explicit `icon_inactive` retain active icons even in `off` states.
**Action:** Always use `TextSelector` with `TextSelectorType.PASSWORD` for sensitive credential fields in config flows and ensure binary sensors have matching active/inactive icon pairs (`icon` and `icon_inactive`).

## 2025-05-18 - Home Assistant Config Flow Email & Autocomplete Selectors
**Learning:** Home Assistant `TextSelectorConfig` supports `type=TextSelectorType.EMAIL` and `autocomplete` parameters (`username`, `current-password`), enabling mobile virtual keyboards (@ key) and credential manager integration in config flows.
**Action:** Always configure `TextSelector(TextSelectorConfig(type=TextSelectorType.EMAIL, autocomplete="username"))` for email fields in config flows alongside password autocomplete.
