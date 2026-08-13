import importlib.util
import os
import stat
import tempfile
import unittest
from pathlib import Path

import yaml


SCRIPT = Path(__file__).parents[1] / "scripts" / "validate-production-config.py"
SPEC = importlib.util.spec_from_file_location("validate_production_config", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class ProductionConfigGuardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "config.yaml"

    def tearDown(self):
        self.temp.cleanup()

    def write_config(self, *, profile=False, guilds=None, plugins=None):
        data = {
            "discord": {
                "allowed_guilds": guilds
                if guilds is not None
                else ["1146359014968537089"]
            },
            "memory": {"memory_enabled": True, "user_profile_enabled": profile},
            "plugins": {
                "enabled": plugins if plugins is not None else ["chatbird-policy"]
            },
            "secrets": {"token": "must-stay-unchanged"},
        }
        self.path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
        os.chmod(self.path, 0o640)

    def test_valid_config_passes(self):
        self.write_config()
        MODULE.validate_config(MODULE._load_config(self.path))

    def test_repair_is_atomic_and_preserves_other_values_and_mode(self):
        self.write_config(profile=True)
        self.assertTrue(MODULE.repair_builtin_profile(self.path))

        repaired = MODULE._load_config(self.path)
        self.assertIs(repaired["memory"]["user_profile_enabled"], False)
        self.assertEqual(repaired["secrets"]["token"], "must-stay-unchanged")
        self.assertEqual(stat.S_IMODE(self.path.stat().st_mode), 0o640)

    def test_wildcard_guild_is_rejected(self):
        self.write_config(guilds=["*"])
        with self.assertRaisesRegex(MODULE.ConfigError, "must not contain"):
            MODULE.validate_config(MODULE._load_config(self.path))

    def test_missing_policy_plugin_is_rejected(self):
        self.write_config(plugins=[])
        with self.assertRaisesRegex(MODULE.ConfigError, "chatbird-policy"):
            MODULE.validate_config(MODULE._load_config(self.path))


if __name__ == "__main__":
    unittest.main()
