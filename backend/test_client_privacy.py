import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ANDROID_CHAT = ROOT / "app/src/main/java/com/jassim/ai/MainActivity.java"
SERVER = ROOT / "backend/server.py"
DASHBOARD_JS = ROOT / "dashboard/app.js"


class SinglePrivateEngineTest(unittest.TestCase):
    def test_android_client_has_no_public_llm_fallback(self):
        source = ANDROID_CHAT.read_text(encoding="utf-8")
        self.assertNotIn("api.jarvisclaw.ai", source)
        self.assertNotIn("oai.endpoints.kepler.ai.cloud.ovh.net", source)
        self.assertNotIn("sendAnonymousFallback", source)
        self.assertNotIn("requestAnonymousProvider", source)
        self.assertNotIn("buildFallbackHistory", source)

    def test_clients_have_no_provider_evaluation_controls(self):
        android = ANDROID_CHAT.read_text(encoding="utf-8")
        dashboard = DASHBOARD_JS.read_text(encoding="utf-8")
        self.assertNotIn("runProviderEvaluation", android)
        self.assertNotIn("external_provider_ready", android)
        self.assertNotIn("api.groq.com", dashboard)

    def test_backend_uses_only_private_ollama_for_chat(self):
        source = SERVER.read_text(encoding="utf-8")
        self.assertNotIn("adaptive.answer_with_provider", source)
        self.assertNotIn("JASSIM_ALLOW_EXTERNAL_CHAT", source)
        self.assertNotIn("JASSIM_ALLOW_EXTERNAL_NPC_CHAT", source)
        self.assertNotIn("api.groq.com", source)
        self.assertIn('return ask_ollama(messages), "ollama"', source)

    def test_unavailable_private_model_never_routes_elsewhere(self):
        source = SERVER.read_text(encoding="utf-8")
        self.assertIn("لم تُرسل رسالتك إلى أي خادم أو مزوّد آخر", source)
        self.assertIn('"private_model_unavailable"', source)

    def test_external_image_provider_is_removed(self):
        source = SERVER.read_text(encoding="utf-8")
        self.assertNotIn("JASSIM_HF_TOKEN", source)
        self.assertNotIn("router.huggingface.co", source)
        self.assertNotIn("generate_image_hf", source)


if __name__ == "__main__":
    unittest.main()
