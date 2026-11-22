import unittest
from unittest.mock import patch

import adaptive


class PrivateOnlyInferenceTests(unittest.TestCase):
    def test_provider_catalog_is_empty(self):
        self.assertEqual(adaptive.provider_stats(), [])

    def test_provider_evaluation_is_disabled_without_network_calls(self):
        with patch.object(adaptive, "_request", create=True) as request:
            result = adaptive.evaluate_providers()
            self.assertFalse(result["enabled"])
            self.assertEqual(result["tested"], 0)
            request.assert_not_called()

    def test_all_external_inference_is_rejected(self):
        with patch.object(adaptive, "_request", create=True) as request:
            with self.assertRaisesRegex(RuntimeError, "external_chat_disabled"):
                adaptive.answer_with_provider(
                    [{"role": "user", "content": "private message"}],
                    allow_external=True,
                )
            request.assert_not_called()

    def test_external_readiness_is_always_false(self):
        self.assertFalse(adaptive.external_chat_enabled())
        self.assertFalse(adaptive.npc_chat_enabled())


if __name__ == "__main__":
    unittest.main()
