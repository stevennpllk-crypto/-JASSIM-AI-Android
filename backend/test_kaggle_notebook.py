"""Static privacy checks for the free Kaggle GPU notebook."""
import json
import unittest
from pathlib import Path

NOTEBOOK = Path(__file__).resolve().parents[1] / "notebooks" / "JASSIM_AI_Kaggle_Free_GPU.ipynb"


class KaggleNotebookPrivacyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.notebook = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
        cls.cells = [
            "".join(cell.get("source", []))
            for cell in cls.notebook.get("cells", [])
            if cell.get("cell_type") == "code"
        ]
        cls.source = "\n".join(cls.cells)

    def test_notebook_is_gpu_enabled_and_contains_code(self):
        self.assertTrue(self.notebook["metadata"]["kaggle"]["isGpuEnabled"])
        self.assertGreaterEqual(len(self.cells), 5)

    def test_inference_endpoint_is_loopback_only(self):
        self.assertIn("http://127.0.0.1:11434", self.source)
        self.assertNotIn("ngrok", self.source.lower())
        self.assertNotIn("cloudflared", self.source.lower())
        self.assertNotIn("trycloudflare", self.source.lower())

    def test_no_real_user_data_or_secret_upload_paths(self):
        forbidden = (
            "GROQ_API_KEY",
            "OPENAI_API_KEY",
            "DATABASE_URL",
            "sessionStorage",
            "Authorization",
            "drive.mount",
            "files.upload",
        )
        for marker in forbidden:
            with self.subTest(marker=marker):
                self.assertNotIn(marker, self.source)

    def test_model_download_is_explicit_and_single_baseline(self):
        self.assertIn("MODEL = 'qwen3.5:4b'", self.source)
        self.assertIn("ollama', 'pull'", self.source.replace("['ollama','pull'", "['ollama', 'pull'"))
        self.assertNotIn("JASSIM_OLLAMA_URL", self.source)

    def test_benchmark_fails_on_incomplete_inference_runs(self):
        self.assertIn("report['completed'] != report['case_count']", self.source)
        self.assertIn("failed_calls", self.source)


if __name__ == "__main__":
    unittest.main()
