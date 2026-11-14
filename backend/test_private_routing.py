"""Privacy regression tests for private-only user chat routing."""
import unittest
from unittest.mock import patch

import server


class PrivateOnlyRoutingTests(unittest.TestCase):
    def test_ollama_failure_never_sends_user_chat_to_external_provider(self):
        previous = server.adaptive.ALLOW_EXTERNAL_CHAT
        server.adaptive.ALLOW_EXTERNAL_CHAT = True
        try:
            with patch.object(server, "ask_ollama", side_effect=RuntimeError("ollama offline")), \
                 patch.object(server.adaptive, "answer_with_provider") as external_provider:
                answer, engine = server.generate_answer([
                    {"role": "user", "content": "رسالة خاصة لا يجب إرسالها خارجياً"}
                ])
            self.assertEqual(engine, "fallback")
            self.assertIn("لم تُرسل رسالتك إلى أي مزوّد خارجي", answer)
            external_provider.assert_not_called()
        finally:
            server.adaptive.ALLOW_EXTERNAL_CHAT = previous


if __name__ == "__main__":
    unittest.main()
