"""Tests for the authenticated, private-only image inference client."""
import base64
import json
import os
import unittest
from unittest.mock import Mock, patch

import private_image


class PrivateImageWorkerTests(unittest.TestCase):
    def _response(self, payload):
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.read.return_value = json.dumps(payload).encode("utf-8")
        return response

    def test_public_worker_url_is_rejected_without_network_access(self):
        with patch.dict(os.environ, {
            "JASSIM_IMAGE_WORKER_URL": "https://images.example.com",
            "JASSIM_IMAGE_WORKER_TOKEN": "secret",
        }):
            # Module settings are loaded at import time; exercise the validator
            # through a temporary module-level configuration.
            with patch.object(private_image, "WORKER_URL", "https://images.example.com"), \
                 patch.object(private_image, "WORKER_TOKEN", "secret"), \
                 patch("urllib.request.urlopen", side_effect=AssertionError("public network forbidden")):
                self.assertIsNone(private_image._private_worker_url())
                self.assertEqual(private_image.worker_status()["model_ready"], False)
                with self.assertRaisesRegex(RuntimeError, "local_image_model_not_configured"):
                    private_image.generate("اختبار")

    def test_private_worker_generation_uses_authenticated_internal_endpoint(self):
        png = b"\x89PNG\r\n\x1a\n" + b"private-test"
        encoded = base64.b64encode(png).decode("ascii")
        payload = {"image_base64": encoded, "mime_type": "image/png", "model": "jassim-image-local"}
        with patch.object(private_image, "WORKER_URL", "http://image-worker.railway.internal:8188"), \
             patch.object(private_image, "WORKER_TOKEN", "worker-secret"), \
             patch("private_image.urllib.request.urlopen", return_value=self._response(payload)) as request:
            result = private_image.generate("منظر فضائي")
        self.assertEqual(result, (encoded, "image/png", "jassim-image-local"))
        sent_request = request.call_args.args[0]
        self.assertEqual(sent_request.full_url, "http://image-worker.railway.internal:8188/v1/images/generate")
        self.assertEqual(sent_request.get_header("Authorization"), "Bearer worker-secret")
        self.assertIn("منظر فضائي", sent_request.data.decode("utf-8"))

    def test_worker_readiness_requires_model_loaded(self):
        payload = {"ready": True, "model_ready": False, "model": "not-loaded"}
        with patch.object(private_image, "WORKER_URL", "http://image-worker.railway.internal:8188"), \
             patch.object(private_image, "WORKER_TOKEN", "worker-secret"), \
             patch("private_image.urllib.request.urlopen", return_value=self._response(payload)):
            status = private_image.worker_status()
        self.assertFalse(status["model_ready"])

    def test_mime_signature_is_checked(self):
        payload = {
            "image_base64": base64.b64encode(b"not-a-png").decode("ascii"),
            "mime_type": "image/png",
            "model": "jassim-image-local",
        }
        with patch.object(private_image, "WORKER_URL", "http://image-worker.railway.internal:8188"), \
             patch.object(private_image, "WORKER_TOKEN", "worker-secret"), \
             patch("private_image.urllib.request.urlopen", return_value=self._response(payload)):
            with self.assertRaisesRegex(RuntimeError, "private_image_worker_mime_mismatch"):
                private_image.generate("اختبار")


if __name__ == "__main__":
    unittest.main()
