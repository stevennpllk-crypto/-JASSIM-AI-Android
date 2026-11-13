"""Private inference must fail closed until the owned engine is installed."""
import os
import unittest
from unittest.mock import patch

import adaptive
import server


class LocalImagePrivacyTests(unittest.TestCase):
    def test_image_generation_does_not_call_external_inference(self):
        with patch.dict(os.environ, {"JASSIM_HF_TOKEN": "test-token"}):
            with patch("urllib.request.urlopen", side_effect=AssertionError("external network call forbidden")):
                with self.assertRaisesRegex(RuntimeError, "local_image_model_not_configured"):
                    server.generate_image("اختبار صورة خاص")

    def test_image_readiness_is_truthful_and_centralized(self):
        self.assertEqual(server.image_generation_status(), {
            "image_generation_ready": False,
            "image_model": "not_configured_private_worker",
        })

    def test_environment_cannot_enable_external_chat_backup(self):
        # Backups remain disabled until an explicit, separately reviewed opt-in
        # is implemented; environment flags alone cannot bypass this privacy gate.
        with patch.dict(os.environ, {
            "JASSIM_ALLOW_EXTERNAL_CHAT": "true",
            "JASSIM_ENABLE_PUBLIC_PROVIDERS": "true",
            "GROQ_API_KEY": "test-key",
        }):
            self.assertFalse(adaptive.external_chat_enabled())
            with self.assertRaisesRegex(RuntimeError, "external_chat_disabled"):
                adaptive.answer_with_provider([{"role": "user", "content": "private test"}])


if __name__ == "__main__":
    unittest.main()
