import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ANDROID_CHAT = ROOT / "app/src/main/java/com/jassim/ai/MainActivity.java"
ADAPTIVE = ROOT / "backend/adaptive.py"


class ClientPrivacyTest(unittest.TestCase):
    def test_android_client_has_no_public_llm_fallback(self):
        source = ANDROID_CHAT.read_text(encoding="utf-8")
        self.assertNotIn("api.jarvisclaw.ai", source)
        self.assertNotIn("oai.endpoints.kepler.ai.cloud.ovh.net", source)
        self.assertNotIn("sendAnonymousFallback", source)
        self.assertNotIn("requestAnonymousProvider", source)
        self.assertNotIn("buildFallbackHistory", source)

    def test_android_client_does_not_send_without_private_server(self):
        source = ANDROID_CHAT.read_text(encoding="utf-8")
        self.assertRegex(
            source,
            re.compile(r'if \(baseUrl\(\)\.isEmpty\(\)\)\s*\{[^}]*لم تُرسل رسالتك إلى أي خدمة خارجية', re.S),
        )

    def test_public_providers_are_disabled_by_default(self):
        source = ADAPTIVE.read_text(encoding="utf-8")
        self.assertRegex(
            source,
            re.compile(r'JASSIM_ENABLE_PUBLIC_PROVIDERS",\s*"false"'),
        )


if __name__ == "__main__":
    unittest.main()
