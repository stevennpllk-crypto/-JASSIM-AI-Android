import unittest

from local_model_benchmark import is_private_ollama_url, is_private_ollama_request_url, percentile


class LocalModelBenchmarkPolicyTests(unittest.TestCase):
    def test_allows_loopback_and_railway_private_hosts(self):
        self.assertTrue(is_private_ollama_url("http://127.0.0.1:11434"))
        self.assertTrue(is_private_ollama_url("http://localhost:11434"))
        self.assertTrue(is_private_ollama_url("http://ollama.railway.internal:11434"))

    def test_request_url_allows_only_known_private_api_paths(self):
        self.assertTrue(is_private_ollama_request_url("http://127.0.0.1:11434/api/chat"))
        self.assertTrue(is_private_ollama_request_url("http://ollama.railway.internal:11434/api/tags"))
        for value in (
            "http://127.0.0.1:11434/api/chat?redirect=https://evil.example",
            "http://127.0.0.1:11434/other/api/chat",
            "http://127.0.0.1:11434/api/delete",
            "http://user:pass@127.0.0.1:11434/api/chat",
            "http://127.0.0.1:11434/api/ps#fragment",
        ):
            with self.subTest(value=value):
                self.assertFalse(is_private_ollama_request_url(value))

    def test_rejects_public_hosts_and_url_injection(self):
        for value in (
            "https://ollama.example.com",
            "http://8.8.8.8:11434",
            "http://user:pass@localhost:11434",
            "http://localhost:11434/api",
            "http://localhost:11434/?target=public",
            "not a url",
        ):
            with self.subTest(value=value):
                self.assertFalse(is_private_ollama_url(value))


    def test_run_benchmark_rejects_public_url_before_any_request(self):
        from unittest.mock import patch
        from local_model_benchmark import run_benchmark

        with patch("local_model_benchmark.request_json") as request:
            with self.assertRaises(ValueError):
                run_benchmark("https://example.com", "model", [], 10)
            request.assert_not_called()

    def test_private_request_redirects_are_disabled(self):
        from local_model_benchmark import _NoRedirectHandler

        handler = _NoRedirectHandler()
        self.assertIsNone(handler.redirect_request(None, None, 302, "Found", {}, "https://example.com"))

    def test_private_opener_disables_environment_proxies(self):
        import urllib.request
        from local_model_benchmark import _PRIVATE_OPENER

        handlers = [
            item for item in _PRIVATE_OPENER.handlers
            if isinstance(item, urllib.request.ProxyHandler)
        ]
        # build_opener may omit an empty ProxyHandler entirely; either way,
        # no non-empty proxy configuration may be present.
        self.assertFalse(any(item.proxies for item in handlers))

    def test_percentile_handles_empty_and_nonempty_samples(self):
        self.assertIsNone(percentile([], 0.95))
        self.assertEqual(percentile([1, 2, 3, 4, 5], 0.95), 5)


if __name__ == "__main__":
    unittest.main()
