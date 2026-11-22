import unittest
from pathlib import Path


class AndroidPrivacyRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (
            Path(__file__).resolve().parents[1]
            / "app" / "src" / "main" / "java" / "com" / "jassim" / "ai"
            / "MainActivity.java"
        ).read_text(encoding="utf-8")

    def test_chat_uses_only_the_configured_jassim_backend(self):
        self.assertIn('openConnection("/api/chat/stream", "POST")', self.source)
        self.assertNotIn("requestAnonymousProvider", self.source)
        self.assertNotIn("sendAnonymousFallback", self.source)
        self.assertNotIn("buildFallbackHistory", self.source)

    def test_android_client_has_no_direct_public_llm_endpoints(self):
        forbidden_endpoints = (
            "api.jarvisclaw.ai",
            "oai.endpoints.kepler.ai.cloud.ovh.net",
            "api.groq.com",
            "router.huggingface.co",
            "openrouter.ai",
        )
        for endpoint in forbidden_endpoints:
            with self.subTest(endpoint=endpoint):
                self.assertNotIn(endpoint, self.source)

    def test_private_backend_requests_use_https_and_session_token(self):
        self.assertIn('"https"', self.source)
        self.assertIn('connection.setRequestProperty("Authorization", "Bearer " + token)', self.source)


if __name__ == "__main__":
    unittest.main()
