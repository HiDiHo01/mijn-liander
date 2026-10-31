"""Tests for the Mijn Liander entity translation catalogs."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from custom_components.mijn_liander.binary_sensor import (
    BINARY_SENSOR_DESCRIPTIONS,
    LianderBinarySensor,
)
from custom_components.mijn_liander.sensor import (
    SENSOR_DESCRIPTIONS,
    LianderSensor,
)

INTEGRATION_PATH = (
    Path(__file__).parents[1] / "custom_components" / "mijn_liander"
)


class EntityTranslationTests(unittest.TestCase):
    """Verify entity names use the integration's translation catalogs."""

    def test_entity_descriptions_use_translated_names(self) -> None:
        """Every entity description has a name in the source and locales."""
        descriptions = {
            "sensor": SENSOR_DESCRIPTIONS,
            "binary_sensor": BINARY_SENSOR_DESCRIPTIONS,
        }
        source = json.loads((INTEGRATION_PATH / "strings.json").read_text())
        locales = {
            language: json.loads(
                (INTEGRATION_PATH / "translations" / f"{language}.json").read_text()
            )
            for language in ("en", "nl")
        }

        self.assertEqual(source["entity"], locales["en"]["entity"])

        for domain, entity_descriptions in descriptions.items():
            for description in entity_descriptions:
                with self.subTest(domain=domain, key=description.key):
                    self.assertIsNotNone(description.translation_key)
                    self.assertNotIsInstance(description.name, str)

                    for catalog in (
                        source["entity"][domain],
                        *(locale["entity"][domain] for locale in locales.values()),
                    ):
                        translated = catalog.get(description.translation_key)
                        self.assertIsNotNone(translated)
                        self.assertTrue(translated["name"])
                        self.assertNotIn("description", translated)

    def test_locales_have_matching_entity_translation_keys(self) -> None:
        """Every locale has the same entity translation keys as the source."""
        source = json.loads((INTEGRATION_PATH / "strings.json").read_text())
        locales = {
            language: json.loads(
                (INTEGRATION_PATH / "translations" / f"{language}.json").read_text()
            )
            for language in ("en", "nl")
        }

        for domain, source_entities in source["entity"].items():
            for language, catalog in locales.items():
                with self.subTest(domain=domain, language=language):
                    self.assertEqual(
                        set(source_entities),
                        set(catalog["entity"][domain]),
                    )

    def test_entity_classes_use_entity_names(self) -> None:
        """Entity names describe the entity and are translated by Home Assistant."""
        self.assertTrue(LianderSensor._attr_has_entity_name)
        self.assertTrue(LianderBinarySensor._attr_has_entity_name)

    def test_binary_sensor_icons_exist_in_mdi_catalog(self) -> None:
        """Validate actual state icons against the pinned upstream catalog."""
        catalog_path = Path(__file__).parent / "fixtures" / "mdi_catalog.json"
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        icon_names = set(catalog["names"])

        for description in BINARY_SENSOR_DESCRIPTIONS:
            # Icon selection needs only the description and native binary state.
            entity = object.__new__(LianderBinarySensor)
            entity.entity_description = description
            for state in (True, False, None):
                with self.subTest(key=description.key, state=state):
                    entity._attr_is_on = state
                    selected_icon = entity.icon
                    expected_icon = (
                        description.icon_inactive
                        if not state and description.icon_inactive is not None
                        else description.icon
                    )
                    self.assertEqual(selected_icon, expected_icon)
                    if selected_icon is not None:
                        self.assertTrue(selected_icon.startswith("mdi:"))
                        self.assertIn(
                            selected_icon.removeprefix("mdi:"),
                            icon_names,
                            f"Unknown MDI icon for {description.key}: {selected_icon}",
                        )

    def test_binary_sensor_device_classes_and_inactive_icons(self) -> None:
        """Verify binary sensors have expected device classes and inactive icon visual feedback."""
        from homeassistant.components.binary_sensor import BinarySensorDeviceClass

        gprs_desc = next(d for d in BINARY_SENSOR_DESCRIPTIONS if d.key == "gprs")
        self.assertEqual(gprs_desc.device_class, BinarySensorDeviceClass.CONNECTIVITY)
        self.assertEqual(gprs_desc.icon, "mdi:signal")
        self.assertEqual(gprs_desc.icon_inactive, "mdi:signal-off")

        gas_status_desc = next(d for d in BINARY_SENSOR_DESCRIPTIONS if d.key == "gas_status")
        self.assertEqual(gas_status_desc.icon, "mdi:check-circle")
        self.assertEqual(gas_status_desc.icon_inactive, "mdi:cancel")

        perm_desc = next(d for d in BINARY_SENSOR_DESCRIPTIONS if d.key == "permission_to_read_data")
        self.assertEqual(perm_desc.icon, "mdi:eye-check-outline")
        self.assertEqual(perm_desc.icon_inactive, "mdi:eye-off-outline")

        gas_perm_desc = next(d for d in BINARY_SENSOR_DESCRIPTIONS if d.key == "gas_permission_to_read_data")
        self.assertEqual(gas_perm_desc.icon, "mdi:eye-check-outline")
        self.assertEqual(gas_perm_desc.icon_inactive, "mdi:eye-off-outline")

        contract_desc = next(d for d in BINARY_SENSOR_DESCRIPTIONS if d.key == "contract_active")
        self.assertEqual(contract_desc.icon, "mdi:check-circle")
        self.assertEqual(contract_desc.icon_inactive, "mdi:close-circle")

        gas_contract_desc = next(d for d in BINARY_SENSOR_DESCRIPTIONS if d.key == "gas_contract_active")
        self.assertEqual(gas_contract_desc.icon, "mdi:check-circle")
        self.assertEqual(gas_contract_desc.icon_inactive, "mdi:close-circle")

        smart_meter_desc = next(d for d in BINARY_SENSOR_DESCRIPTIONS if d.key == "smart_meter")
        self.assertEqual(smart_meter_desc.icon, "mdi:meter-electric")
        self.assertEqual(smart_meter_desc.icon_inactive, "mdi:meter-electric-outline")

        gas_smart_meter_desc = next(d for d in BINARY_SENSOR_DESCRIPTIONS if d.key == "gas_smart_meter")
        self.assertEqual(gas_smart_meter_desc.icon, "mdi:meter-gas")
        self.assertEqual(gas_smart_meter_desc.icon_inactive, "mdi:meter-gas-outline")

        backfeeding_desc = next(d for d in BINARY_SENSOR_DESCRIPTIONS if d.key == "backfeeding_energy")
        self.assertEqual(backfeeding_desc.icon, "mdi:transmission-tower-import")
        self.assertEqual(backfeeding_desc.icon_inactive, "mdi:transmission-tower-off")

        net_metering_desc = next(d for d in BINARY_SENSOR_DESCRIPTIONS if d.key == "net_metering")
        self.assertEqual(net_metering_desc.icon, "mdi:solar-power")
        self.assertEqual(net_metering_desc.icon_inactive, "mdi:solar-power-variant-outline")

        self.assertNotIn("analog", {d.key for d in BINARY_SENSOR_DESCRIPTIONS})

        suitable_backfeeding_desc = next(d for d in BINARY_SENSOR_DESCRIPTIONS if d.key == "suitable_for_backfeeding")
        self.assertEqual(suitable_backfeeding_desc.icon, "mdi:transmission-tower")
        self.assertEqual(suitable_backfeeding_desc.icon_inactive, "mdi:transmission-tower-off")

        suitable_dual_tariff_desc = next(d for d in BINARY_SENSOR_DESCRIPTIONS if d.key == "suitable_for_dual_tariff")
        self.assertEqual(suitable_dual_tariff_desc.icon, "mdi:cash-multiple")
        self.assertEqual(suitable_dual_tariff_desc.icon_inactive, "mdi:cash-off")

        meter_fault_desc = next(d for d in BINARY_SENSOR_DESCRIPTIONS if d.key == "meter_fault_check_allowed")
        self.assertEqual(meter_fault_desc.icon, "mdi:meter-electric")
        self.assertEqual(meter_fault_desc.icon_inactive, "mdi:meter-electric-outline")

        smart_request_desc = next(d for d in BINARY_SENSOR_DESCRIPTIONS if d.key == "smart_meter_request_allowed")
        self.assertEqual(smart_request_desc.icon, "mdi:meter-electric")
        self.assertEqual(smart_request_desc.icon_inactive, "mdi:meter-electric-outline")

        gas_meter_fault_desc = next(d for d in BINARY_SENSOR_DESCRIPTIONS if d.key == "gas_meter_fault_check_allowed")
        self.assertEqual(gas_meter_fault_desc.icon, "mdi:meter-gas")
        self.assertEqual(gas_meter_fault_desc.icon_inactive, "mdi:meter-gas-outline")

        # Verify every binary sensor has an icon_inactive defined
        for desc in BINARY_SENSOR_DESCRIPTIONS:
            self.assertIsNotNone(desc.icon_inactive, f"Missing icon_inactive for binary sensor {desc.key}")


if __name__ == "__main__":
    unittest.main()
