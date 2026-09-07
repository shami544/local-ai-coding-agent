import io
import json
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from agent import AgentError, OllamaAgent
from web_search import get_search_query, safe_source_url, search_web


def search_result(status="ok"):
    return {"query": "Python asyncio", "status": status, "searched_at": "2026-09-07T00:00:00Z",
            "results": [{"title": "Python docs", "url": "https://docs.python.org/3/library/asyncio.html",
                         "snippet": "Unique retrieved snippet"}] if status == "ok" else [],
            "error": "Search timed out" if status == "error" else ""}


class SearchAdapterTests(unittest.TestCase):
    def test_search_activation_and_off_precedence(self):
        for prompt in ("/search Python asyncio", "search the web for Python asyncio",
                       "ابحث على الإنترنت عن Python asyncio", "لو سمحت ابحث في النت عن Python asyncio"):
            with self.subTest(prompt=prompt):
                self.assertEqual(get_search_query(prompt), "Python asyncio")
                self.assertIsNone(get_search_query(prompt, "off"))
        for prompt in ("مرحبا", "اكتب دالة بحث", "Build a web search tool", "لا تبحث على الإنترنت"):
            self.assertIsNone(get_search_query(prompt))
        self.assertEqual(get_search_query("Python asyncio", "on"), "Python asyncio")

    def test_invalid_query_and_mode(self):
        for prompt, mode in (("/search", "auto"), ("x" * 501, "on"), ("hi", "invalid")):
            with self.subTest(prompt=prompt[:10], mode=mode), self.assertRaises(ValueError):
                get_search_query(prompt, mode)

    def test_unsafe_urls(self):
        for url in ("javascript:alert(1)", "file:///C:/secret", "https://u:p@example.com",
                    "https://example.com/\nfoo", "https://[bad", "https://", None):
            self.assertEqual(safe_source_url(url), "")

    @patch("ddgs.DDGS")
    def test_normalize_bound_and_deduplicate_results(self, ddgs):
        row = {"title": "Docs\n Title", "href": "https://example.com/1", "body": "x" * 3000}
        ddgs.return_value.text.return_value = [None, {"href": "javascript:alert(1)", "body": "bad"}, row, row] + [
            {"title": "Docs", "href": f"https://example.com/{i}", "body": "Snippet"} for i in range(2, 12)
        ]
        result = search_web("Python")
        self.assertEqual(result["status"], "ok")
        self.assertEqual(len(result["results"]), 5)
        self.assertEqual(len(result["results"][0]["snippet"]), 1000)
        self.assertEqual(result["results"][0]["title"], "Docs Title")
        ddgs.assert_called_once_with(timeout=10)

    @patch("ddgs.DDGS")
    def test_empty_and_failure(self, ddgs):
        ddgs.return_value.text.return_value = []
        self.assertEqual(search_web("Python")["status"], "empty")
        ddgs.return_value.text.side_effect = TimeoutError("secret proxy credential")
        result = search_web("Python")
        self.assertEqual(result["status"], "error")
        self.assertNotIn("secret", result["error"])

    def test_missing_dependency(self):
        with patch.dict(sys.modules, {"ddgs": None}):
            result = search_web("Python")
        self.assertEqual(result["status"], "error")
        self.assertIn("pip install", result["error"])


