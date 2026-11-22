import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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
            with patch.object(adaptive, "_request") as request:
                with self.assertRaisesRegex(RuntimeError, "external_chat_disabled"):
                    adaptive.answer_with_provider([{"role": "user", "content": "private test"}])
                request.assert_not_called()
        finally:
            adaptive.ALLOW_EXTERNAL_CHAT = old

    def test_npc_external_routing_requires_separate_opt_in(self):
        old_chat = adaptive.ALLOW_EXTERNAL_CHAT
        old_npc = adaptive.ALLOW_EXTERNAL_NPC_CHAT
        old_public = adaptive.ENABLE_PUBLIC_PROVIDERS
        adaptive.ALLOW_EXTERNAL_CHAT = False
        adaptive.ALLOW_EXTERNAL_NPC_CHAT = False
        adaptive.ENABLE_PUBLIC_PROVIDERS = True
        try:
            self.assertFalse(adaptive.npc_chat_enabled())
            with patch.object(adaptive, "provider_stats") as stats, patch.object(adaptive, "_request") as request:
                with self.assertRaisesRegex(RuntimeError, "external_chat_disabled"):
                    adaptive.answer_with_provider(
                        [{"role": "user", "content": "private conversation history"}],
                        allow_external=True,
                    )
                stats.assert_not_called()
                request.assert_not_called()
        finally:
            adaptive.ALLOW_EXTERNAL_CHAT = old_chat
            adaptive.ALLOW_EXTERNAL_NPC_CHAT = old_npc
            adaptive.ENABLE_PUBLIC_PROVIDERS = old_public

    def test_global_chat_opt_in_does_not_override_npc_opt_in(self):
        old_chat = adaptive.ALLOW_EXTERNAL_CHAT
        old_npc = adaptive.ALLOW_EXTERNAL_NPC_CHAT
        old_public = adaptive.ENABLE_PUBLIC_PROVIDERS
        adaptive.ALLOW_EXTERNAL_CHAT = True
        adaptive.ALLOW_EXTERNAL_NPC_CHAT = False
        adaptive.ENABLE_PUBLIC_PROVIDERS = True
        try:
            with patch.object(adaptive, "provider_stats") as stats, patch.object(adaptive, "_request") as request:
                with self.assertRaisesRegex(RuntimeError, "external_chat_disabled"):
                    adaptive.answer_with_provider(
                        [{"role": "user", "content": "NPC context"}],
                        allow_external=True,
                    )
                stats.assert_not_called()
                request.assert_not_called()
        finally:
            adaptive.ALLOW_EXTERNAL_CHAT = old_chat
            adaptive.ALLOW_EXTERNAL_NPC_CHAT = old_npc
            adaptive.ENABLE_PUBLIC_PROVIDERS = old_public

    def test_provider_score_persists_and_ranks(self):
        old_enabled = adaptive.ENABLE_PUBLIC_PROVIDERS
        adaptive.ENABLE_PUBLIC_PROVIDERS = True
        try:
            adaptive._record("jarvisclaw", 500, 0.9)
            adaptive._record("ovh", 2000, 0.4)
            scores = {item["id"]: item for item in adaptive.provider_stats()}
            self.assertEqual(scores["jarvisclaw"]["attempts"], 1)
            self.assertGreater(scores["jarvisclaw"]["routing_score"],
                               scores["ovh"]["routing_score"])
        finally:
            adaptive.ENABLE_PUBLIC_PROVIDERS = old_enabled

    def test_groq_is_hidden_without_api_key(self):
        with patch.dict(os.environ, {"GROQ_API_KEY": ""}):
            self.assertNotIn("groq", [p["id"] for p in adaptive._configured_providers()])

    def test_groq_is_configured_only_when_api_key_exists(self):
        with patch.dict(os.environ, {"GROQ_API_KEY": "test-only-placeholder"}):
            self.assertIn("groq", [p["id"] for p in adaptive._configured_providers()])

    def test_evaluator_uses_only_synthetic_cases(self):
        old_enabled = adaptive.ENABLE_PUBLIC_PROVIDERS
        old_providers = adaptive.PROVIDERS
        original_request = adaptive._request
        calls = []
        adaptive.ENABLE_PUBLIC_PROVIDERS = True
        # This test exercises the evaluator with a credential-free fake provider.
        provider = dict(adaptive.PROVIDERS[0])
        provider.pop("key_env", None)
        adaptive.PROVIDERS = [provider]

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
