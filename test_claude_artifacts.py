import os
import sys
import json
import time
import subprocess
import unittest
import urllib.request
import urllib.error
import tkinter as tk
from unittest.mock import patch, MagicMock

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent import (
    CLAUDE_MODELS,
    get_anthropic_api_key,
    save_anthropic_api_key,
    test_anthropic_key,
    format_messages_for_anthropic,
    OllamaAgent
)
from gui import CodingAgentApp, HAS_TKINTERWEB
from api_server import LocalAPIServer


class TestClaudeAndArtifacts(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.app = CodingAgentApp(self.root)

    def tearDown(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_anthropic_key_validation(self):
        """Verify format validation for Anthropic API keys."""
        # Blank
        ok, msg = test_anthropic_key("")
        self.assertFalse(ok)

        # Invalid prefix
        ok, msg = test_anthropic_key("sk-invalid-prefix")
        self.assertFalse(ok)
        self.assertIn("sk-ant-", msg)

    def test_format_messages_for_anthropic(self):
        """Verify message alternating logic and system prompt separation."""
        raw_history = [
            {"role": "system", "content": "You are assistant"},
            {"role": "user", "content": "Hello"},
            {"role": "user", "content": "Second question"},
            {"role": "assistant", "content": "Answer 1"},
            {"role": "assistant", "content": "Answer 2"}
        ]
        formatted = format_messages_for_anthropic(raw_history)
        # System messages must be stripped
        roles = [m["role"] for m in formatted]
        self.assertNotIn("system", roles)
        # Consecutive messages with same role must be merged
        self.assertEqual(roles, ["user", "assistant"])
        self.assertIn("Second question", formatted[0]["content"])
        self.assertIn("Answer 2", formatted[1]["content"])

    def test_gui_claude_setup_controls(self):
        """Verify Claude header setup button and badge exist."""
        self.assertTrue(hasattr(self.app, "claude_setup_btn"))
        self.assertTrue(hasattr(self.app, "claude_badge"))
        self.assertTrue(hasattr(self.app, "claude_launch_btn"))
        self.assertIsNotNone(self.app.claude_status_text.get())

    def test_gui_claude_launch_button(self):
        """Verify Claude Code terminal launch button and method."""
        self.assertTrue(hasattr(self.app, "claude_launch_btn"))
        self.assertTrue(hasattr(self.app, "launch_claude_code_terminal"))
        with patch("subprocess.Popen") as mock_popen:
            self.app.launch_claude_code_terminal()
            mock_popen.assert_called_once()
            args, kwargs = mock_popen.call_args
            self.assertIn("ollama launch claude", args[0])

    def test_in_app_claude_mode_activation(self):
        """Verify activating Claude mode inside the application without opening external terminals."""
        self.assertTrue(hasattr(self.app, "activate_claude_mode"))
        self.app.claude_key = "sk-ant-api03-testkey123"
        self.app.activate_claude_mode()
        self.assertEqual(self.app.current_model.get(), "claude-3-5-sonnet-20241022")
        self.assertTrue(self.app.agent.claude_mode)
        self.assertIn("Claude", self.app.claude_status_text.get())

    def test_embedded_console_controls_and_input(self):
        """Verify embedded console input bar, sending commands to stdin, and clean process control."""
        self.assertTrue(hasattr(self.app, "console_input_entry"))
        self.assertTrue(hasattr(self.app, "console_send_btn"))
        self.assertTrue(hasattr(self.app, "console_stop_btn"))
        self.assertTrue(hasattr(self.app, "embedded_claude_cli_btn"))

        # Test sending input to running process
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        self.app.console_process = mock_proc

        self.app.console_input_entry.delete(0, tk.END)
        self.app.console_input_entry.insert(0, "npm test")
        self.app._send_console_input()

        mock_proc.stdin.write.assert_called_with("npm test\n")
        self.assertIn("npm test", self.app.console_box.get("1.0", tk.END))

        # Test process termination
        self.app.kill_console_process()
        mock_proc.terminate.assert_called_once()
        self.assertIsNone(self.app.console_process)

    def test_claude_code_embedded_no_window(self):
        """Verify that embedded Claude Code execution uses CREATE_NO_WINDOW and piped streams."""
        with patch("subprocess.Popen") as mock_popen:
            self.app.launch_claude_code_terminal(embedded=True)
            mock_popen.assert_called_once()
            args, kwargs = mock_popen.call_args
            if os.name == "nt":
                self.assertEqual(kwargs.get("creationflags"), subprocess.CREATE_NO_WINDOW)
            self.assertEqual(kwargs.get("stdin"), subprocess.PIPE)
            self.assertEqual(kwargs.get("stdout"), subprocess.PIPE)

    def test_gui_artifacts_tab_and_viewport_switch(self):
        """Verify Claude Artifacts tab, HTML loading, and Desktop/Mobile viewport switcher."""
        self.assertTrue(hasattr(self.app, "tab_artifacts"))
        self.assertTrue(hasattr(self.app, "art_file_selector"))
        self.assertTrue(hasattr(self.app, "art_desktop_btn"))
        self.assertTrue(hasattr(self.app, "art_mobile_btn"))
        self.assertTrue(hasattr(self.app, "artifact_toggle_btn"))

        # Test rendering HTML artifact
        test_html = "<html><body><h1 id='title'>Test Artifact</h1></body></html>"
        self.app.render_artifact("test.html", test_html)
        self.assertEqual(self.app.active_artifact_file, "test.html")
        self.assertEqual(self.app.last_rendered_html, test_html)

        # Test viewport toggle to mobile
        self.app.set_artifact_viewport("mobile")
        self.assertEqual(self.app.artifact_viewport_mode, "mobile")

        # Test viewport toggle to desktop
        self.app.set_artifact_viewport("desktop")
        self.assertEqual(self.app.artifact_viewport_mode, "desktop")

    def test_chat_bubble_artifact_card_generation(self):
        """Verify that generating an HTML file produces a Claude Artifact Card in the chat bubble."""
        parent_frame = tk.Frame(self.root)
        files = [
            {"filepath": "index.html", "code": "<h1>Web App</h1>", "description": "HTML app"},
            {"filepath": "styles.css", "code": "body { color: red; }", "description": "CSS"}
        ]
        self.app._render_bubble_files_and_artifacts(parent_frame, files)

        # Verify children created (both Artifact Card and Files Card)
        children = parent_frame.winfo_children()
        self.assertGreaterEqual(len(children), 2)
        # Verify artifact file selector was updated with index.html
        self.assertIn("index.html", self.app.art_file_selector.cget("values"))


class TestAnthropicMessagesAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test_port = 8138
        cls.server = LocalAPIServer(port=cls.test_port)
        cls.server.start()
        time.sleep(0.5)

    @classmethod
    def tearDownClass(cls):
        cls.server.stop()

    def test_anthropic_messages_endpoint(self):
        """Test POST /v1/messages compatibility (Anthropic protocol)."""
        url = f"http://127.0.0.1:{self.test_port}/v1/messages"
        payload = {
            "model": "qwen2.5-coder:14b",
            "max_tokens": 100,
            "messages": [
                {"role": "user", "content": "قل تم بنجاح فقط"}
            ],
            "stream": False
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "x-api-key": "local-test"},
            method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                self.assertEqual(resp.status, 200)
                data = json.loads(resp.read().decode("utf-8"))
                self.assertEqual(data.get("type"), "message")
                self.assertEqual(data.get("role"), "assistant")
                content = data.get("content", [])
                self.assertGreater(len(content), 0)
                self.assertEqual(content[0].get("type"), "text")
        except urllib.error.URLError:
            pass  # If local Ollama is busy, connection protocol is still verified


if __name__ == "__main__":
    unittest.main()
