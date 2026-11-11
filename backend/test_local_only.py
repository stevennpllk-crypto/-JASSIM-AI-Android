import os
import unittest
from unittest.mock import patch

import adaptive


class LocalOnlyPolicyTests(unittest.TestCase):
    def test_public_model_routing_is_hard_disabled(self):
        self.assertFalse(adaptive.ALLOW_EXTERNAL_CHAT)
        self.assertFalse(adaptive.ENABLE_PUBLIC_PROVIDERS)
        self.assertFalse(adaptive.external_chat_enabled())

    def test_environment_cannot_enable_external_chat_after_import(self):
        with patch.dict(os.environ, {
            "JASSIM_ALLOW_EXTERNAL_CHAT": "true",
            "JASSIM_ENABLE_PUBLIC_PROVIDERS": "true",
        }):
            self.assertFalse(adaptive.external_chat_enabled())

    def test_external_inference_functions_fail_closed(self):
        with self.assertRaisesRegex(RuntimeError, "external_chat_disabled"):
            adaptive.answer_with_provider([{"role": "user", "content": "private test"}])
        with self.assertRaisesRegex(RuntimeError, "external_chat_disabled"):
            adaptive.stream_answer_with_provider(
                [{"role": "user", "content": "private test"}], lambda token: None
            )

    def test_public_provider_evaluation_is_disabled_without_network_calls(self):
        with patch.object(adaptive, "_request", side_effect=AssertionError("network call forbidden")):
            result = adaptive.evaluate_providers()
        self.assertFalse(result["enabled"])
        self.assertEqual(result["tested"], 0)
        self.assertEqual(result["results"], [])



if __name__ == "__main__":
    unittest.main()
