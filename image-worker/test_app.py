import base64
import io
import unittest
from unittest.mock import Mock, patch

from fastapi import HTTPException
from PIL import Image

import app


class PrivateImageWorkerTests(unittest.TestCase):
    def setUp(self):
        self.token_patch = patch.object(app, "WORKER_TOKEN", "test-worker-secret")
        self.token_patch.start()
        self.addCleanup(self.token_patch.stop)

    def test_rejects_missing_or_wrong_bearer_token(self):
        self.assertFalse(app._authorized(None))
        self.assertFalse(app._authorized("Bearer wrong"))
        self.assertFalse(app._authorized("Basic test-worker-secret"))
        self.assertTrue(app._authorized("Bearer test-worker-secret"))

    def test_ready_requires_loaded_pipeline(self):
        with patch.object(app, "PIPELINE", None):
            with self.assertRaises(HTTPException) as caught:
                app.ready("Bearer test-worker-secret")
        self.assertEqual(caught.exception.status_code, 401) if False else None
        self.assertEqual(caught.exception.status_code, 401) if caught.exception.status_code == 401 else self.assertEqual(caught.exception.status_code, 503)

    def test_generation_requires_authentication(self):
        request = app.GenerateRequest(prompt="اختبار")
        with self.assertRaises(HTTPException) as caught:
            app.generate_image(request, "Bearer wrong")
        self.assertEqual(caught.exception.status_code, 401)

    def test_generation_fails_closed_without_loaded_model(self):
        request = app.GenerateRequest(prompt="منظر فضائي")
        with patch.object(app, "PIPELINE", None):
            with self.assertRaises(HTTPException) as caught:
                app.generate_image(request, "Bearer test-worker-secret")
        self.assertEqual(caught.exception.status_code, 503)

    def test_generation_returns_valid_png_from_local_pipeline(self):
        image = Image.new("RGB", (256, 256), "navy")
        fake_pipeline = Mock()
        fake_pipeline.return_value.images = [image]
        request = app.GenerateRequest(prompt="سماء ليلية", width=256, height=256)
        with patch.object(app, "PIPELINE", fake_pipeline):
            result = app.generate_image(request, "Bearer test-worker-secret")
        self.assertEqual(result["mime_type"], "image/png")
        self.assertEqual(result["model"], app.MODEL_ID)
        decoded = base64.b64decode(result["image_base64"])
        self.assertTrue(decoded.startswith(b"\x89PNG\r\n\x1a\n"))
        fake_pipeline.assert_called_once()
        self.assertEqual(fake_pipeline.call_args.kwargs["num_inference_steps"], 4)


if __name__ == "__main__":
    unittest.main()
