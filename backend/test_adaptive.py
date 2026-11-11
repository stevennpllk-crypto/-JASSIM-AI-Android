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

    def test_live_chat_routing_ignores_unverified_quality_score(self):
        adaptive._record("jarvisclaw", 800, 0.99)
        adaptive._record("ovh", 800, 0.01)
        scores = {item["id"]: item for item in adaptive.provider_stats()}
        self.assertEqual(scores["jarvisclaw"]["routing_score"],
                         scores["ovh"]["routing_score"])

    def test_live_chat_attempt_preserves_benchmark_quality_and_failure_latency(self):
        adaptive._record("jarvisclaw", 900, 0.8)
        adaptive._record("jarvisclaw", 0, None, "TimeoutError: timed out")
        scores = {item["id"]: item for item in adaptive.provider_stats()}
        self.assertEqual(scores["jarvisclaw"]["quality_score"], 0.8)
        self.assertEqual(scores["jarvisclaw"]["average_latency_ms"], 900)
        self.assertEqual(scores["jarvisclaw"]["successes"], 1)
        self.assertEqual(scores["jarvisclaw"]["attempts"], 2)

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

        def fake_request(provider, messages, max_tokens=256, timeout=None):
            calls.append(messages)
            return "تونس", 123

        adaptive._request = fake_request
        try:
            result = adaptive.evaluate_providers()
            self.assertEqual(result["tested"], 1)
            self.assertEqual(result["case_count"], 8)
            self.assertEqual(result["benchmark_version"], adaptive.BENCHMARK_VERSION)
            self.assertIn("pass_rate", result["results"][0])
            self.assertIn("median_latency_ms", result["results"][0])
            self.assertIn("p95_latency_ms", result["results"][0])
            self.assertEqual(len(calls), len(adaptive.EVALUATION_CASES))
            self.assertTrue(all("user" in call[-1]["role"] for call in calls))
            self.assertNotIn("conversation_id", str(calls))
        finally:
            adaptive._request = original_request
            adaptive.PROVIDERS = old_providers
            adaptive.ENABLE_PUBLIC_PROVIDERS = old_enabled


    def test_deterministic_benchmark_graders(self):
        cases = {case["id"]: case for case in adaptive.EVALUATION_CASES}
        self.assertTrue(adaptive._grade_benchmark_case(cases["ar_capital_01"], "تونس."))
        self.assertTrue(adaptive._grade_benchmark_case(cases["math_multiply_01"], "323"))
        self.assertFalse(adaptive._grade_benchmark_case(cases["math_multiply_01"], "324"))
        self.assertTrue(adaptive._grade_benchmark_case(
            cases["json_schema_01"], '{"name":"Ali","age":16}'))
        self.assertFalse(adaptive._grade_benchmark_case(
            cases["json_schema_01"], 'Here is JSON: {"name":"Ali","age":16}'))
        self.assertTrue(adaptive._grade_benchmark_case(
            cases["python_ast_01"], "def add(a, b):\\n    return a + b"))
        self.assertFalse(adaptive._grade_benchmark_case(
            cases["python_ast_01"], "def add(a, b): return a - b"))
        self.assertTrue(adaptive._grade_benchmark_case(
            cases["french_translation_01"], "Bonjour!"))

    def test_external_fallback_bounds_each_provider_attempt(self):
        providers = [
            {"id": "jarvisclaw", "url": "https://example.invalid", "model": "test"},
            {"id": "ovh", "url": "https://example.invalid", "model": "test"},
        ]
        ranked = [{"id": "jarvisclaw"}, {"id": "ovh"}]
        with patch.object(adaptive, "ALLOW_EXTERNAL_CHAT", True), \
             patch.object(adaptive, "ENABLE_PUBLIC_PROVIDERS", True), \
             patch.object(adaptive, "PROVIDERS", providers), \
             patch.object(adaptive, "PROVIDER_ATTEMPT_TIMEOUT", 7), \
             patch.object(adaptive, "PROVIDER_TOTAL_TIMEOUT", 30), \
             patch.object(adaptive, "provider_stats", return_value=ranked), \
             patch.object(adaptive, "_request", side_effect=[
                 TimeoutError("first provider timed out"), ("answer", 123)
             ]) as request:
            answer, provider = adaptive.answer_with_provider(
                [{"role": "user", "content": "test"}]
            )
        self.assertEqual((answer, provider), ("answer", "ovh"))
        self.assertEqual(request.call_count, 2)
        self.assertEqual(request.call_args_list[0].kwargs["timeout"], 7)
        self.assertEqual(request.call_args_list[1].kwargs["timeout"], 7)

    def test_external_fallback_stops_when_total_budget_is_exhausted(self):
        providers = [
            {"id": "jarvisclaw", "url": "https://example.invalid", "model": "test"},
            {"id": "ovh", "url": "https://example.invalid", "model": "test"},
        ]
        ranked = [{"id": "jarvisclaw"}, {"id": "ovh"}]
        with patch.object(adaptive, "ALLOW_EXTERNAL_CHAT", True), \
             patch.object(adaptive, "ENABLE_PUBLIC_PROVIDERS", True), \
             patch.object(adaptive, "PROVIDERS", providers), \
             patch.object(adaptive, "PROVIDER_TOTAL_TIMEOUT", 10), \
             patch.object(adaptive, "provider_stats", return_value=ranked), \
             patch.object(adaptive.time, "monotonic", side_effect=[100.0, 111.0]), \
             patch.object(adaptive, "_request", side_effect=TimeoutError("timeout")) as request:
            with self.assertRaisesRegex(RuntimeError, "provider_budget_exhausted"):
                adaptive.answer_with_provider([{"role": "user", "content": "test"}])
        request.assert_not_called()


    def test_openai_compatible_sse_stream_emits_text_deltas(self):
        import io
        from unittest.mock import patch

        class FakeResponse:
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def __iter__(self):
                return iter([
                    b'data: {"choices":[{"delta":{"content":"Hello "},"finish_reason":null}]}\n',
                    b'data: {"choices":[{"delta":{"content":"world"},"finish_reason":null}]}\n',
                    b'data: [DONE]\n',
                ])

        emitted = []
        provider = {"id": "test", "url": "https://example.invalid", "model": "test"}
        with patch.object(adaptive.urllib.request, "urlopen", return_value=FakeResponse()):
            answer, latency = adaptive._stream_request(
                provider, [{"role": "user", "content": "hi"}], on_delta=emitted.append
            )
        self.assertEqual(answer, "Hello world")
        self.assertEqual(emitted, ["Hello ", "world"])
        self.assertGreaterEqual(latency, 0)

    def test_openai_stream_rejects_missing_terminal_event(self):
        from unittest.mock import patch

        class FakeResponse:
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def __iter__(self):
                return iter([
                    b'data: {"choices":[{"delta":{"content":"partial"},"finish_reason":null}]}\n'
                ])

        provider = {"id": "test", "url": "https://example.invalid", "model": "test"}
        with patch.object(adaptive.urllib.request, "urlopen", return_value=FakeResponse()):
            with self.assertRaisesRegex(RuntimeError, "incomplete_provider_stream"):
                adaptive._stream_request(provider, [{"role": "user", "content": "hi"}])

    def test_stream_router_does_not_switch_provider_after_partial_output(self):
        providers = [
            {"id": "first", "url": "https://example.invalid", "model": "test"},
            {"id": "second", "url": "https://example.invalid", "model": "test"},
        ]
        ranked = [{"id": "first"}, {"id": "second"}]
        emitted = []
        def interrupted(*args, **kwargs):
            kwargs["on_delta"]("partial")
            raise RuntimeError("connection lost")
        with patch.object(adaptive, "ALLOW_EXTERNAL_CHAT", True):
            with patch.object(adaptive, "ENABLE_PUBLIC_PROVIDERS", True):
                with patch.object(adaptive, "PROVIDERS", providers):
                    with patch.object(adaptive, "provider_stats", return_value=ranked):
                        with patch.object(adaptive, "_stream_request", side_effect=interrupted) as request:
                            with self.assertRaisesRegex(RuntimeError, "provider_stream_interrupted"):
                                adaptive.stream_answer_with_provider(
                                    [{"role": "user", "content": "test"}], emitted.append
                                )
        self.assertEqual(emitted, ["partial"])
        request.assert_called_once()


if __name__ == "__main__":
    unittest.main()
