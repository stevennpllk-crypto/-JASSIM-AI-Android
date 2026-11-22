import unittest

import server


class ServerPrivacySecurityTests(unittest.TestCase):
    def test_regular_user_cannot_enable_external_npc_routing(self):
        body = {"context": "game_npc"}
        identity = {"user_id": "user-1", "role": "user"}
        self.assertFalse(server.can_route_npc_externally(body, identity))

    def test_admin_can_enable_external_npc_routing_when_server_allows_it(self):
        body = {"context": "game_npc"}
        identity = {"user_id": "owner-1", "role": "admin"}
        self.assertTrue(server.can_route_npc_externally(body, identity))

    def test_non_npc_context_never_uses_npc_exception(self):
        body = {"context": "ordinary_chat"}
        identity = {"user_id": "owner-1", "role": "admin"}
        self.assertFalse(server.can_route_npc_externally(body, identity))

    def test_npc_provider_does_not_make_private_chat_ready(self):
        model_state = {"reachable": False, "model_ready": False}
        self.assertFalse(server.private_chat_ready(model_state, external_ready=False))

    def test_private_chat_is_ready_when_local_model_is_ready(self):
        model_state = {"reachable": True, "model_ready": True}
        self.assertTrue(server.private_chat_ready(model_state, external_ready=False))

    def test_operator_global_external_chat_opt_in_can_mark_chat_ready(self):
        model_state = {"reachable": False, "model_ready": False}
        self.assertTrue(server.private_chat_ready(model_state, external_ready=True))


if __name__ == "__main__":
    unittest.main()
