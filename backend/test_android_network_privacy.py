"""Static privacy regression checks for Android network connections."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN_ACTIVITY = ROOT / "app" / "src" / "main" / "java" / "com" / "jassim" / "ai" / "MainActivity.java"
MANIFEST = ROOT / "app" / "src" / "main" / "AndroidManifest.xml"


class AndroidNetworkPrivacyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = MAIN_ACTIVITY.read_text(encoding="utf-8")
        cls.manifest = MANIFEST.read_text(encoding="utf-8")

    def test_every_http_connection_disables_redirects(self):
        connection_creations = self.source.count(".openConnection();")
        redirect_guards = self.source.count("setInstanceFollowRedirects(false);")
        self.assertEqual(connection_creations, 3, "Review any newly added Android network connection.")
        self.assertEqual(redirect_guards, connection_creations,
                         "Every Android connection must reject redirects before sending credentials or prompts.")

    def test_discovery_is_pinned_to_the_project_registry_and_api(self):
        self.assertIn(
            "https://stevennpllk-crypto.github.io/-JASSIM-AI-Android/connection.json",
            self.source,
        )
        self.assertIn(
            "https://jassim-ai-core-final-production.up.railway.app",
            self.source,
        )
        self.assertIn("TrustedEndpointPolicy.isTrusted(candidate)", self.source)

    def test_cleartext_http_is_disabled(self):
        self.assertIn('android:usesCleartextTraffic="false"', self.manifest)
        self.assertIn('android:label="JASSIM AI"', self.manifest)

    def test_android_branding_matches_repository(self):
        self.assertIn("JASSIM AI", self.source)
        self.assertNotIn("Mahdia AI", self.source)


if __name__ == "__main__":
    unittest.main()
