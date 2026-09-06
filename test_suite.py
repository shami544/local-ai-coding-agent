import os
import sys
import unittest
import tempfile
import shutil
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent import parse_json_response, extract_streaming_chat_reply, OllamaAgent
from executor import (
    resolve_safe_path,
    write_code_file,
    write_project_bundle,
    open_file_in_browser,
    execute_script,
    export_project_zip,
    scan_existing_project,
    detect_missing_package,
    ExecutionError
)
from highlighter import get_lexer_for_filename


class TestOllamaChatAgentLogic(unittest.TestCase):
    def test_extract_streaming_chat_reply(self):
        partial = '{\n  "chat_reply": "مرحباً بك! لقد قمت بإنشاء الملف بنجاح.",\n  "project_name": "Test"'
        extracted = extract_streaming_chat_reply(partial)
        self.assertEqual(extracted, "مرحباً بك! لقد قمت بإنشاء الملف بنجاح.")

        # Partial in the middle of streaming
        partial_ongoing = '{\n  "chat_reply": "جاري تجهيز الكود'
        extracted_ongoing = extract_streaming_chat_reply(partial_ongoing)
        self.assertEqual(extracted_ongoing, "جاري تجهيز الكود")
    def test_parse_json_chat_response(self):
        raw = '''{
  "chat_reply": "قمت بإنشاء صفحة الهبوط وملف التنسيق بنجاح.",
  "project_name": "Restaurant Web App",
  "explanation": "المشروع عبارة عن موقع مطعم يحتوي على قائمة طعام وتنسيقات عصرية.",
  "files": [
    {"filepath": "index.html", "code": "<h1>مطعم الأصالة</h1>", "description": "الصفحة الرئيسية"},
    {"filepath": "styles.css", "code": "body { background: #fff; }", "description": "ملف التنسيقات"}
  ]
}'''
        parsed = parse_json_response(raw)
        self.assertTrue(parsed["parse_success"])
        self.assertEqual(parsed["chat_reply"], "قمت بإنشاء صفحة الهبوط وملف التنسيق بنجاح.")
        self.assertEqual(len(parsed["files"]), 2)
        self.assertEqual(parsed["files"][0]["filepath"], "index.html")
        self.assertEqual(parsed["files"][1]["filepath"], "styles.css")

    def test_chat_memory_reset(self):
        agent = OllamaAgent()
        agent.conversation_history.append({"role": "user", "content": "مرحبا"})
        agent.conversation_history.append({"role": "assistant", "content": "أهلاً بك"})
        self.assertEqual(len(agent.conversation_history), 2)
        agent.reset_chat()
        self.assertEqual(len(agent.conversation_history), 0)

    def test_list_models_live(self):
        agent = OllamaAgent()
        models = agent.list_models()
        self.assertIsInstance(models, list)
        self.assertGreater(len(models), 0, "Expected at least one model in Ollama")


class TestExecutor(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_safe_path_resolution(self):
        resolved = resolve_safe_path(self.test_dir, "nested/sub/file.py")
        self.assertTrue(str(resolved).startswith(str(Path(self.test_dir).resolve())))

    def test_path_traversal_prevention(self):
        with self.assertRaises(ExecutionError):
            resolve_safe_path(self.test_dir, "../../escaped.py")

    def test_write_project_bundle(self):
        files = [
            {"filepath": "index.html", "code": "<!DOCTYPE html><html><body><h1>Title</h1></body></html>"},
            {"filepath": "css/style.css", "code": "body { color: red; }"},
            {"filepath": "js/app.js", "code": "console.log('App ready');"}
        ]
        res = write_project_bundle(self.test_dir, files)
        self.assertTrue(res["success"])
        self.assertEqual(res["files_written"], 3)
        self.assertTrue((Path(self.test_dir) / "index.html").exists())
        self.assertTrue((Path(self.test_dir) / "css" / "style.css").exists())
        self.assertTrue((Path(self.test_dir) / "js" / "app.js").exists())

    def test_arabic_utf8_write_and_execute(self):
        code = "# كود تجريبي باللغة العربية\nprint('مرحباً بك في استوديو الشات البرمجي')\n"
        meta = write_code_file(self.test_dir, "scripts/arabic_test.py", code)
        self.assertTrue(meta["success"])

        res = execute_script(self.test_dir, "scripts/arabic_test.py")
        self.assertTrue(res["success"])
        self.assertEqual(res["returncode"], 0)
        self.assertIn("مرحباً بك في استوديو الشات البرمجي", res["stdout"])

    def test_export_project_zip(self):
        write_code_file(self.test_dir, "app.py", "print('hello')")
        write_code_file(self.test_dir, "templates/index.html", "<h1>Hello</h1>")
        zip_out = os.path.join(self.test_dir, "bundle.zip")
        res = export_project_zip(self.test_dir, zip_out)
        self.assertTrue(res["success"])
        self.assertTrue(os.path.exists(zip_out))
        self.assertGreaterEqual(res["file_count"], 2)

    def test_scan_existing_project(self):
        write_code_file(self.test_dir, "main.js", "console.log('main');")
        write_code_file(self.test_dir, "styles.css", "body { color: blue; }")
        scanned = scan_existing_project(self.test_dir)
        filepaths = [f["filepath"] for f in scanned]
        self.assertIn("main.js", filepaths)
        self.assertIn("styles.css", filepaths)

    def test_detect_missing_package(self):
        py_err = "ModuleNotFoundError: No module named 'requests'"
        detected = detect_missing_package(py_err)
        self.assertIsNotNone(detected)
        self.assertEqual(detected["package"], "requests")
        self.assertEqual(detected["manager"], "pip")

        node_err = "Error: Cannot find module 'express'"
        detected_node = detect_missing_package(node_err)
        self.assertIsNotNone(detected_node)
        self.assertEqual(detected_node["package"], "express")
        self.assertEqual(detected_node["manager"], "npm")


class TestHighlighter(unittest.TestCase):
    def test_lexer_resolution(self):
        lexer_py = get_lexer_for_filename("main.py")
        self.assertEqual(lexer_py.name.lower(), "python")
        lexer_html = get_lexer_for_filename("index.html")
        self.assertEqual(lexer_html.name.lower(), "html")
        lexer_css = get_lexer_for_filename("styles.css")
        self.assertEqual(lexer_css.name.lower(), "css")


if __name__ == "__main__":
    unittest.main()
