import unittest
from unittest.mock import patch

import server


class ServerPrivacySecurityTests(unittest.TestCase):
    def test_regular_user_cannot_enable_external_npc_routing(self):
        body = {"context": "game_npc"}
        identity = {"user_id": "user-1", "role": "user"}
        self.assertFalse(server.can_route_npc_externally(body, identity))

    def test_admin_cannot_enable_external_npc_routing(self):
        body = {"context": "game_npc"}
        identity = {"user_id": "owner-1", "role": "admin"}
        self.assertFalse(server.can_route_npc_externally(body, identity))

    def test_non_npc_context_never_uses_npc_exception(self):
        body = {"context": "ordinary_chat"}
        identity = {"user_id": "owner-1", "role": "admin"}
        self.assertFalse(server.can_route_npc_externally(body, identity))

    def test_image_generation_never_contacts_a_hosted_provider(self):
        with patch.object(server.urllib.request, "urlopen") as outbound:
            with self.assertRaisesRegex(RuntimeError, "private_image_engine_not_configured"):
                server.generate_image_hf("test prompt")
            outbound.assert_not_called()

    def test_external_image_token_cannot_enable_image_generation(self):
        with patch.dict("os.environ", {"JASSIM_HF_TOKEN": "unused-test-token"}):
            with patch.object(server.urllib.request, "urlopen") as outbound:
                with self.assertRaisesRegex(RuntimeError, "private_image_engine_not_configured"):
                    server.generate_image_hf("private prompt")
                outbound.assert_not_called()

    def test_npc_provider_does_not_make_private_chat_ready(self):
        model_state = {"reachable": False, "model_ready": False}
        self.assertFalse(server.private_chat_ready(model_state, external_ready=False))

    def test_private_chat_is_ready_when_local_model_and_token_are_ready(self):
        model_state = {"reachable": True, "model_ready": True}
        previous_token = server.API_TOKEN
        server.API_TOKEN = "test-api-token"
        try:
            self.assertTrue(server.private_chat_ready(model_state, external_ready=False))
        finally:
            server.API_TOKEN = previous_token

    def test_operator_global_external_chat_opt_in_cannot_mark_private_chat_ready(self):
        model_state = {"reachable": False, "model_ready": False}
        previous_token = server.API_TOKEN
        server.API_TOKEN = "test-api-token"
        try:
            self.assertFalse(server.private_chat_ready(model_state, external_ready=True))
        finally:
            server.API_TOKEN = previous_token


if __name__ == "__main__":
    unittest.main()
