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


if __name__ == "__main__":
    unittest.main()
