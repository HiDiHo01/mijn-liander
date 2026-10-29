## 2025-02-17 - Home Assistant Config Flow Password Selectors & Binary Sensor Inactive Icons
**Learning:** Home Assistant config flow forms default to plaintext inputs unless `TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))` is explicitly declared. Additionally, binary sensors without explicit `icon_inactive` retain active icons even in `off` states.
**Action:** Always use `TextSelector` with `TextSelectorType.PASSWORD` for sensitive credential fields in config flows and ensure binary sensors have matching active/inactive icon pairs (`icon` and `icon_inactive`).

## 2025-05-18 - Home Assistant Config Flow Email & Password Autocomplete Selectors
**Learning:** Home Assistant config flow email inputs declared with plain `cv.string` lack email keyboard layout optimization and password manager autofill hints (`autocomplete="username"` / `autocomplete="current-password"`).
**Action:** Use `TextSelector(TextSelectorConfig(type=TextSelectorType.EMAIL, autocomplete="username"))` for username/email inputs and specify `autocomplete="current-password"` for password selectors in config flows.
