import unittest
import server


class PrivateEngineSecurityTests(unittest.TestCase):
    def test_only_private_model_can_make_chat_ready(self):
        self.assertFalse(server.private_chat_ready({"reachable": False, "model_ready": False}))
        self.assertFalse(server.private_chat_ready({"reachable": True, "model_ready": False}))
        self.assertTrue(server.private_chat_ready({"reachable": True, "model_ready": True}))


if __name__ == "__main__":
    unittest.main()
