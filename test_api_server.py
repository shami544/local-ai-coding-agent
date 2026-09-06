import os
import sys
import time
import json
import unittest
import urllib.request
import urllib.error

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from api_server import LocalAPIServer


class TestAPIServer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test_port = 8123
        cls.server = LocalAPIServer(port=cls.test_port)
        cls.server.start()
        # Give server thread a moment to bind and listen
        time.sleep(0.4)

    @classmethod
    def tearDownClass(cls):
        cls.server.stop()
        time.sleep(0.2)

    def test_server_status(self):
        url = f"http://127.0.0.1:{self.test_port}/api/status"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertEqual(data.get("status"), "online")
            self.assertEqual(data.get("compatible"), "OpenAI v1")

    def test_cors_preflight(self):
        url = f"http://127.0.0.1:{self.test_port}/v1/chat/completions"
        req = urllib.request.Request(url, method="OPTIONS")
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            headers = dict(resp.headers)
            self.assertEqual(headers.get("Access-Control-Allow-Origin"), "*")
            self.assertIn("POST", headers.get("Access-Control-Allow-Methods", ""))

    def test_get_models_openai_format(self):
        url = f"http://127.0.0.1:{self.test_port}/v1/models"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertEqual(data.get("object"), "list")
            models = data.get("data", [])
            self.assertIsInstance(models, list)
            self.assertGreater(len(models), 0)
            self.assertEqual(models[0].get("object"), "model")
            self.assertEqual(models[0].get("owned_by"), "ollama-local")

    def test_chat_completions_non_streaming(self):
        url = f"http://127.0.0.1:{self.test_port}/v1/chat/completions"
        payload = {
            "model": "qwen2.5-coder:14b",
            "messages": [
                {"role": "user", "content": "قل مرحباً فقط"}
            ],
            "stream": False
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertEqual(data.get("object"), "chat.completion")
            self.assertTrue(data.get("id", "").startswith("chatcmpl-"))
            choices = data.get("choices", [])
            self.assertGreater(len(choices), 0)
            content = choices[0]["message"]["content"]
            self.assertTrue(len(content) > 0)

    def test_chat_completions_streaming_sse(self):
        url = f"http://127.0.0.1:{self.test_port}/v1/chat/completions"
        payload = {
            "model": "qwen2.5-coder:14b",
            "messages": [
                {"role": "user", "content": "عد من 1 إلى 3"}
            ],
            "stream": True
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            self.assertEqual(resp.status, 200)
            self.assertIn("text/event-stream", resp.headers.get("Content-Type", ""))
            data_lines = []
            for line in resp:
                decoded = line.decode("utf-8").strip()
                if decoded:
                    data_lines.append(decoded)
                if "data: [DONE]" in decoded:
                    break
            self.assertGreater(len(data_lines), 0)
            self.assertIn("data: [DONE]", data_lines)


if __name__ == "__main__":
    unittest.main()
