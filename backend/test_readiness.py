"""Readiness must prove the private local model, not an external fallback."""
import unittest

from readiness import local_model_ready


class LocalModelReadinessTests(unittest.TestCase):
    def test_ready_when_local_model_is_reachable_and_installed(self):
        self.assertTrue(local_model_ready({
            "reachable": True,
            "model_ready": True,
        }))

    def test_not_ready_when_ollama_is_unreachable(self):
        self.assertFalse(local_model_ready({
            "reachable": False,
            "model_ready": True,
        }))

    def test_not_ready_when_model_is_missing(self):
        self.assertFalse(local_model_ready({
            "reachable": True,
            "model_ready": False,
        }))

    def test_not_ready_for_missing_or_malformed_status(self):
        for value in (None, {}, {"reachable": True}, "healthy"):
            with self.subTest(value=value):
                self.assertFalse(local_model_ready(value))


if __name__ == "__main__":
    unittest.main()