class SearchChatTests(unittest.TestCase):
    def setUp(self):
        self.agent = OllamaAgent()
        self.agent.client = MagicMock()
        self.raw = json.dumps({"chat_reply": "Answer [1]", "files": []})
        self.agent.client.chat.return_value = SimpleNamespace(message=SimpleNamespace(content=self.raw))

    @patch("agent.search_web", return_value=search_result())
    def test_context_sources_privacy_and_next_turn(self, search):
        statuses = []
        result = self.agent.chat_turn("/search Python asyncio", "qwen2.5-coder:14b",
                                      [{"filepath": "private.py", "code": "private workspace content"}],
                                      on_status=statuses.append)
        search.assert_called_once_with("Python asyncio")
        messages = self.agent.client.chat.call_args.kwargs["messages"]
        self.assertIn("Unique retrieved snippet", messages[-1]["content"])
        self.assertIn("private workspace content", messages[-1]["content"])
        self.assertNotIn("Unique retrieved snippet", str(self.agent.conversation_history))
        self.assertEqual(result["model"], "qwen2.5-coder:14b")
        self.assertIn(result["sources"][0]["url"], result["chat_reply"])
        self.assertEqual(statuses, ["searching", "generating"])
        self.agent.chat_turn("Explain that", "qwen2.5-coder:14b")
        self.assertNotIn("Unique retrieved snippet", str(self.agent.client.chat.call_args.kwargs["messages"]))
        search.assert_called_once()

    @patch("agent.search_web", return_value=search_result())
    def test_streaming(self, search):
        self.agent.client.chat.return_value = [SimpleNamespace(message=SimpleNamespace(content=c)) for c in self.raw]
        chunks = []
        result = self.agent.chat_turn("/search Python asyncio", "qwen", on_chunk=lambda p, full: chunks.append(full))
        self.assertEqual(chunks[-1], self.raw)
        self.assertTrue(self.agent.client.chat.call_args.kwargs["stream"])
        self.assertEqual(result["web_search"]["status"], "ok")

    @patch("agent.search_web")
    def test_off_and_normal_chat_make_no_search(self, search):
        for prompt, mode in (("hello", "auto"), ("/search Python", "off")):
            result = self.agent.chat_turn(prompt, "qwen", web_search_mode=mode)
            self.assertNotIn("web_search", result)
        search.assert_not_called()

    @patch("agent.search_web")
    def test_failure_is_visible_and_has_no_sources(self, search):
        for status in ("error", "empty"):
            search.return_value = search_result(status)
            result = self.agent.chat_turn("/search Python", "qwen")
            self.assertEqual(result["sources"], [])
            self.assertIn("لم يتم التحقق", result["chat_reply"])
            self.assertEqual(result["web_search"]["status"], status)

    @patch("agent.search_web", return_value=search_result())
    def test_model_failure_rolls_back_turn(self, search):
        self.agent.conversation_history = [{"role": "user", "content": "earlier"}]
        self.agent.client.chat.side_effect = RuntimeError("Model unavailable")
        with self.assertRaises(AgentError):
            self.agent.chat_turn("/search Python", "qwen")
        self.assertEqual(self.agent.conversation_history, [{"role": "user", "content": "earlier"}])

    @patch("agent.get_anthropic_api_key", return_value="test-key")
    @patch("agent.call_anthropic_messages_api")
    @patch("agent.search_web", return_value=search_result())
    def test_claude_context_and_sources(self, search, api, key):
        api.return_value = self.raw
        result = self.agent.chat_turn("/search Python asyncio", "claude-test", on_chunk=lambda *args: None)
        self.assertIn("Unique retrieved snippet", api.call_args.kwargs["messages"][-1]["content"])
        self.assertTrue(api.call_args.kwargs["stream"])
        self.assertEqual(result["sources"], search_result()["results"])

    @patch("agent.get_anthropic_api_key", return_value="")
    def test_missing_claude_key_rolls_back(self, key):
        with self.assertRaises(AgentError):
            self.agent.chat_turn("hello", "claude-test")
        self.assertEqual(self.agent.conversation_history, [])


class SearchAPITests(unittest.TestCase):
    def test_generate_passes_mode_and_returns_sources(self):
        from api_server import OpenAICompatibleHandler
        handler = MagicMock()
        handler.wfile = io.BytesIO()
        handler.agent.chat_turn.return_value = {"chat_reply": "Answer", "sources": search_result()["results"]}
        OpenAICompatibleHandler._handle_agent_generate(handler, {"prompt": "Python", "model": "qwen",
                                                               "web_search_mode": "on"})
        handler.agent.chat_turn.assert_called_once_with(user_message="Python", model="qwen",
                                                        current_project_files=[], web_search_mode="on")
        handler.send_response.assert_called_once_with(200)
        self.assertEqual(json.loads(handler.wfile.getvalue())["sources"], search_result()["results"])

    def test_bad_mode_is_rejected_before_generation(self):
        from api_server import OpenAICompatibleHandler
        handler = MagicMock()
        handler.wfile = io.BytesIO()
        OpenAICompatibleHandler._handle_agent_generate(handler, {"prompt": "Python", "web_search_mode": "bad"})
        handler.send_response.assert_called_once_with(400)
        handler.agent.chat_turn.assert_not_called()


if __name__ == "__main__":
    unittest.main()
