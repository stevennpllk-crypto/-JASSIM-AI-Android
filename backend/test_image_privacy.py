"""Image generation must fail closed until a private local engine exists."""
import os
import unittest
from unittest.mock import patch

import server


class LocalImagePrivacyTests(unittest.TestCase):
    def test_image_generation_does_not_call_external_inference(self):
        with patch.dict(os.environ, {"JASSIM_HF_TOKEN": "test-token"}):
            with patch("urllib.request.urlopen", side_effect=AssertionError("external network call forbidden")):
                with self.assertRaisesRegex(RuntimeError, "local_image_model_not_configured"):
                    server.generate_image("اختبار صورة خاص")

    def test_image_generation_status_is_never_claimed_ready(self):
        with patch.dict(os.environ, {
            "JASSIM_HF_TOKEN": "test-token",
            "JASSIM_IMAGE_MODEL": "some-cloud-model",
        }):
            # The API health payload is intentionally hard-coded false until
            # a self-hosted image engine and its readiness probe are implemented.
            self.assertIn('"image_generation_ready": False', open(
                server.__file__, encoding="utf-8"
            ).read())


if __name__ == "__main__":
    unittest.main()
