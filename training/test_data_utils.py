import unittest

from training.data_utils import encode_assistant_only


class FakeTokenizer:
    def apply_chat_template(self, messages, tokenize, add_generation_prompt):
        body = "|".join(f"{m['role']}:{m['content']}" for m in messages)
        if add_generation_prompt:
            return body + "|assistant:"
        return body

    def encode(self, text, add_special_tokens=False):
        return text.split("|")


class AssistantOnlyMaskTests(unittest.TestCase):
    def test_masks_prompt_and_trains_assistant(self):
        tokenizer = FakeTokenizer()
        messages = [
            {"role": "system", "content": "Be concise"},
            {"role": "user", "content": "2+2?"},
            {"role": "assistant", "content": "4"},
        ]
        result = encode_assistant_only(tokenizer, messages, max_length=64)
        self.assertTrue(all(x == -100 for x in result["labels"][:-1]))
        self.assertEqual(result["labels"][-1], result["input_ids"][-1])
        self.assertEqual(len(result["input_ids"]), len(result["labels"]))

    def test_rejects_truncation_that_removes_answer(self):
        tokenizer = FakeTokenizer()
        messages = [
            {"role": "user", "content": "long question"},
            {"role": "assistant", "content": "answer"},
        ]
        with self.assertRaises(ValueError):
            encode_assistant_only(tokenizer, messages, max_length=1)


if __name__ == "__main__":
    unittest.main()
