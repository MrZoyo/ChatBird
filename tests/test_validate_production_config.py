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

    def write_config(self, *, profile=False, guilds=None, plugins=None, **overrides):
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
            "gateway": {"strict": True, "trust_recent_files": False},
            "web": {"keyless_fallback": False, "keyless_rescue": False},
            "tools": {"tool_search": {"enabled": "off"}},
            "security": {"allow_lazy_installs": False},
            "secrets": {"token": "must-stay-unchanged"},
        }
        data.update(overrides)
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

    def test_production_mirror_passes(self):
        mirror = Path(__file__).parents[1] / "patches" / "chatbird-production-config.yaml"
        MODULE.validate_config(MODULE._load_config(mirror))

    def test_each_hermes_default_that_would_open_the_bot_is_rejected(self):
        cases = {
            "strict": {"gateway": {"strict": False, "trust_recent_files": False}},
            "trust_recent_files": {"gateway": {"strict": True}},
            "keyless_rescue": {"web": {"keyless_fallback": False}},
            "keyless_fallback": {"web": {"keyless_rescue": False}},
            "tool_search": {"tools": {}},
            "allow_lazy_installs": {"security": {}},
            "write_approval": {"memory": {"user_profile_enabled": False, "write_approval": True}},
        }
        for name, overrides in cases.items():
            with self.subTest(name):
                self.write_config(**overrides)
                with self.assertRaisesRegex(MODULE.ConfigError, name.split("_")[0]):
                    MODULE.validate_config(MODULE._load_config(self.path))

    def test_bare_yaml_off_for_tool_search_is_accepted(self):
        self.write_config(tools={"tool_search": {"enabled": False}})
        MODULE.validate_config(MODULE._load_config(self.path))

    def test_env_file_cannot_override_media_policy(self):
        env = Path(self.temp.name) / ".env"
        admin = "CHATBIRD_ADMIN_USERS=1\nCHATBIRD_ADMIN_CHANNELS=2:3\n"
        env.write_text(f"ANTHROPIC_API_KEY=secret-value\n{admin}", encoding="utf-8")
        MODULE.validate_env_file(env)
        env.write_text(f"{admin}export HERMES_MEDIA_DELIVERY_STRICT=secret-value\n", encoding="utf-8")
        with self.assertRaises(MODULE.ConfigError) as caught:
            MODULE.validate_env_file(env)
        self.assertIn("HERMES_MEDIA_DELIVERY_STRICT", str(caught.exception))
        self.assertNotIn("secret-value", str(caught.exception))

    def test_missing_env_file_is_an_error(self):
        with self.assertRaisesRegex(MODULE.ConfigError, "cannot read .env"):
            MODULE.validate_env_file(Path(self.temp.name) / ".env")

    def test_env_file_must_name_the_admin_mapping(self):
        env = Path(self.temp.name) / ".env"
        env.write_text("# CHATBIRD_ADMIN_USERS=1\nCHATBIRD_ADMIN_CHANNELS=2:3\n", encoding="utf-8")
        with self.assertRaisesRegex(MODULE.ConfigError, "CHATBIRD_ADMIN_USERS"):
            MODULE.validate_env_file(env)


if __name__ == "__main__":
    unittest.main()
