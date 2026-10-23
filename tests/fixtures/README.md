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
