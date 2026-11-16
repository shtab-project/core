import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "configure_vps", ROOT / "infra/scripts/configure_vps.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ConfigureVpsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        source = self.root / "infra/authentik/blueprints"
        source.mkdir(parents=True)
        (source / "shtab.yaml").write_text(
            (ROOT / "infra/authentik/blueprints/shtab.yaml").read_text("utf-8"),
            "utf-8",
        )

    def test_repeat_run_preserves_secrets_and_blueprint_uses_public_ip(self):
        credentials = MODULE.configure(self.root, "203.0.113.10")
        env = self.root / "infra/vps/.env"
        before = env.read_bytes()
        MODULE.configure(self.root, "203.0.113.10")
        self.assertEqual(env.read_bytes(), before)
        blueprint = (self.root / "infra/vps/blueprints/shtab.yaml").read_text("utf-8")
        self.assertIn("http://203.0.113.10/api/auth/callback", blueprint)
        self.assertNotIn("localhost", blueprint)
        self.assertIn("Login: akadmin", credentials.read_text("utf-8"))
        self.assertIn("SHTAB_AUTH_URL=http://203.0.113.10:9000", env.read_text("utf-8"))

    def test_rejects_changed_address_and_corrupt_existing_secrets(self):
        MODULE.configure(self.root, "203.0.113.10", 8080, 9001)
        with self.assertRaises(ValueError):
            MODULE.configure(self.root, "203.0.113.11", 8080, 9001)
        env = self.root / "infra/vps/.env"
        env.write_text("SHTAB_HOST=203.0.113.10\n", "utf-8")
        with self.assertRaises(ValueError):
            MODULE.configure(self.root, "203.0.113.10", 8080, 9001)

    def test_rejects_invalid_network_configuration(self):
        for address in ("0.0.0.0", "::1", "example.com", "1.2.3.4; echo x"):
            with self.subTest(address=address), self.assertRaises(ValueError):
                MODULE.configure(self.root, address)
        for ports in ((80, 80), (0, 9000), (80, 65536)):
            with self.subTest(ports=ports), self.assertRaises(ValueError):
                MODULE.configure(self.root, "203.0.113.10", *ports)


if __name__ == "__main__":
    unittest.main()
