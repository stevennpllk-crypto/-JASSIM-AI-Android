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

    def test_streaming_ollama_failure_never_uses_external_provider(self):
        previous = server.adaptive.ALLOW_EXTERNAL_CHAT
        server.adaptive.ALLOW_EXTERNAL_CHAT = True
        handler = server.Handler.__new__(server.Handler)
        try:
            with patch("server.urllib.request.urlopen", side_effect=server.urllib.error.URLError("offline")), \\
                 patch.object(server.adaptive, "answer_with_provider") as external_provider, \\
                 patch.object(handler, "send_json") as send_json:
                handler.stream_chat_response(
                    "private-stream", "رسالة خاصة", [{"role": "user", "content": "رسالة خاصة"}], "test-user"
                )
            send_json.assert_called_once()
            self.assertEqual(send_json.call_args.args[0], 503)
            self.assertIn("لم تُرسل رسالتك إلى أي مزوّد خارجي", send_json.call_args.args[1]["message"])
            external_provider.assert_not_called()
        finally:
            server.adaptive.ALLOW_EXTERNAL_CHAT = previous


if __name__ == "__main__":
    unittest.main()
