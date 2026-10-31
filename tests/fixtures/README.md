# MDI catalog fixture

`mdi_catalog.json` contains all 7,447 canonical `name` values from the official
Material Design Icons `meta.json` at the commit recorded in the fixture. The
names are extracted from upstream, not from integration constants or test
expectations. Tests use this snapshot without network access.

To refresh it, download `meta.json` from a reviewed upstream commit, extract and
sort every entry's `name`, and update both `source` and `commit`. Do not add
individual names by hand to make a failing test pass. Review the resulting diff
and run `python -m pytest -q tests/test_translations.py`.

Catalog membership proves that an icon exists upstream; availability in the
supported Home Assistant frontend must also be checked when selecting new icons.

## Synthetic Liander account

`liander_account.json` was manually synthesized from a user-provided API schema.
It is not a saved production response or a reversible redaction. All address
values, EANs, meter identifiers, dates, tariffs, connection ratings, equipment
names and installation ratings were replaced with invented test values. The
all-zero-prefixed EANs and `TEST-` meter identifiers are deliberately fictional.
The installation's connection EAN consistently references the fictional
electricity connection. No original identifying values are stored in the fixture.

The fixture preserves API field names, container structure, JSON types, true/false
flags, the empty storage/case lists, and decimal-comma power notation. Do not use
live accounts or replace synthetic values with production examples. Derive
negative cases in memory from a fresh fixture load so tests remain independent.
