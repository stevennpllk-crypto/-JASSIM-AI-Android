"""Tests for the authenticated, private-only image inference client."""
import base64
import json
import os
from pathlib import Path
import unittest
import urllib.request
from unittest.mock import Mock, patch

import private_image


class PrivateImageWorkerTests(unittest.TestCase):
    def test_worker_transport_disables_proxies_and_redirects(self):
        handlers = private_image._WORKER_OPENER.handlers
        self.assertTrue(any(isinstance(h, urllib.request.ProxyHandler)
                            and h.proxies == {} for h in handlers))
        redirect = next(h for h in handlers if isinstance(
            h, private_image._NoWorkerRedirects))
        self.assertIsNone(redirect.redirect_request(
            None, None, 302, "Found", {}, "https://public.example/steal"))

    def test_source_uses_only_the_hardened_private_transport(self):
        source = Path(__file__).with_name("private_image.py").read_text(encoding="utf-8")
        self.assertNotIn("urllib.request.urlopen(", source)
        self.assertIn("urllib.request.ProxyHandler({})", source)
        self.assertIn("_NoWorkerRedirects()", source)
        self.assertIn('requested.path not in ("/ready", "/v1/images/generate")', source)

    def test_worker_rejects_mismatched_origin_and_unapproved_paths(self):
        with patch.object(private_image, "WORKER_URL",
                          "http://image-worker.railway.internal:8188"), \
             patch.object(private_image, "WORKER_TOKEN", "worker-secret"), \
             patch.object(private_image._WORKER_OPENER, "open") as opener:
            for url in (
                "http://public.example:8188/ready",
                "http://image-worker.railway.internal:8188/v1/images/generate?target=public",
                "http://image-worker.railway.internal:8188/admin",
                "http://user@image-worker.railway.internal:8188/ready",
            ):
                with self.subTest(url=url):
                    request = private_image.urllib.request.Request(url)
                    with self.assertRaisesRegex(
                        RuntimeError, "private_image_worker_request_target_mismatch"
                    ):
                        private_image.open_worker(request, timeout=1)
            wrong_method = private_image.urllib.request.Request(
                "http://image-worker.railway.internal:8188/ready",
                data=b"unexpected",
                method="POST",
            )
            with self.assertRaisesRegex(
                RuntimeError, "private_image_worker_request_target_mismatch"
            ):
                private_image.open_worker(wrong_method, timeout=1)
            opener.assert_not_called()


    def setUp(self):
        private_image._STATUS_CACHE = None
        private_image._STATUS_CACHE_AT = 0.0

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
                 patch("private_image._WORKER_OPENER.open", side_effect=AssertionError("public network forbidden")):
                self.assertIsNone(private_image._private_worker_url())
                self.assertEqual(private_image.worker_status(force_refresh=True)["model_ready"], False)
                with self.assertRaisesRegex(RuntimeError, "local_image_model_not_configured"):
                    private_image.generate("اختبار")

    def test_private_worker_generation_uses_authenticated_internal_endpoint(self):
        png = b"\x89PNG\r\n\x1a\n" + b"private-test"
        encoded = base64.b64encode(png).decode("ascii")
        payload = {"image_base64": encoded, "mime_type": "image/png", "model": "jassim-image-local"}
        ready = {"ready": True, "model_ready": True, "model": "jassim-image-local"}
        with patch.object(private_image, "WORKER_URL", "http://image-worker.railway.internal:8188"), \
             patch.object(private_image, "WORKER_TOKEN", "worker-secret"), \
             patch("private_image._WORKER_OPENER.open", side_effect=[
                 self._response(ready), self._response(payload)
             ]) as request:
            result = private_image.generate("منظر فضائي")
        self.assertEqual(result, (encoded, "image/png", "jassim-image-local"))
        sent_request = request.call_args_list[-1].args[0]
        self.assertEqual(sent_request.full_url, "http://image-worker.railway.internal:8188/v1/images/generate")
        self.assertEqual(sent_request.get_header("Authorization"), "Bearer worker-secret")
        self.assertEqual(json.loads(sent_request.data.decode("utf-8"))["prompt"], "منظر فضائي")

    def test_worker_readiness_requires_model_loaded(self):
        payload = {"ready": True, "model_ready": False, "model": "not-loaded"}
        with patch.object(private_image, "WORKER_URL", "http://image-worker.railway.internal:8188"), \
             patch.object(private_image, "WORKER_TOKEN", "worker-secret"), \
             patch("private_image._WORKER_OPENER.open", return_value=self._response(payload)):
            status = private_image.worker_status(force_refresh=True)
        self.assertFalse(status["model_ready"])

    def test_mime_signature_is_checked(self):
        payload = {
            "image_base64": base64.b64encode(b"not-a-png").decode("ascii"),
            "mime_type": "image/png",
            "model": "jassim-image-local",
        }
        ready = {"ready": True, "model_ready": True, "model": "jassim-image-local"}
        with patch.object(private_image, "WORKER_URL", "http://image-worker.railway.internal:8188"), \
             patch.object(private_image, "WORKER_TOKEN", "worker-secret"), \
             patch("private_image._WORKER_OPENER.open", side_effect=[
                 self._response(ready), self._response(payload)
             ]):
            with self.assertRaisesRegex(RuntimeError, "private_image_worker_mime_mismatch"):
                private_image.generate("اختبار")


if __name__ == "__main__":
    unittest.main()
