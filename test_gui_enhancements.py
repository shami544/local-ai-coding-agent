import os
import sys
import tempfile
import shutil
import tkinter as tk
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from gui import CodingAgentApp
from executor import write_code_file


def run_gui_enhancement_tests():
    print("Initializing CodingAgentApp in test mode...")
    root = tk.Tk()
    root.withdraw()  # keep window hidden during automated test

    app = CodingAgentApp(root)
    test_dir = tempfile.mkdtemp()

    try:
        # Test 1: Line Numbers Gutter
        print("Testing Line Numbers Gutter...")
        assert hasattr(app, "line_gutter"), "line_gutter widget missing!"
        sample_code = "\n".join([f"print('Line {i}')" for i in range(1, 25)])
        app.code_box.delete("1.0", tk.END)
        app.code_box.insert("1.0", sample_code)
        app._sync_line_gutter()
        gutter_text = app.line_gutter.get("1.0", tk.END).strip()
        assert "1" in gutter_text and "24" in gutter_text, f"Line numbers not found in gutter: {gutter_text[:30]}..."
        print("  ✓ Line Numbers Gutter synchronized: lines 1 to 24 counted and displayed.")

        # Test 2: Diff Viewer
        print("Testing Diff Viewer...")
        assert hasattr(app, "diff_box"), "diff_box widget missing!"
        assert hasattr(app, "diff_toggle_btn"), "diff_toggle_btn widget missing!"
        app.project_files = [
            {"filepath": "index.html", "code": "<h1>Old Title</h1>", "description": "HTML"}
        ]
        app.active_file_idx = 0
        app.previous_file_versions["index.html"] = "<h1>Old Title</h1>"
        # Now change code
        app.code_box.delete("1.0", tk.END)
        app.code_box.insert("1.0", "<h1>New Updated Title</h1>\n<p>Added paragraph</p>")
        app._render_diff_view()
        diff_content = app.diff_box.get("1.0", tk.END)
        assert "-<h1>Old Title</h1>" in diff_content, f"Expected deletion in diff, got:\n{diff_content}"
        assert "+<h1>New Updated Title</h1>" in diff_content, f"Expected addition in diff, got:\n{diff_content}"
        print("  ✓ Diff Viewer accurately computed unified diff with additions and deletions.")

        # Test 3: Auto-Fix Error Trigger
        print("Testing Auto-Fix Error Trigger...")
        assert hasattr(app, "auto_fix_btn"), "auto_fix_btn widget missing!"
        assert hasattr(app, "install_pkg_btn"), "install_pkg_btn widget missing!"
        # Simulate execution failure with ModuleNotFoundError
        fail_res = {
            "success": False,
            "returncode": 1,
            "stdout": "",
            "stderr": "Traceback (most recent call last):\n  File 'test.py', line 1, in <module>\nModuleNotFoundError: No module named 'requests'",
            "duration": 0.12,
            "timed_out": False
        }
        app._on_execution_completed(fail_res, "test.py")
        assert app.last_failed_file == "test.py"
        assert "requests" in app.last_stderr
        assert app.detected_pkg is not None and app.detected_pkg["package"] == "requests"
        print("  ✓ Auto-Fix & Missing Package Detection triggered correctly on execution failure.")

        # Test 4: Project Tools (ZIP Export & Folder Scanner)
        print("Testing Project Tools (ZIP Export & Folder Scanner)...")
        assert hasattr(app, "export_zip_btn"), "export_zip_btn widget missing!"
        assert hasattr(app, "scan_folder_btn"), "scan_folder_btn widget missing!"
        app.project_dir.set(test_dir)
        write_code_file(test_dir, "test_file.py", "print('hello')")
        write_code_file(test_dir, "test_page.html", "<h1>Hello</h1>")
        app.scan_and_load_folder()
        fps = [f["filepath"] for f in app.project_files]
        assert "test_file.py" in fps and "test_page.html" in fps, f"Files not loaded by scanner: {fps}"
        print("  ✓ Project Scanner indexed and loaded files into studio workspace.")

        # Test 5: Streaming Bubbles
        print("Testing Streaming Bubbles...")
        app._start_streaming_bubble("qwen2.5-coder:14b")
        assert app.streaming_bubble is not None
        app._update_streaming_bubble("أهلاً بك! لقد بدأت التوليد...", 45)
        current_text = app.streaming_bubble["msg_lbl"].cget("text")
        assert "أهلاً بك" in current_text
        app._finalize_streaming_bubble("اكتمل الرد بنجاح.", [{"filepath": "test_file.py", "code": "print('ok')"}], "qwen2.5-coder:14b (1.2s)")
        assert app.streaming_bubble is None
        print("  ✓ Streaming bubble started, updated incrementally, and finalized with file chips.")

        # Test 6: VS Code API Server Controls
        print("Testing VS Code API Server Controls...")
        assert hasattr(app, "api_toggle_btn"), "api_toggle_btn widget missing!"
        assert hasattr(app, "api_copy_btn"), "api_copy_btn widget missing!"
        assert hasattr(app, "api_guide_btn"), "api_guide_btn widget missing!"

        # Use an alternate test port to avoid collision
        app.api_port = 8130
        app.toggle_api_server()
        assert app.api_server is not None and app.api_server.is_running(), "API server failed to start!"
        app.copy_api_url()
        assert "8130" in app.status_message.get()

        app.toggle_api_server()
        assert app.api_server is None, "API server failed to stop!"
        print("  ✓ VS Code API Server started, verified, copied URL, and stopped cleanly.")

        print("\nALL 6 ENHANCEMENT TESTS PASSED SUCCESSFULLY!")

    finally:
        shutil.rmtree(test_dir, ignore_errors=True)
        root.destroy()


if __name__ == "__main__":
    run_gui_enhancement_tests()
