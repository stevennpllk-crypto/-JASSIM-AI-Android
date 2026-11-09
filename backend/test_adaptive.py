import os
import tempfile
import unittest
from pathlib import Path

import adaptive


class AdaptiveRouterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_path = adaptive.DB_PATH
        adaptive.DB_PATH = Path(self.tmp.name) / "test.db"

    def tearDown(self):
        adaptive.DB_PATH = self.old_path
        self.tmp.cleanup()

    def test_quality_scoring_rewards_correct_answer(self):
        self.assertGreater(adaptive._quality("العاصمة تونس", ["تونس"]),
                           adaptive._quality("العاصمة صفاقس", ["تونس"]))

    def test_external_chat_is_disabled_by_default(self):
        old = adaptive.ALLOW_EXTERNAL_CHAT
        adaptive.ALLOW_EXTERNAL_CHAT = False
        try:
            self.assertFalse(adaptive.external_chat_enabled())
            with self.assertRaises(RuntimeError):
                adaptive.answer_with_provider([{"role": "user", "content": "test"}])
        finally:
            adaptive.ALLOW_EXTERNAL_CHAT = old

    def test_provider_score_persists_and_ranks(self):
        adaptive._record("jarvisclaw", 500, 0.9)
        adaptive._record("ovh", 2000, 0.4)
        scores = {item["id"]: item for item in adaptive.provider_stats()}
        self.assertEqual(scores["jarvisclaw"]["attempts"], 1)
        self.assertGreater(scores["jarvisclaw"]["routing_score"],
                           scores["ovh"]["routing_score"])

    def test_evaluator_uses_only_synthetic_cases(self):
        old_enabled = adaptive.ENABLE_PUBLIC_PROVIDERS
        old_providers = adaptive.PROVIDERS
        original_request = adaptive._request
        calls = []
        adaptive.ENABLE_PUBLIC_PROVIDERS = True
        adaptive.PROVIDERS = [dict(adaptive.PROVIDERS[0])]
        def fake_request(provider, messages, max_tokens=256):
            calls.append(messages)
            return "تونس", 123
        adaptive._request = fake_request
        try:
            result = adaptive.evaluate_providers()
            self.assertEqual(result["tested"], 1)
            self.assertEqual(len(calls), len(adaptive.EVALUATION_CASES))
            self.assertTrue(all("user" in call[-1]["role"] for call in calls))
            self.assertNotIn("conversation_id", str(calls))
        finally:
            adaptive._request = original_request
            adaptive.PROVIDERS = old_providers
            adaptive.ENABLE_PUBLIC_PROVIDERS = old_enabled


if __name__ == "__main__":
    unittest.main()
