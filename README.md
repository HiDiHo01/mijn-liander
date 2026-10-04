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

## Manual installation

1. Download the [latest version of this repository](https://github.com/HiDiHo01/mijn-liander/archive/refs/heads/main.zip).
2. Copy the `custom_components/mijn_liander` directory to `<config>/custom_components/mijn_liander` in Home Assistant.
3. Restart Home Assistant.
4. Add **Mijn Liander** through **Settings > Devices & services > Add integration** and sign in with your Mijn Liander account.
