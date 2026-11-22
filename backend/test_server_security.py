import unittest
from unittest.mock import patch

import server


class PrivateEngineSecurityTests(unittest.TestCase):
    def test_only_private_model_can_make_chat_ready(self):
        self.assertFalse(server.private_chat_ready({"reachable": False, "model_ready": False}))
        self.assertFalse(server.private_chat_ready({"reachable": True, "model_ready": False}))
        self.assertTrue(server.private_chat_ready({"reachable": True, "model_ready": True}))

    def test_unavailable_private_model_fails_closed_without_fallback(self):
        with patch.object(server, "ask_ollama", side_effect=RuntimeError("private model offline")):
            answer, engine = server.generate_answer([{"role": "user", "content": "private test"}])
        self.assertEqual(engine, "unavailable")
        self.assertIn("لم تُرسل رسالتك إلى أي خادم أو مزوّد آخر", answer)


if __name__ == "__main__":
    unittest.main()
