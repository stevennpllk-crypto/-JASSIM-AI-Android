import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ANDROID_CHAT = ROOT / "app/src/main/java/com/jassim/ai/MainActivity.java"
SERVER = ROOT / "backend/server.py"
DASHBOARD_JS = ROOT / "dashboard/app.js"
DASHBOARD_HTML = ROOT / "dashboard/index.html"
ENV_EXAMPLE = ROOT / ".env.example"
STORAGE = ROOT / "backend/storage.py"


class SinglePrivateEngineTest(unittest.TestCase):
    def test_all_android_auth_requests_enforce_https_before_sending_credentials(self):
        source = ANDROID_CHAT.read_text(encoding="utf-8")
        self.assertIn("private URL secureUrl(String path)", source)
        self.assertIn('"https".equalsIgnoreCase(url.getProtocol())', source)
        self.assertIn('secureUrl(register ? "/api/auth/register" : "/api/auth/login")', source)
        self.assertIn("URL url = secureUrl(path);", source)

    def test_android_client_has_no_public_llm_fallback(self):
        source = ANDROID_CHAT.read_text(encoding="utf-8")
        self.assertNotIn("api.jarvisclaw.ai", source)
        self.assertNotIn("oai.endpoints.kepler.ai.cloud.ovh.net", source)
        self.assertNotIn("sendAnonymousFallback", source)
        self.assertNotIn("requestAnonymousProvider", source)
        self.assertNotIn("buildFallbackHistory", source)

    def test_android_connection_is_private_only_and_has_no_implicit_railway_default(self):
        android = ANDROID_CHAT.read_text(encoding="utf-8")
        self.assertNotIn("DEFAULT_SERVER_URL", android)
        self.assertNotIn("jassim-ai-core-final-production.up.railway.app", android)
        self.assertNotIn("خدمة ذكاء اصطناعي عامة مجانية", android)
        self.assertNotIn("الخدمة الاحتياطية متاحة", android)
        self.assertIn("لن تُرسل رسائلك إلى أي مزوّد خارجي", android)
        self.assertIn('prefs.getString("endpoint", "")', android)

    def test_clients_have_no_provider_evaluation_controls(self):
        android = ANDROID_CHAT.read_text(encoding="utf-8")
        dashboard = DASHBOARD_JS.read_text(encoding="utf-8")
        self.assertNotIn("runProviderEvaluation", android)
        self.assertNotIn("external_provider_ready", android)
        self.assertNotIn("api.groq.com", dashboard)
        dashboard_html = DASHBOARD_HTML.read_text(encoding="utf-8")
        self.assertNotIn("نموذج توليد صور خارجي", dashboard_html)
        self.assertIn("لن يتم استخدام مزوّد صور خارجي", dashboard_html)
        env = ENV_EXAMPLE.read_text(encoding="utf-8")
        storage = STORAGE.read_text(encoding="utf-8")
        self.assertNotIn("JASSIM_ENABLE_PUBLIC_PROVIDERS", env)
        self.assertNotIn("JASSIM_ALLOW_EXTERNAL_CHAT", env)
        self.assertNotIn("provider_scores", storage)

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
