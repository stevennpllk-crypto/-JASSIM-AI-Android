import unittest

from local_model_benchmark import is_private_ollama_url, percentile


class LocalModelBenchmarkPolicyTests(unittest.TestCase):
    def test_allows_loopback_and_railway_private_hosts(self):
        self.assertTrue(is_private_ollama_url("http://127.0.0.1:11434"))
        self.assertTrue(is_private_ollama_url("http://localhost:11434"))
        self.assertTrue(is_private_ollama_url("http://ollama.railway.internal:11434"))

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

    def test_percentile_handles_empty_and_nonempty_samples(self):
        self.assertIsNone(percentile([], 0.95))
        self.assertEqual(percentile([1, 2, 3, 4, 5], 0.95), 5)


if __name__ == "__main__":
    unittest.main()
