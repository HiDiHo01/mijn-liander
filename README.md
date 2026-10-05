# Mijn Liander

Home Assistant integration for Mijn Liander.

## Install via HACS

Click the button below to open Mijn Liander in HACS in your Home Assistant instance:

[![Open your Home Assistant instance and show the Mijn Liander integration in the HACS store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=HiDiHo01&repository=mijn-liander&category=integration)

Then select **Download** in HACS and restart Home Assistant. If the button does not work, add the repository manually:

1. In Home Assistant, open **HACS > Integrations**.
2. Open the menu in the upper-right corner and select **Custom repositories**.
3. Add `https://github.com/HiDiHo01/mijn-liander` with the **Integration** category.
4. Find **Mijn Liander** in HACS and select **Download**.
5. Restart Home Assistant.
6. Go to **Settings > Devices & services > Add integration**, find **Mijn Liander**, and sign in with your Mijn Liander account.

Gas entities are created only while the account has an active gas contract. If the contract is added or removed later, the integration refreshes its entities when the account data next updates.

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
python -m pip install --require-hashes --only-binary=:all: --no-binary=pyric -r requirements_test.txt
python -m pytest -q
```

PyRIC has no published wheel, so only its hash-verified source archive is allowed.
Run Ruff 0.16.10 with `ruff check --config ruff.toml custom_components/mijn_liander tests`.
To update the dependency lock, edit `requirements_test.in` and run the `uv pip compile`
command recorded at the top of `requirements_test.txt`.
