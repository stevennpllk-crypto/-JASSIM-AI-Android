import unittest

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
