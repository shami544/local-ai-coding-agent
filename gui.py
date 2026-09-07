import os
import sys
import threading
import time
import difflib
import subprocess
import tkinter as tk
from tkinter import filedialog, messagebox
import webbrowser
from pathlib import Path
from typing import Optional, List, Dict, Any

try:
    import tkinterweb
    HAS_TKINTERWEB = True
except Exception:
    HAS_TKINTERWEB = False

import customtkinter as ctk

from agent import (
    OllamaAgent,
    AgentError,
    extract_streaming_chat_reply,
    get_anthropic_api_key,
    save_anthropic_api_key,
    test_anthropic_key,
    CLAUDE_MODELS
)
from executor import (
    write_code_file,
    write_project_bundle,
    open_file_in_browser,
    execute_script,
    export_project_zip,
    scan_existing_project,
    detect_missing_package,
    install_package,
    ExecutionError
)
from highlighter import CodeHighlighter
from api_server import LocalAPIServer

# CustomTkinter Styling
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

# Quick inspiration project templates
INSPIRATIONS = {
    "ar": [
        ("🌐 صفحة هبوط لشركة تقنية", "ابنِ موقع صفحة هبوط (Landing Page) عصرية وفخمة لشركة تقنية ناشئة مع شريط تنقل متجاوب، قسم خدمات بمؤثرات بصرية، قسم أسعار، ونموذج تواصل تفاعلي، مقسمة إلى: index.html و styles.css و script.js."),
        ("📊 لوحة تحكم Dashboard", "أنشئ لوحة تحكم تفاعلية متجاوبة (Analytics Dashboard) تحتوي على بطاقات إحصائيات، رسم بياني مرئي، وجدول بيانات متفاعل مع الوضع الداكن، مقسمة إلى index.html و styles.css و script.js."),
        ("⚡ تطبيق Flask REST API", "أنشئ خادم واجهة برمجية مصغر بلغة بايثون باستخدام Flask مع توثيق للـ endpoints، وحفظ البيانات في SQLite، مع ملف requirements.txt وسكربت اختبار test_api.py."),
        ("🎮 لعبة ويب تفاعلية", "أنشئ لعبة متصفح كلاسيكية ممتعة (مثل لعبة Snake أو Memory Cards) بتصميم جذاب ومؤثرات صوتية ومؤقت نقاط، مقسمة إلى index.html و styles.css و script.js.")
    ],
    "en": [
        ("🌐 Tech Landing Page", "Build a modern, sleek landing page for a tech startup with responsive navbar, hero section, interactive services grid, pricing cards, and contact form, structured across: index.html, styles.css, and script.js."),
        ("📊 Analytics Dashboard", "Create a responsive analytics dashboard with stat metric cards, data visualization charts, dark mode toggle, and interactive data table, split into index.html, styles.css, and script.js."),
        ("⚡ Flask REST API", "Build a lightweight Flask REST API with SQLite database, user CRUD endpoints, requirements.txt, and a test script."),
        ("🎮 Interactive Web Game", "Create a fun browser game (e.g. Classic Snake or Memory Match) with modern UI, score tracking, and smooth animations using index.html, styles.css, and script.js.")
    ]
}

# Localization dictionary
TRANSLATIONS: Dict[str, Dict[str, str]] = {
    "ar": {
        "app_title": "استوديو المساعد البرمجي الذكي (Ollama Chat & Code Studio)",
        "header_title": "⚡ استوديو الذكاء الاصطناعي البرمجي",
        "header_subtitle": " (Ollama Chat & Code Studio)",
        "checking_ollama": "جاري فحص Ollama...",
        "connected": "● متصل ({count} نماذج)",
        "offline": "● غير متصل بـ Ollama",
        "dark_mode": "الوضع الداكن",
        "model_label": "نموذج الذكاء الاصطناعي",
        "refresh_btn": "🔄 تحديث",
        "project_label": "مسار المشروع",
        "browse_btn": "📁 استعراض",
        "open_folder_btn": "📂 فتح",
        "chat_title": "المحادثة",
        "new_chat_btn": "🔄 محادثة جديدة",
        "welcome_msg": "مرحباً بك! أنا مساعدك البرمجي الذكي. اكتب لي أي موقع أو برنامج تريد بناءه، وسأقوم بإنشائه ومساعدتك في تعديله وتطويره خطوة بخطوة في هذا الشات.",
        "chat_input_placeholder": "اكتب طلبك أو تعديلك هنا (مثال: ابنِ لي موقع متجر إلكتروني، أو غيّر لون الخلفية للأزرق)...",
        "send_btn": "🚀 إرسال / Send",
        "cancel_btn": "✕ إلغاء",
        "shortcut_hint": "(Enter أو Ctrl+Enter للإرسال)",
        "files_toolbar_lbl": "ملفات المشروع",
        "active_file_lbl": "الملف المعروض",
        "save_all_btn": "حفظ المشروع",
        "save_active_btn": "💾 حفظ هذا الملف",
        "open_browser_btn": "🌐 فتح في المتصفح",
        "run_code_btn": "▶ تشغيل الكود",
        "tab_code": "الكود",
        "tab_diff": "الفروقات",
        "tab_explanation": "الملاحظات",
        "tab_console": "الطرفية",
        "diff_btn": "🔀 عرض الفروقات",
        "export_zip_btn": "📦 تصدير ZIP",
        "scan_folder_btn": "📥 فحص المجلد",
        "auto_fix_btn": "🪄 أصلح هذا الخطأ تلقائياً",
        "install_pkg_btn": "📦 تثبيت الحزمة تلقائياً",
        "streaming_typing": "المساعد يكتب الآن... ⏳",
        "no_diff_msg": "✓ لا توجد فروقات سابقة لهذا الملف (الملف جديد أو لم يطرأ عليه تغيير).",
        "copy_code_btn": "📋 نسخ الكود",
        "rehighlight_btn": "🎨 إعادة التلوين",
        "clear_console_btn": "🗑 مسح المخرجات",
        "ready_status": "جاهز. اكتب فكرتك في الشات وسيبدأ المساعد في بنائها.",
        "copied_toast": "تم نسخ الكود إلى الحافظة بنجاح!",
        "save_all_success_title": "تم حفظ كامل المشروع",
        "save_all_success_msg": "تم حفظ جميع ملفات المشروع بنجاح ({count} ملفات) في:\n{dir}",
        "save_success_title": "تم حفظ الملف",
        "save_success_msg": "تم حفظ الملف بنجاح:\n{path}",
        "zip_success_title": "تم تصدير ZIP",
        "zip_success_msg": "تم إنشاء ملف ZIP المضغوط بنجاح:\n{path}",
        "scan_success_title": "تم فحص المجلد",
        "scan_success_msg": "تم العثور على {count} ملفات وتحميلها إلى الاستوديو بنجاح!",
        "scan_empty_msg": "المجلد لا يحتوي على ملفات نصية برمجية مدعومة.",
        "console_placeholder": "ستظهر مخرجات التشغيل والأخطاء هنا عند تشغيل الأكواد.\n",
        "no_model_title": "لم يتم اختيار نموذج",
        "no_model_msg": "يرجى اختيار نموذج Ollama صالح قبل البدء.",
        "empty_prompt_title": "الرسالة فارغة",
        "empty_prompt_msg": "يرجى كتابة رسالتك في الشات قبل الإرسال.",
        "ollama_offline_msg": "تعذر الاتصال بـ Ollama. تأكد من تشغيل 'ollama serve'.",
        "no_models_found": "لا توجد نماذج. شغّل 'ollama pull qwen2.5-coder'.",
        "api_server_btn": "🔌 خادم VS Code API",
        "api_server_running": "🟢 نشط ({port})",
        "api_server_stopped": "⚪ متوقف",
        "api_copy_url": "📋 نسخ الرابط",
        "api_guide_btn": "ℹ️ ربط VS Code",
        "api_copied_toast": "تم نسخ رابط API ({url}) إلى الحافظة بنجاح!",
        "api_guide_title": "دليل ربط استوديو الذكاء الاصطناعي مع VS Code",
        "api_started_msg": "✓ تم تشغيل خادم VS Code API بنجاح على المنفذ {port}.",
        "api_stopped_msg": "تم إيقاف خادم VS Code API.",
        "tab_artifacts": "المعاينة",
        "claude_key_btn": "🔑 مفتاح Claude",
        "claude_active_badge": "🟢 Claude جاهز",
        "claude_inactive_badge": "⚪ Claude غير مفعل",
        "claude_setup_title": "إعدادات نماذج Anthropic Claude",
        "claude_key_lbl": "مفتاح Anthropic API (يبدأ بـ sk-ant-):",
        "claude_key_saved": "✓ تم حفظ مفتاح Claude وتحديث قائمة النماذج بنجاح!",
        "claude_test_btn": "⚡ اختبار الاتصال",
        "claude_save_btn": "💾 حفظ وتفعيل",
        "claude_remove_btn": "🗑️ حذف المفتاح",
        "artifact_preview_mode": "👁️ المعاينة الحية",
        "artifact_code_mode": "💻 شفرة الأرتيفاكت",
        "artifact_refresh_btn": "🔄 تحديث المعاينة",
        "artifact_browser_btn": "🌐 فتح في المتصفح",
        "artifact_desktop_btn": "💻 شاشة كاملة",
        "artifact_mobile_btn": "📱 جوال (375px)",
        "artifact_card_title": "🎨 أرتيفاكت تفاعلي: {name}",
        "artifact_preview_card_btn": "👁️ معاينة الأرتيفاكت",
        "artifact_in_browser_btn": "🌐 في المتصفح",
        "launch_claude_code_btn": "🤖 استخدام Claude",
        "claude_code_launched": "✓ تم تفعيل وضع Claude داخل التطبيق بنجاح!",
        "claude_mode_activated": "✨ تم تفعيل وضع Claude داخل التطبيق بنجاح!",
        "console_input_placeholder": "اكتب أمراً للكونسول أو رداً تفاعلياً هنا...",
        "console_send_btn": "إرسال ↵",
        "console_stop_btn": "⏹️ إيقاف",
        "console_run_claude_btn": "🚀 تشغيل Claude CLI هنا",
        "options_btn": "☰ الخيارات",
        "options_title": "إعدادات الاستوديو",
        "section_model": "النموذج والذكاء الاصطناعي",
        "section_project": "المشروع والملفات",
        "section_tools": "أدوات المحرّر",
        "section_connections": "الربط مع VS Code",
        "section_appearance": "اللغة والمظهر",
        "close_options": "إغلاق",
    },
    "en": {
        "app_title": "AI Coding Studio (Ollama Chat & Code Studio)",
        "header_title": "⚡ AI Coding Agent Studio",
        "header_subtitle": " (Ollama Chat & Code Studio)",
        "checking_ollama": "Checking Ollama...",
        "connected": "● Connected ({count} models)",
        "offline": "● Ollama Offline",
        "dark_mode": "Dark Mode",
        "model_label": "Coding Model",
        "refresh_btn": "🔄 Refresh",
        "project_label": "Project Path",
        "browse_btn": "📁 Browse",
        "open_folder_btn": "📂 Open",
        "chat_title": "Chat",
        "new_chat_btn": "🔄 New Chat",
        "welcome_msg": "Hello! I am your local AI coding assistant. Tell me what website or application you want to build, and we can develop, modify, and iterate on it step by step right here.",
        "chat_input_placeholder": "Type your message or requested edit here (e.g., Build a personal portfolio site, or change the hero title)...",
        "send_btn": "🚀 Send",
        "cancel_btn": "✕ Cancel",
        "shortcut_hint": "(Enter or Ctrl+Enter to send)",
        "files_toolbar_lbl": "Project Files",
        "active_file_lbl": "Active File",
        "save_all_btn": "Save project",
        "save_active_btn": "💾 Save Active File",
        "open_browser_btn": "🌐 Open in Browser",
        "run_code_btn": "▶ Run Code",
        "tab_code": "Code",
        "tab_diff": "Diff",
        "tab_explanation": "Notes",
        "tab_console": "Console",
        "diff_btn": "🔀 View Diff",
        "export_zip_btn": "📦 Export ZIP",
        "scan_folder_btn": "📥 Scan Folder",
        "auto_fix_btn": "🪄 Auto-Fix This Error",
        "install_pkg_btn": "📦 Install Package",
        "streaming_typing": "Agent is typing... ⏳",
        "no_diff_msg": "✓ No prior diff for this file (file is new or unchanged).",
        "copy_code_btn": "📋 Copy Code",
        "rehighlight_btn": "🎨 Re-Highlight",
        "clear_console_btn": "🗑 Clear Console",
        "ready_status": "Ready. Chat with the agent to start building.",
        "copied_toast": "Code copied to clipboard!",
        "save_all_success_title": "Project Saved",
        "save_all_success_msg": "All {count} project files saved successfully to:\n{dir}",
        "save_success_title": "File Saved",
        "save_success_msg": "File saved successfully:\n{path}",
        "zip_success_title": "ZIP Exported",
        "zip_success_msg": "Project ZIP archive created successfully:\n{path}",
        "scan_success_title": "Folder Scanned",
        "scan_success_msg": "Found and loaded {count} project files into studio!",
        "scan_empty_msg": "No supported code files found in selected directory.",
        "console_placeholder": "Terminal stdout/stderr output will appear here.\n",
        "no_model_title": "No Model Selected",
        "no_model_msg": "Please select a valid Ollama model before generating.",
        "empty_prompt_title": "Empty Message",
        "empty_prompt_msg": "Please type a message before sending.",
        "ollama_offline_msg": "Cannot connect to Ollama. Make sure 'ollama serve' is running.",
        "no_models_found": "No models found. Run 'ollama pull qwen2.5-coder'.",
        "api_server_btn": "🔌 VS Code API Server",
        "api_server_running": "🟢 Online ({port})",
        "api_server_stopped": "⚪ Offline",
        "api_copy_url": "📋 Copy URL",
        "api_guide_btn": "ℹ️ VS Code Setup",
        "api_copied_toast": "API endpoint ({url}) copied to clipboard!",
        "api_guide_title": "VS Code Connection Guide (Continue & Cline)",
        "api_started_msg": "✓ VS Code API Server started on port {port}.",
        "api_stopped_msg": "VS Code API Server stopped.",
        "tab_artifacts": "Preview",
        "claude_key_btn": "🔑 Claude Key",
        "claude_active_badge": "🟢 Claude Ready",
        "claude_inactive_badge": "⚪ Claude Offline",
        "claude_setup_title": "Anthropic Claude Model Settings",
        "claude_key_lbl": "Anthropic API Key (starts with sk-ant-):",
        "claude_key_saved": "✓ Claude API key saved and models loaded successfully!",
        "claude_test_btn": "⚡ Test Connection",
        "claude_save_btn": "💾 Save & Activate",
        "claude_remove_btn": "🗑️ Remove Key",
        "artifact_preview_mode": "👁️ Live Preview",
        "artifact_code_mode": "💻 Artifact Code",
        "artifact_refresh_btn": "🔄 Refresh Preview",
        "artifact_browser_btn": "🌐 Open in Browser",
        "artifact_desktop_btn": "💻 Desktop",
        "artifact_mobile_btn": "📱 Mobile (375px)",
        "artifact_card_title": "🎨 Interactive Artifact: {name}",
        "artifact_preview_card_btn": "👁️ Preview Artifact",
        "artifact_in_browser_btn": "🌐 In Browser",
        "launch_claude_code_btn": "🤖 Use Claude",
        "claude_code_launched": "✓ Claude Mode activated in application!",
        "claude_mode_activated": "✨ Claude Mode activated inside the app successfully!",
        "console_input_placeholder": "Type command or interactive reply here...",
        "console_send_btn": "Send ↵",
        "console_stop_btn": "⏹️ Stop",
        "console_run_claude_btn": "🚀 Run Claude CLI Here",
        "options_btn": "☰ Options",
        "options_title": "Studio settings",
        "section_model": "Model & AI",
        "section_project": "Project & files",
        "section_tools": "Editor tools",
        "section_connections": "VS Code connection",
        "section_appearance": "Language & appearance",
        "close_options": "Close",
    }
}


def get_file_icon(filepath: str) -> str:
    ext = os.path.splitext(filepath)[1].lower()
    mapping = {
        ".html": "🌐",
        ".htm": "🌐",
        ".css": "🎨",
        ".js": "⚡",
        ".ts": "⚡",
        ".py": "🐍",
        ".json": "📦",
        ".md": "📝",
        ".sql": "🗄️",
        ".txt": "📄",
    }
    return mapping.get(ext, "📄")


class CodingAgentApp:
    def __init__(self, root: ctk.CTk):
        self.root = root
        self.lang = "ar"  # Default to Arabic
        self.t = TRANSLATIONS[self.lang]
        self.is_rtl = (self.lang == "ar")

        self.root.title(self.t["app_title"])
        self.root.geometry("1320x890")
        self.root.minsize(1100, 750)

        # State variables
        self.agent = OllamaAgent()
        self.models: List[str] = []
        self.current_model = ctk.StringVar(value="")
        self.web_search_mode = "auto"
        self.project_dir = ctk.StringVar(
            value=str(Path(os.getcwd()) / "workspace")
        )
        self.status_message = ctk.StringVar(value=self.t["ready_status"])
        self.connection_status = ctk.StringVar(value=self.t["checking_ollama"])
        self.is_generating = False
        self.options_visible = False
        self.cancel_requested = False

        # Multi-file project buffer
        self.project_files: List[Dict[str, str]] = [
            {"filepath": "index.html", "code": "", "description": "Main HTML"}
        ]
        self.active_file_idx = 0
        self.active_filepath = ctk.StringVar(value="index.html")

        # Studio Enhancements State
        self._current_line_count = 0
        self.streaming_bubble: Optional[Dict[str, Any]] = None
        self.detected_pkg: Optional[Dict[str, str]] = None
        self.last_failed_file: str = ""
        self.last_stderr: str = ""
        self.previous_file_versions: Dict[str, str] = {}

        # VS Code Local API Server State
        self.api_server: Optional[LocalAPIServer] = None
        self.api_port = 8000
        self.api_status_text = ctk.StringVar(value=self.tr("api_server_stopped"))

        # Claude & Artifacts State
        self.claude_key: str = get_anthropic_api_key()
        self.claude_status_text = ctk.StringVar(
            value=self.tr("claude_active_badge") if self.claude_key else self.tr("claude_inactive_badge")
        )
        self.active_artifact_file: Optional[str] = None
        self.last_rendered_html: str = ""
        self.artifact_viewport_mode: str = "desktop"

        # Embedded Console Process State (In-App Terminal)
        self.console_process: Optional[subprocess.Popen] = None
        self.console_reader_thread: Optional[threading.Thread] = None

        # Main window container
        self.main_container = ctk.CTkFrame(self.root, fg_color="transparent")
        self.main_container.pack(fill="both", expand=True)

        # Build Side-by-Side Chat & Code Studio Layout
        self._build_studio_layout()

        # Keyboard shortcuts & Clean exit handler
        self.root.bind("<Control-Return>", lambda event: self.send_chat_message())
        self.root.bind("<Escape>", lambda event: self._toggle_options_panel(False))
        self.root.bind("<ButtonPress>", self._on_options_outside_click, add="+")
        self.root.protocol("WM_DELETE_WINDOW", self._on_window_close)

        # Asynchronous model discovery
        threading.Thread(target=self.refresh_models, daemon=True).start()

    @property
    def side_start(self) -> str:
        return "right" if self.is_rtl else "left"

    @property
    def side_end(self) -> str:
        return "left" if self.is_rtl else "right"

    @property
    def text_anchor(self) -> str:
        return "e" if self.is_rtl else "w"

    def tr(self, key: str, **kwargs) -> str:
        template = TRANSLATIONS.get(self.lang, TRANSLATIONS["ar"]).get(key, key)
        if kwargs:
            return template.format(**kwargs)
        return template

    # -------------------------------------------------------------------------
    # Layout Builder: Side-by-Side Studio
    # -------------------------------------------------------------------------

    def _build_studio_layout(self):
        self._create_header()
        self._create_options_panel()

        # Split container
        self.split_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.split_frame.pack(fill="both", expand=True, padx=12, pady=(4, 10))

        # Side-by-side ordering based on RTL
        if self.is_rtl:
            # Chat on Right, Editor on Left
            self._create_chat_panel(self.split_frame, side="right")
            self._create_workspace_panel(self.split_frame, side="left")
        else:
            # Chat on Left, Editor on Right
            self._create_chat_panel(self.split_frame, side="left")
            self._create_workspace_panel(self.split_frame, side="right")

        if self.options_visible:
            self._toggle_options_panel(True)
        self._toggle_theme()

    def _create_header(self):
        header = ctk.CTkFrame(self.main_container, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(16, 12))
        self.options_btn = ctk.CTkButton(
            header, text=self.tr("options_btn"), width=110, height=36,
            corner_radius=10, command=self._toggle_options_panel)
        self.options_btn.pack(side=self.side_start, padx=8)
        title_box = ctk.CTkFrame(header, fg_color="transparent")
        title_box.pack(side=self.side_start, padx=8)
        self.title_label = ctk.CTkLabel(
            title_box, text=self.tr("header_title"), anchor=self.text_anchor,
            font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"))
        self.title_label.pack(fill="x")
        self.subtitle_label = ctk.CTkLabel(
            title_box, text="Ollama Chat & Code Studio", anchor=self.text_anchor,
            text_color=("gray40", "gray65"), font=ctk.CTkFont(size=11))
        self.subtitle_label.pack(fill="x")
        self.status_badge = ctk.CTkLabel(
            header, textvariable=self.connection_status, corner_radius=10,
            fg_color=("gray90", "#222530"), text_color="#d99421", padx=12)
        self.status_badge.pack(side=self.side_end, padx=8)

    def _option_section(self, key):
        card = ctk.CTkFrame(self.options_scroll, corner_radius=10,
                            fg_color=("#ffffff", "#222530"))
        card.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(
            card, text=self.tr(key), anchor=self.text_anchor,
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold")
        ).pack(fill="x", padx=14, pady=(10, 4))
        body = ctk.CTkFrame(card, fg_color="transparent")
        body.pack(fill="x", padx=12, pady=(0, 12))
        return body

    def _option_button(self, parent, key, command):
        button = ctk.CTkButton(
            parent, text=self.tr(key), command=command, height=34,
            anchor=self.text_anchor, corner_radius=8,
            fg_color=("#e8edf5", "#303646"),
            text_color=("#202b40", "#e2e8f0"),
            hover_color=("#d8e2f0", "#3d4760"),
            font=ctk.CTkFont(family="Segoe UI", size=12))
        button.pack(fill="x", pady=3)
        return button

    def _create_options_panel(self):
        # Overlay keeps the workspace width unchanged when opening settings.
        self.options_panel = ctk.CTkFrame(
            self.main_container, width=340, corner_radius=14, border_width=1,
            border_color=("#cbd5e1", "#394155"),
            fg_color=("#f1f5f9", "#191d27"))
        self.options_panel.pack_propagate(False)
        top = ctk.CTkFrame(self.options_panel, fg_color="transparent")
        top.pack(fill="x", padx=16, pady=(14, 10))
        ctk.CTkLabel(top, text=self.tr("options_title"),
                     font=ctk.CTkFont(size=17, weight="bold")).pack(side=self.side_start)
        self.close_options_btn = ctk.CTkButton(
            top, text=self.tr("close_options"), width=65, height=30,
            command=lambda: self._toggle_options_panel(False))
        self.close_options_btn.pack(side=self.side_end)
        self.options_scroll = ctk.CTkScrollableFrame(
            self.options_panel, fg_color="transparent")
        self.options_scroll.pack(fill="both", expand=True, padx=8, pady=(0, 10))

        model = self._option_section("section_model")
        self.model_lbl = ctk.CTkLabel(model, text=self.tr("model_label"), anchor=self.text_anchor)
        self.model_lbl.pack(fill="x")
        self.model_dropdown = ctk.CTkComboBox(
            model, variable=self.current_model, values=self.models or ["Searching..."],
            state="readonly", height=34)
        self.model_dropdown.pack(fill="x", pady=(0, 6))
        self.refresh_btn = self._option_button(
            model, "refresh_btn", lambda: threading.Thread(target=self.refresh_models, daemon=True).start())
        self.claude_launch_btn = self._option_button(model, "launch_claude_code_btn", self.activate_claude_mode)
        self.claude_setup_btn = self._option_button(model, "claude_key_btn", self.show_claude_settings_dialog)
        self.claude_badge = ctk.CTkLabel(model, textvariable=self.claude_status_text,
                                        text_color="#10b981" if self.claude_key else "#94a3b8")
        self.claude_badge.pack(fill="x")

        project = self._option_section("section_project")
        ctk.CTkLabel(project, text=self.tr("project_label"), anchor=self.text_anchor).pack(fill="x")
        self.dir_entry = ctk.CTkEntry(project, textvariable=self.project_dir, height=34)
        self.dir_entry.pack(fill="x", pady=(0, 6))
        self.browse_btn = self._option_button(project, "browse_btn", self._browse_directory)
        self.open_folder_btn = self._option_button(project, "open_folder_btn", self._open_project_folder)
        self.scan_folder_btn = self._option_button(project, "scan_folder_btn", self.scan_and_load_folder)
        self.export_zip_btn = self._option_button(project, "export_zip_btn", self.export_project_as_zip)
        self.open_browser_btn = self._option_button(project, "open_browser_btn", self.open_in_browser)

        editor = self._option_section("section_tools")
        self.copy_btn = self._option_button(editor, "copy_code_btn", self._copy_code_to_clipboard)
        self.diff_toggle_btn = self._option_button(editor, "diff_btn", self.toggle_diff_view)
        self.artifact_toggle_btn = self._option_button(editor, "tab_artifacts", self.open_artifact_tab)
        self.rehighlight_btn = self._option_button(editor, "rehighlight_btn", self._apply_syntax_highlighting)

        connection = self._option_section("section_connections")
        self.api_badge = ctk.CTkLabel(connection, textvariable=self.api_status_text, text_color="#94a3b8")
        self.api_badge.pack(fill="x")
        self.api_toggle_btn = self._option_button(connection, "api_server_btn", self.toggle_api_server)
        self.api_copy_btn = self._option_button(connection, "api_copy_url", self.copy_api_url)
        self.api_guide_btn = self._option_button(connection, "api_guide_btn", self.show_vscode_guide)
        if self.api_server and self.api_server.is_running():
            self.api_badge.configure(text_color="#10b981")
            self.api_toggle_btn.configure(fg_color="#059669", text="✓ " + self.tr("api_server_btn"))

        appearance = self._option_section("section_appearance")
        self.lang_selector = ctk.CTkSegmentedButton(
            appearance, values=["العربية", "English"], command=self._on_language_change)
        self.lang_selector.set("العربية" if self.is_rtl else "English")
        self.lang_selector.pack(fill="x", pady=(4, 12))
        self.theme_switch = ctk.CTkSwitch(appearance, text=self.tr("dark_mode"), command=self._toggle_theme)
        if ctk.get_appearance_mode() == "Dark":
            self.theme_switch.select()
        self.theme_switch.pack(anchor=self.text_anchor, pady=4)

    def _on_options_outside_click(self, event):
        if not self.options_visible:
            return

        widget = event.widget
        while widget is not None:
            # Include child widgets and the toggle button in the menu area.
            if widget in (self.options_panel, self.options_btn):
                return
            widget = getattr(widget, "master", None)

        self._toggle_options_panel(False, restore_focus=False)

    def _toggle_options_panel(self, visible=None, *, restore_focus=True):
        self.options_visible = not self.options_visible if visible is None else visible
        if self.options_visible:
            self.options_panel.place(
                relx=1.0 if self.is_rtl else 0.0, x=-16 if self.is_rtl else 16,
                rely=0.11, relheight=0.87, anchor="ne" if self.is_rtl else "nw")
            self.options_panel.lift()
            self.close_options_btn.focus_set()
        else:
            self.options_panel.place_forget()
            if restore_focus:
                self.options_btn.focus_set()

    # -------------------------------------------------------------------------
    # Panel 1: Interactive Chat Stream
    # -------------------------------------------------------------------------

    def _create_chat_panel(self, parent, side: str):
        self.chat_frame = ctk.CTkFrame(parent, width=460, corner_radius=12)
        self.chat_frame.pack(side=side, fill="both", padx=5, pady=0)
        self.chat_frame.pack_propagate(False)

        # Header with New Chat Button
        c_head = ctk.CTkFrame(self.chat_frame, fg_color="transparent")
        c_head.pack(fill="x", padx=12, pady=(10, 4))

        self.chat_title_lbl = ctk.CTkLabel(
            c_head,
            text=self.tr("chat_title"),
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            anchor=self.text_anchor
        )
        self.chat_title_lbl.pack(side=self.side_start)

        self.new_chat_btn = ctk.CTkButton(
            c_head,
            text=self.tr("new_chat_btn"),
            font=ctk.CTkFont(family="Segoe UI", size=11),
            width=90,
            height=26,
            fg_color="gray30",
            hover_color="gray40",
            command=self.start_new_chat
        )
        self.new_chat_btn.pack(side=self.side_end)

        # Scrollable Chat Messages Stream
        self.chat_scroll = ctk.CTkScrollableFrame(
            self.chat_frame,
            corner_radius=8,
            fg_color=("gray95", "#16181f")
        )
        self.chat_scroll.pack(fill="both", expand=True, padx=10, pady=4)

        # Initial welcome message from AI Agent
        self._add_agent_bubble(
            message=self.tr("welcome_msg"),
            files=None,
            model_info=None
        )

        # Quick Suggestions Card
        insp_box = ctk.CTkFrame(self.chat_frame, fg_color="transparent")
        insp_box.pack(fill="x", padx=10, pady=(2, 4))

        insp_scroll = ctk.CTkScrollableFrame(insp_box, height=42, orientation="horizontal", fg_color="transparent")
        insp_scroll.pack(fill="x")

        for title, prompt_text in INSPIRATIONS.get(self.lang, INSPIRATIONS["ar"]):
            chip = ctk.CTkButton(
                insp_scroll,
                text=title,
                font=ctk.CTkFont(family="Segoe UI", size=11),
                height=26,
                corner_radius=13,
                fg_color=("gray85", "#272a34"),
                text_color=("gray10", "gray90"),
                hover_color=("gray75", "#353945"),
                command=lambda p=prompt_text: self._set_chat_input(p)
            )
            chip.pack(side=self.side_start, padx=3)

        # Chat Input Area
        input_container = ctk.CTkFrame(self.chat_frame, fg_color=("gray90", "#21242d"), corner_radius=10)
        input_container.pack(fill="x", padx=10, pady=(0, 10))

        search_bar = ctk.CTkFrame(input_container, fg_color="transparent")
        search_bar.pack(fill="x", padx=8, pady=(6, 0))
        ctk.CTkLabel(search_bar, text="بحث الإنترنت" if self.is_rtl else "Web search",
                     font=ctk.CTkFont(family="Segoe UI", size=11)).pack(side=self.side_start)
        search_labels = ["تلقائي", "مفعّل", "متوقف"] if self.is_rtl else ["Auto", "On", "Off"]
        search_modes = ["auto", "on", "off"]
        self.web_search_dropdown = ctk.CTkOptionMenu(
            search_bar, values=search_labels, width=95, height=24,
            command=lambda label: setattr(self, "web_search_mode", search_modes[search_labels.index(label)])
        )
        self.web_search_dropdown.set(search_labels[search_modes.index(self.web_search_mode)])
        self.web_search_dropdown.pack(side=self.side_start, padx=6)
        ctk.CTkLabel(search_bar, text="/search موضوع" if self.is_rtl else "/search topic",
                     font=ctk.CTkFont(size=11), text_color="gray60").pack(side=self.side_end)

        self.chat_textbox = ctk.CTkTextbox(
            input_container,
            height=65,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            fg_color="transparent"
        )
        self.chat_textbox.pack(fill="x", padx=8, pady=(6, 2))
        self._apply_textbox_alignment(self.chat_textbox)

        # Real-time RTL alignment bindings
        self.chat_textbox._textbox.bind("<<Modified>>", lambda e: self._apply_textbox_alignment(self.chat_textbox))
        self.chat_textbox._textbox.bind("<KeyRelease>", lambda e: self._apply_textbox_alignment(self.chat_textbox))
        self.chat_textbox._textbox.bind("<FocusIn>", lambda e: self._apply_textbox_alignment(self.chat_textbox))
        self.chat_textbox.bind("<Return>", self._on_chat_return)

        # Buttons and progress bar
        action_bar = ctk.CTkFrame(input_container, fg_color="transparent")
        action_bar.pack(fill="x", padx=8, pady=(0, 6))

        self.send_btn = ctk.CTkButton(
            action_bar,
            text=self.tr("send_btn"),
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            height=30,
            fg_color="#1d4ed8",
            hover_color="#1e40af",
            command=self.send_chat_message
        )
        self.send_btn.pack(side=self.side_start, padx=(0, 6) if not self.is_rtl else (6, 0))

        self.cancel_btn = ctk.CTkButton(
            action_bar,
            text=self.tr("cancel_btn"),
            width=65,
            height=30,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            fg_color="#b22222",
            hover_color="#8b0000",
            state="disabled",
            command=self.cancel_generation
        )
        self.cancel_btn.pack(side=self.side_start, padx=(0, 6) if not self.is_rtl else (6, 0))

        self.progress_bar = ctk.CTkProgressBar(action_bar, mode="indeterminate", height=6)
        self.progress_bar.pack(side=self.side_start, fill="x", expand=True, padx=4)
        self.progress_bar.set(0)

    def _on_chat_return(self, event):
        """Send message on Enter (unless Shift is held)."""
        if not (event.state & 0x0001):  # Shift not pressed
            self.send_chat_message()
            return "break"
        return None

    def _set_chat_input(self, text: str):
        self.chat_textbox.delete("1.0", tk.END)
        self.chat_textbox.insert("1.0", text)
        self._apply_textbox_alignment(self.chat_textbox)

    # -------------------------------------------------------------------------
    # Chat Bubble Rendering
    # -------------------------------------------------------------------------

    def _add_user_bubble(self, message: str):
        bubble_frame = ctk.CTkFrame(
            self.chat_scroll,
            fg_color=("gray85", "#2c313d"),
            corner_radius=12
        )
        bubble_frame.pack(fill="x", padx=8, pady=4)

        header = ctk.CTkLabel(
            bubble_frame,
            text="👤 " + ("أنت" if self.is_rtl else "You"),
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=("#1d4ed8", "#60a5fa"),
            anchor=self.text_anchor
        )
        header.pack(fill="x", padx=10, pady=(6, 2))

        msg_lbl = ctk.CTkLabel(
            bubble_frame,
            text=message,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            wraplength=400,
            justify="right" if self.is_rtl else "left",
            anchor=self.text_anchor
        )
        msg_lbl.pack(fill="x", padx=10, pady=(0, 8))

        self._scroll_chat_to_bottom()

    def _add_agent_bubble(self, message: str, files: Optional[List[Dict[str, str]]] = None, model_info: Optional[str] = None):
        bubble_frame = ctk.CTkFrame(
            self.chat_scroll,
            fg_color=("gray90", "#1c202a"),
            border_width=1,
            border_color=("gray80", "#2d3342"),
            corner_radius=12
        )
        bubble_frame.pack(fill="x", padx=8, pady=6)

        top_row = ctk.CTkFrame(bubble_frame, fg_color="transparent")
        top_row.pack(fill="x", padx=10, pady=(6, 2))

        header = ctk.CTkLabel(
            top_row,
            text="🤖 " + ("المساعد البرمجي" if self.is_rtl else "AI Agent"),
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color="#10b981",
            anchor=self.text_anchor
        )
        header.pack(side=self.side_start)

        if model_info:
            badge = ctk.CTkLabel(
                top_row,
                text=model_info,
                font=ctk.CTkFont(family="Segoe UI", size=10),
                text_color="gray60"
            )
            badge.pack(side=self.side_end)

        msg_lbl = ctk.CTkLabel(
            bubble_frame,
            text=message,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            wraplength=400,
            justify="right" if self.is_rtl else "left",
            anchor=self.text_anchor
        )
        msg_lbl.pack(fill="x", padx=10, pady=(2, 6))

        # If files were modified or generated, display interactive chips & Claude artifact cards
        if files:
            self._render_bubble_files_and_artifacts(bubble_frame, files)

        self._scroll_chat_to_bottom()

    def _scroll_chat_to_bottom(self):
        self.root.after(50, lambda: self.chat_scroll._parent_canvas.yview_moveto(1.0))

    # -------------------------------------------------------------------------
    # Panel 2: Workspace, File Explorer, Code Editor, and Outputs
    # -------------------------------------------------------------------------

    def _create_workspace_panel(self, parent, side: str):
        self.workspace_frame = ctk.CTkFrame(parent, corner_radius=12)
        self.workspace_frame.pack(side=side, fill="both", expand=True, padx=5, pady=0)

        # 2. Project File Explorer Toolbar (File Chips)
        files_bar = ctk.CTkFrame(self.workspace_frame, fg_color="transparent")
        files_bar.pack(fill="x", padx=10, pady=(2, 4))

        self.files_bar_scroll = ctk.CTkScrollableFrame(files_bar, height=36, orientation="horizontal", fg_color="transparent")
        self.files_bar_scroll.pack(side=self.side_start, fill="x", expand=True)

        self._render_file_tabs()

        # 3. Code Editor Tabs & Output
        self.tabview = ctk.CTkTabview(self.workspace_frame)
        self.tabview.pack(fill="both", expand=True, padx=10, pady=(0, 6))

        self.tab_code = self.tabview.add(self.tr("tab_code"))
        self.tab_artifacts = self.tabview.add(self.tr("tab_artifacts"))
        self.tab_diff = self.tabview.add(self.tr("tab_diff"))
        self.tab_explanation = self.tabview.add(self.tr("tab_explanation"))
        self.tab_console = self.tabview.add(self.tr("tab_console"))

        # --- Tab 1: Code Editor with Line Numbers Gutter ---
        editor_container = ctk.CTkFrame(self.tab_code, fg_color="transparent")
        editor_container.pack(fill="both", expand=True, pady=2)

        # Line numbers gutter (always on left for LTR monospace code)
        self.line_gutter = tk.Text(
            editor_container,
            width=4,
            padx=6,
            pady=4,
            takefocus=0,
            border=0,
            highlightthickness=0,
            background="#1a1c23" if self.theme_switch.get() == 1 else "#f1f5f9",
            foreground="#64748b",
            state="disabled",
            wrap="none",
            font=("Consolas", 12)
        )
        self.line_gutter.pack(side="left", fill="y", padx=(0, 2))

        self.code_box = ctk.CTkTextbox(
            editor_container,
            wrap="none",
            font=ctk.CTkFont(family="Consolas", size=12)
        )
        self.code_box.pack(side="left", fill="both", expand=True)
        self.code_box.bind("<KeyRelease>", self._on_code_edited)

        # Connect line numbers gutter scroll synchronization
        self._setup_line_gutter_sync()
        self.highlighter = CodeHighlighter(self.code_box._textbox, mode="dark")

        # --- Tab: Claude Live Artifacts (Interactive Web Preview) ---
        art_tools = ctk.CTkFrame(self.tab_artifacts, fg_color="transparent")
        art_tools.pack(fill="x", pady=(0, 4))

        self.art_file_selector = ctk.CTkComboBox(
            art_tools,
            values=["(No HTML/SVG artifacts)"],
            width=190,
            state="readonly",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            command=self._on_artifact_combo_selected
        )
        self.art_file_selector.pack(side=self.side_start, padx=(0, 6) if not self.is_rtl else (6, 0))

        self.art_refresh_btn = ctk.CTkButton(
            art_tools,
            text=self.tr("artifact_refresh_btn"),
            width=105,
            height=26,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            fg_color="gray30",
            hover_color="gray40",
            command=self.refresh_active_artifact
        )
        self.art_refresh_btn.pack(side=self.side_start, padx=(0, 6) if not self.is_rtl else (6, 0))

        self.art_browser_btn = ctk.CTkButton(
            art_tools,
            text=self.tr("artifact_browser_btn"),
            width=115,
            height=26,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            fg_color="#059669",
            hover_color="#047857",
            command=self.open_current_artifact_in_browser
        )
        self.art_browser_btn.pack(side=self.side_start, padx=(0, 10) if not self.is_rtl else (10, 0))

        # Viewport toggles (Desktop vs Mobile)
        viewport_tools = ctk.CTkFrame(self.tab_artifacts, fg_color="transparent")
        viewport_tools.pack(fill="x", pady=(0, 8))
        self.art_desktop_btn = ctk.CTkButton(
            viewport_tools,
            text=self.tr("artifact_desktop_btn"),
            width=90,
            height=26,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            fg_color="#2563eb",
            command=lambda: self.set_artifact_viewport("desktop")
        )
        self.art_desktop_btn.pack(side=self.side_end, padx=(3, 0) if self.is_rtl else (0, 3))

        self.art_mobile_btn = ctk.CTkButton(
            viewport_tools,
            text=self.tr("artifact_mobile_btn"),
            width=105,
            height=26,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            fg_color="gray30",
            command=lambda: self.set_artifact_viewport("mobile")
        )
        self.art_mobile_btn.pack(side=self.side_end, padx=(4, 3) if self.is_rtl else (3, 4))

        # Viewport container (Desktop full expansion or Mobile phone container)
        self.art_viewport_container = ctk.CTkFrame(self.tab_artifacts, fg_color="transparent")
        self.art_viewport_container.pack(fill="both", expand=True)

        self._build_artifact_preview_canvas()

        # --- Tab 2: Diff View (Before & After Comparison) ---
        diff_tools = ctk.CTkFrame(self.tab_diff, fg_color="transparent")
        diff_tools.pack(fill="x", pady=(0, 4))

        self.diff_info_lbl = ctk.CTkLabel(
            diff_tools,
            text="",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            anchor=self.text_anchor
        )
        self.diff_info_lbl.pack(side=self.side_start, fill="x", expand=True)

        self.diff_refresh_btn = ctk.CTkButton(
            diff_tools,
            text="🔄 " + ("تحديث المقارنة" if self.is_rtl else "Refresh Diff"),
            width=110,
            height=24,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            fg_color="gray30",
            hover_color="gray40",
            command=self._render_diff_view
        )
        self.diff_refresh_btn.pack(side=self.side_end)

        self.diff_box = ctk.CTkTextbox(
            self.tab_diff,
            wrap="none",
            font=ctk.CTkFont(family="Consolas", size=12)
        )
        self.diff_box.pack(fill="both", expand=True)
        self._setup_diff_box_tags()

        # --- Tab 3: Explanation ---
        self.explanation_box = ctk.CTkTextbox(
            self.tab_explanation,
            wrap="word",
            font=ctk.CTkFont(family="Segoe UI", size=13)
        )
        self.explanation_box.pack(fill="both", expand=True, pady=4)
        self.explanation_box.insert("1.0", "سيظهر هنا الشرح المعماري وخطة المشروع.\n")
        self._apply_textbox_alignment(self.explanation_box)

        # --- Tab 4: Console ---
        c_tools = ctk.CTkFrame(self.tab_console, fg_color="transparent")
        c_tools.pack(fill="x", pady=(0, 4))

        self.clear_console_btn = ctk.CTkButton(
            c_tools,
            text=self.tr("clear_console_btn"),
            width=110,
            height=24,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            fg_color="gray30",
            hover_color="gray40",
            command=self._clear_console
        )
        self.clear_console_btn.pack(side=self.side_start)

        # Auto-Fix Button (Self-Healing)
        self.auto_fix_btn = ctk.CTkButton(
            c_tools,
            text=self.tr("auto_fix_btn"),
            height=24,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            fg_color="#7c3aed",
            hover_color="#6d28d9",
            command=self.trigger_auto_fix
        )

        # Missing Package Auto-Installer Button
        self.install_pkg_btn = ctk.CTkButton(
            c_tools,
            text=self.tr("install_pkg_btn"),
            height=24,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            fg_color="#d97706",
            hover_color="#b45309",
            command=self._install_missing_package
        )

        self.embedded_claude_cli_btn = ctk.CTkButton(
            c_tools,
            text=self.tr("console_run_claude_btn"),
            height=24,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            fg_color="#ea580c",
            hover_color="#c2410c",
            command=lambda: self.launch_claude_code_terminal(embedded=True)
        )
        self.embedded_claude_cli_btn.pack(side=self.side_end, padx=4)

        self.console_box = ctk.CTkTextbox(
            self.tab_console,
            wrap="none",
            font=ctk.CTkFont(family="Consolas", size=12),
            text_color="#00FF66",
            fg_color="#121212"
        )
        self.console_box.pack(fill="both", expand=True)
        self.console_box.insert("1.0", self.tr("console_placeholder"))

        # Interactive Embedded Console Input Bar (In-App Terminal)
        self.console_input_bar = ctk.CTkFrame(self.tab_console, fg_color="transparent")
        self.console_input_bar.pack(fill="x", pady=(4, 0))

        self.console_input_entry = ctk.CTkEntry(
            self.console_input_bar,
            placeholder_text=self.tr("console_input_placeholder"),
            font=ctk.CTkFont(family="Segoe UI", size=11)
        )
        self.console_input_entry.pack(side=self.side_start, fill="x", expand=True, padx=(0, 4) if not self.is_rtl else (4, 0))
        self.console_input_entry.bind("<Return>", lambda e: self._send_console_input())

        self.console_send_btn = ctk.CTkButton(
            self.console_input_bar,
            text=self.tr("console_send_btn"),
            width=75,
            height=28,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            command=self._send_console_input
        )
        self.console_send_btn.pack(side=self.side_start, padx=(0, 4) if not self.is_rtl else (4, 0))

        self.console_stop_btn = ctk.CTkButton(
            self.console_input_bar,
            text=self.tr("console_stop_btn"),
            width=70,
            height=28,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            fg_color="#b91c1c",
            hover_color="#991b1b",
            command=self.kill_console_process
        )
        self.console_stop_btn.pack(side=self.side_start, padx=2)

        # 4. Bottom Approval Bar
        bottom_card = ctk.CTkFrame(self.workspace_frame, corner_radius=10)
        bottom_card.pack(side="bottom", fill="x", before=self.tabview, padx=10, pady=(0, 10))

        b_inner = ctk.CTkFrame(bottom_card, fg_color="transparent")
        b_inner.pack(fill="x", padx=10, pady=8)

        self.save_all_btn = ctk.CTkButton(
            b_inner,
            text=self.tr("save_all_btn"),
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            height=34,
            fg_color="#059669",
            hover_color="#047857",
            command=self.save_all_project_files
        )
        self.save_all_btn.pack(side=self.side_start, padx=(0, 8) if not self.is_rtl else (8, 0))

        self.run_btn = ctk.CTkButton(
            b_inner,
            text=self.tr("run_code_btn"),
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            height=34,
            fg_color="#2563eb",
            hover_color="#1d4ed8",
            command=self.run_active_code
        )
        self.run_btn.pack(side=self.side_start, padx=(0, 8) if not self.is_rtl else (8, 0))

        self.status_lbl = ctk.CTkLabel(
            bottom_card,
            textvariable=self.status_message,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=("gray40", "gray65"),
            anchor=self.text_anchor, wraplength=500
        )
        self.status_lbl.pack(fill="x", padx=12, pady=(0, 8))

    def _render_file_tabs(self):
        """Render file tabs horizontally in the workspace header."""
        for w in self.files_bar_scroll.winfo_children():
            w.destroy()

        for idx, f in enumerate(self.project_files):
            fp = f.get("filepath", "file.txt")
            icon = get_file_icon(fp)
            is_active = (idx == self.active_file_idx)

            fg = ("#2563eb", "#2563eb") if is_active else ("gray85", "#272a34")
            text_col = "white" if is_active else ("gray20", "gray85")

            btn = ctk.CTkButton(
                self.files_bar_scroll,
                text=f"{icon} {fp}",
                font=ctk.CTkFont(family="Consolas" if not self.is_rtl else "Segoe UI", size=11, weight="bold" if is_active else "normal"),
                height=28,
                corner_radius=6,
                fg_color=fg,
                text_color=text_col,
                command=lambda i=idx: self._select_file_index(i)
            )
            btn.pack(side=self.side_start, padx=3)

    def _select_file_index(self, idx: int):
        if 0 <= idx < len(self.project_files):
            if 0 <= self.active_file_idx < len(self.project_files):
                self.project_files[self.active_file_idx]["code"] = self.code_box.get("1.0", "end-1c")

            self.active_file_idx = idx
            f = self.project_files[idx]
            fp = f.get("filepath", "file.txt")
            self.active_filepath.set(fp)

            self.code_box.delete("1.0", tk.END)
            self.code_box.insert("1.0", f.get("code", ""))
            self._apply_syntax_highlighting()
            self._render_file_tabs()
            self._current_line_count = 0
            self._sync_line_gutter()
            self._render_diff_view()

    def _on_code_edited(self, event=None):
        if 0 <= self.active_file_idx < len(self.project_files):
            self.project_files[self.active_file_idx]["code"] = self.code_box.get("1.0", "end-1c")
        self._sync_line_gutter()

    # -------------------------------------------------------------------------
    # Core Logic: Chat & Multi-Turn Generation
    # -------------------------------------------------------------------------

    def send_chat_message(self):
        if self.is_generating:
            return

        model = self.current_model.get().strip()
        if not model or model in ["Searching...", "No models", "Offline", "No models found"]:
            messagebox.showwarning(self.tr("no_model_title"), self.tr("no_model_msg"))
            return

        user_text = self.chat_textbox.get("1.0", tk.END).strip()
        if not user_text:
            messagebox.showwarning(self.tr("empty_prompt_title"), self.tr("empty_prompt_msg"))
            return

        # Clear input box
        self.chat_textbox.delete("1.0", tk.END)

        # Add user message bubble
        self._add_user_bubble(user_text)

        # Prepare UI state
        self.is_generating = True
        self.cancel_requested = False
        self.send_btn.configure(state="disabled")
        self.cancel_btn.configure(state="normal")
        self.progress_bar.start()

        if self.lang == "ar":
            self.status_message.set(f"المساعد يفكر ويقوم ببناء الكود عبر {model}...")
        else:
            self.status_message.set(f"Agent thinking & coding with {model}...")

        # Run multi-turn chat in background thread
        thread = threading.Thread(
            target=self._chat_worker,
            args=(user_text, model, self.web_search_mode),
            daemon=True
        )
        thread.start()

    def cancel_generation(self):
        if self.is_generating:
            self.cancel_requested = True
            self.status_message.set("جاري إلغاء الطلب..." if self.lang == "ar" else "Cancelling request...")
            self.cancel_btn.configure(state="disabled")

    def _chat_worker(self, user_text: str, model: str, web_search_mode: str = "auto"):
        start_time = time.time()
        try:
            # Snapshot existing file versions before this turn for diff comparison
            for f in self.project_files:
                if f.get("filepath") and f.get("code"):
                    self.previous_file_versions[f["filepath"]] = f.get("code")

            # Start real-time streaming bubble
            self.root.after(0, lambda m=model: self._start_streaming_bubble(m))

            def _chunk_callback(piece: str, full_so_far: str):
                if not self.cancel_requested:
                    extracted = extract_streaming_chat_reply(full_so_far)
                    byte_len = len(full_so_far)
                    self.root.after(0, lambda ext=extracted, bl=byte_len: self._update_streaming_bubble(ext, bl))

            def _status_callback(status):
                if self.cancel_requested:
                    return
                if status == "searching":
                    text = "جاري البحث على الإنترنت..." if self.lang == "ar" else "Searching the web..."
                else:
                    text = f"جاري إعداد الرد عبر {model}..." if self.lang == "ar" else f"Generating with {model}..."
                self.root.after(0, lambda msg=text: self.status_message.set(msg))

            result = self.agent.chat_turn(
                user_message=user_text,
                model=model,
                current_project_files=self.project_files,
                on_chunk=_chunk_callback,
                web_search_mode=web_search_mode,
                on_status=_status_callback
            )
            elapsed = round(time.time() - start_time, 2)
            if not self.cancel_requested:
                self.root.after(0, lambda res=result, el=elapsed: self._on_chat_success(res, el))
            else:
                self.root.after(0, self._on_chat_cancelled)
        except Exception as e:
            err_text = str(e)
            elapsed = round(time.time() - start_time, 2)
            if not self.cancel_requested:
                self.root.after(0, lambda err=err_text, el=elapsed: self._on_chat_error(err, el))
            else:
                self.root.after(0, self._on_chat_cancelled)

    def _on_chat_success(self, result: dict, elapsed: float):
        self._reset_generation_state()

        chat_reply = result.get("chat_reply", "تم تنفيذ التعديل بنجاح.")
        new_files = result.get("files", [])
        explanation = result.get("explanation", "")
        proj_name = result.get("project_name", "My Project")
        model_name = result.get("model", self.current_model.get())

        # Merge or update project files
        if new_files:
            # Snapshot before update if not already snapshotted
            for nf in new_files:
                fp = nf.get("filepath")
                for existing_f in self.project_files:
                    if existing_f.get("filepath") == fp and fp not in self.previous_file_versions:
                        self.previous_file_versions[fp] = existing_f.get("code", "")

            existing_map = {f["filepath"]: f for f in self.project_files}
            for nf in new_files:
                existing_map[nf["filepath"]] = nf
            self.project_files = list(existing_map.values())
            self._render_file_tabs()

            # Load active file into editor
            if self.project_files:
                self._select_file_index(0)

        # Update diff view
        self._render_diff_view()

        # Update or add AI bubble to chat stream
        model_tag = f"{model_name} ({elapsed}s)"
        if self.streaming_bubble:
            self._finalize_streaming_bubble(
                message=chat_reply,
                files=new_files,
                model_info=model_tag
            )
        else:
            self._add_agent_bubble(
                message=chat_reply,
                files=new_files,
                model_info=model_tag
            )

        # Update explanation tab
        if result.get("sources"):
            self._render_search_sources(result["sources"])

        self.explanation_box.delete("1.0", tk.END)
        doc = f"## 🚀 {proj_name}\n"
        doc += f"**{model_name}** | {elapsed}s\n"
        doc += "=" * 50 + "\n\n"
        doc += f"### 💡 الشرح والتوثيق:\n{explanation}\n\n"
        doc += "### 📋 ملفات المشروع الحالية:\n"
        for f in self.project_files:
            doc += f"- `{f.get('filepath')}`: {f.get('description', '')}\n"
        self.explanation_box.insert("1.0", doc)
        self._apply_textbox_alignment(self.explanation_box)

        # Update status
        if self.lang == "ar":
            self.status_message.set(f"اكتمل الرد في {elapsed} ثانية! تم تحديث {len(new_files)} ملفات.")
        else:
            self.status_message.set(f"Completed in {elapsed}s! {len(new_files)} files updated.")

    def _render_search_sources(self, sources):
        from web_search import safe_source_url
        card = ctk.CTkFrame(self.chat_scroll, corner_radius=8)
        card.pack(fill="x", padx=8, pady=4)
        ctk.CTkLabel(card, text="فتح مصادر البحث" if self.is_rtl else "Open search sources",
                     anchor=self.text_anchor).pack(fill="x", padx=10, pady=4)
        for index, source in enumerate(sources, 1):
            url = safe_source_url(source.get("url"))
            if not url:
                continue
            title = source.get("title", url)
            button = ctk.CTkButton(
                card, text=f"[{index}] {title[:48]}", height=26,
                anchor="w", command=lambda target=url: webbrowser.open(target)
            )
            button.pack(fill="x", padx=10, pady=(0, 5))

    def _on_chat_error(self, err_msg: str, elapsed: float):
        self._reset_generation_state()
        if self.streaming_bubble:
            try:
                self.streaming_bubble["frame"].destroy()
            except Exception:
                pass
            self.streaming_bubble = None

        self._add_agent_bubble(
            message=f"❌ حدث خطأ أثناء التوليد ({elapsed} ثانية):\n{err_msg}",
            files=None,
            model_info="Error"
        )
        self.status_message.set(f"خطأ ({elapsed}s): {err_msg}")

    def _on_chat_cancelled(self):
        self._reset_generation_state()
        if self.streaming_bubble:
            try:
                self.streaming_bubble["frame"].destroy()
            except Exception:
                pass
            self.streaming_bubble = None

        self._add_agent_bubble(
            message="تم إلغاء الطلب بناءً على رغبتك.",
            files=None,
            model_info="Cancelled"
        )
        self.status_message.set("تم إلغاء الطلب." if self.lang == "ar" else "Cancelled.")

    def _reset_generation_state(self):
        self.is_generating = False
        self.cancel_requested = False
        self.progress_bar.stop()
        self.progress_bar.set(0)
        self.send_btn.configure(state="normal")
        self.cancel_btn.configure(state="disabled")

    def start_new_chat(self):
        """Reset conversation memory and clear chat bubbles."""
        self.agent.reset_chat()
        for w in self.chat_scroll.winfo_children():
            w.destroy()
        self._add_agent_bubble(
            message=self.tr("welcome_msg"),
            files=None,
            model_info=None
        )
        self.status_message.set("تم بدء محادثة جديدة وتصفير الذاكرة." if self.lang == "ar" else "Started new chat session.")

    # -------------------------------------------------------------------------
    # File I/O: Save All, Save Active, Browser, Run
    # -------------------------------------------------------------------------

    def save_all_project_files(self):
        project_dir = self.project_dir.get().strip()
        if not project_dir:
            messagebox.showwarning("تنبيه" if self.lang == "ar" else "Warning", "يرجى تحديد مسار المشروع.")
            return

        if 0 <= self.active_file_idx < len(self.project_files):
            self.project_files[self.active_file_idx]["code"] = self.code_box.get("1.0", "end-1c")

        try:
            res = write_project_bundle(project_dir, self.project_files)
            count = res["files_written"]
            bytes_tot = res["total_bytes"]
            if self.lang == "ar":
                self.status_message.set(f"✓ تم حفظ كامل المشروع بنجاح ({count} ملفات، {bytes_tot} بايت)!")
            else:
                self.status_message.set(f"✓ All {count} project files saved successfully ({bytes_tot} bytes)!")

            messagebox.showinfo(
                self.tr("save_all_success_title"),
                self.tr("save_all_success_msg", count=count, dir=project_dir)
            )
        except Exception as e:
            messagebox.showerror("خطأ" if self.lang == "ar" else "Error", str(e))

    def open_in_browser(self):
        project_dir = self.project_dir.get().strip()
        if not project_dir:
            messagebox.showwarning("تنبيه" if self.lang == "ar" else "Warning", "يرجى تحديد مسار المشروع.")
            return

        index_path = Path(project_dir) / "index.html"
        if not index_path.exists():
            ans = messagebox.askyesno(
                "حفظ أولاً" if self.lang == "ar" else "Save First",
                "لم يتم حفظ ملفات المشروع بعد. هل ترغب في حفظ كافة الملفات الآن وفتح الموقع؟"
            )
            if ans:
                self.save_all_project_files()
            else:
                return

        res = open_file_in_browser(project_dir, "index.html")
        if res.get("success"):
            self.status_message.set("تم فتح الموقع في المتصفح بنجاح! 🌐")
        else:
            messagebox.showwarning("تنبيه", res.get("error", "لم يتم العثور على ملف HTML."))

    def run_active_code(self):
        project_dir = self.project_dir.get().strip()
        filepath = self.active_filepath.get().strip()

        if not project_dir or not filepath:
            messagebox.showwarning("تنبيه", "يرجى تحديد مسار المشروع والملف.")
            return

        if filepath.lower().endswith((".html", ".htm")):
            self.open_in_browser()
            return

        target_full = Path(project_dir) / filepath
        if not target_full.exists():
            ans = messagebox.askyesno("حفظ أولاً", f"الملف '{filepath}' لم يُحفظ بعد. حفظ وتشغيل؟")
            if ans:
                self.save_all_project_files()
            else:
                return

        self.tabview.set(self.tr("tab_console"))
        self.status_message.set(f"جاري تشغيل {filepath}...")
        self.run_btn.configure(state="disabled")

        def _run_worker():
            res = execute_script(project_dir, filepath)
            self.root.after(0, lambda r=res, fp=filepath: self._on_execution_completed(r, fp))

        threading.Thread(target=_run_worker, daemon=True).start()

    def _on_execution_completed(self, res: dict, filepath: str):
        self.run_btn.configure(state="normal")
        self.console_box.delete("1.0", tk.END)

        header = f"=== Executing / تشغيل: {filepath} ===\n"
        header += f"Duration / المدة: {res.get('duration', 0)}s | Exit Code: {res.get('returncode', -1)}\n"
        header += "=" * 50 + "\n\n"
        self.console_box.insert(tk.END, header)

        stdout = res.get("stdout", "")
        stderr = res.get("stderr", "")

        if stdout:
            self.console_box.insert(tk.END, "[STDOUT / المخرجات القياسية]\n" + stdout + "\n")
        if stderr:
            self.console_box.insert(tk.END, "[STDERR / الأخطاء والتحذيرات]\n" + stderr + "\n")

        # Record error details for Self-Healing / Auto-Fix
        self.last_failed_file = filepath
        self.last_stderr = (stderr or stdout).strip()

        # Handle failure: show Auto-Fix and detect missing packages
        has_error = (not res.get("success")) or (res.get("returncode", 0) != 0) or (bool(stderr.strip()))
        if has_error:
            self.auto_fix_btn.pack(side=self.side_start, padx=6)
            missing = detect_missing_package(self.last_stderr)
            if missing:
                self.detected_pkg = missing
                pkg_name = missing["package"]
                mgr = missing["manager"]
                self.install_pkg_btn.configure(
                    state="normal",
                    text=f"📦 تثبيت {pkg_name} تلقائياً ({mgr} install {pkg_name})" if self.is_rtl else f"📦 Auto-Install {pkg_name} ({mgr} install {pkg_name})"
                )
                self.install_pkg_btn.pack(side=self.side_start, padx=6)
            else:
                self.install_pkg_btn.pack_forget()
        else:
            self.auto_fix_btn.pack_forget()
            self.install_pkg_btn.pack_forget()

        if res.get("timed_out"):
            self.status_message.set(f"انتهت مهلة تشغيل {filepath}.")
        elif res.get("success"):
            self.status_message.set(f"اكتمل التشغيل بنجاح في {res.get('duration')} ثانية.")
        else:
            self.status_message.set(f"انتهى التشغيل برمز الخروج {res.get('returncode')}.")

    # -------------------------------------------------------------------------
    # Enhancement 1: Line Numbers Gutter
    # -------------------------------------------------------------------------

    def _setup_line_gutter_sync(self):
        """Synchronize line numbers gutter with code editor scrolling."""
        orig_yview = self.code_box._textbox.yview

        def _custom_yview(*args):
            res = orig_yview(*args)
            self._sync_line_gutter()
            return res

        self.code_box._textbox.yview = _custom_yview

        self.line_gutter.bind(
            "<MouseWheel>",
            lambda e: self.code_box._textbox.yview_scroll(int(-1 * (e.delta / 120)), "units")
        )
        self.code_box._textbox.bind("<MouseWheel>", lambda e: self.root.after(10, self._sync_line_gutter))
        self.code_box._textbox.bind("<Configure>", lambda e: self.root.after(10, self._sync_line_gutter))

    def _sync_line_gutter(self):
        try:
            end_index = self.code_box._textbox.index("end-1c")
            line_count = int(end_index.split(".")[0]) if end_index else 1
            line_count = max(1, line_count)

            if line_count != self._current_line_count:
                digits = max(3, len(str(line_count)))
                self.line_gutter.configure(width=digits + 1, state="normal")
                self.line_gutter.delete("1.0", tk.END)
                self.line_gutter.insert("1.0", "\n".join(str(i) for i in range(1, line_count + 1)))
                self.line_gutter.configure(state="disabled")
                self._current_line_count = line_count

            fraction = self.code_box._textbox.yview()[0]
            self.line_gutter.yview_moveto(fraction)
        except Exception:
            pass

    # -------------------------------------------------------------------------
    # Enhancement 2: Diff Viewer
    # -------------------------------------------------------------------------

    def _setup_diff_box_tags(self):
        try:
            self.diff_box._textbox.tag_configure("diff_add", foreground="#10b981", background="#064e3b")
            self.diff_box._textbox.tag_configure("diff_sub", foreground="#f87171", background="#450a0a")
            self.diff_box._textbox.tag_configure("diff_hunk", foreground="#38bdf8", font=("Consolas", 12, "bold"))
            self.diff_box._textbox.tag_configure("diff_header", foreground="#94a3b8", font=("Consolas", 12, "bold"))
        except Exception:
            pass

    def toggle_diff_view(self):
        self.tabview.set(self.tr("tab_diff"))
        self._render_diff_view()

    def _render_diff_view(self):
        self.diff_box.delete("1.0", tk.END)
        if not self.project_files or self.active_file_idx >= len(self.project_files):
            self.diff_box.insert("1.0", self.tr("no_diff_msg"))
            self.diff_info_lbl.configure(text="")
            return

        active_f = self.project_files[self.active_file_idx]
        fp = active_f.get("filepath", "file.txt")
        current_code = self.code_box.get("1.0", "end-1c")
        orig_code = self.previous_file_versions.get(fp)

        if orig_code is None:
            self.diff_info_lbl.configure(text=f"📁 {fp} : " + ("ملف جديد تم إنشاؤه لأول مرة" if self.is_rtl else "Brand new file"))
            self.diff_box.insert("1.0", f"// {fp}\n// " + self.tr("no_diff_msg") + "\n\n" + current_code)
            return

        orig_lines = orig_code.splitlines(keepends=True)
        new_lines = current_code.splitlines(keepends=True)
        diff = list(difflib.unified_diff(orig_lines, new_lines, fromfile=f"a/{fp}", tofile=f"b/{fp}"))

        if not diff:
            self.diff_info_lbl.configure(text=f"📁 {fp} : " + ("لم يطرأ أي تغيير على هذا الملف" if self.is_rtl else "No changes in this file"))
            self.diff_box.insert("1.0", self.tr("no_diff_msg"))
            return

        add_count = sum(1 for line in diff if line.startswith("+") and not line.startswith("+++"))
        sub_count = sum(1 for line in diff if line.startswith("-") and not line.startswith("---"))
        self.diff_info_lbl.configure(
            text=f"📁 {fp} | +{add_count} " + ("إضافة" if self.is_rtl else "additions") + f" | -{sub_count} " + ("حذف" if self.is_rtl else "deletions")
        )

        for line in diff:
            start_idx = self.diff_box._textbox.index("insert")
            self.diff_box.insert(tk.END, line)
            end_idx = self.diff_box._textbox.index("insert")
            if line.startswith("+++") or line.startswith("---"):
                self.diff_box._textbox.tag_add("diff_header", start_idx, end_idx)
            elif line.startswith("+"):
                self.diff_box._textbox.tag_add("diff_add", start_idx, end_idx)
            elif line.startswith("-"):
                self.diff_box._textbox.tag_add("diff_sub", start_idx, end_idx)
            elif line.startswith("@@"):
                self.diff_box._textbox.tag_add("diff_hunk", start_idx, end_idx)

    # -------------------------------------------------------------------------
    # Enhancement 3: Auto-Fix & Self-Healing & Package Installer
    # -------------------------------------------------------------------------

    def trigger_auto_fix(self):
        if not self.last_failed_file or not self.last_stderr:
            return
        fp = self.last_failed_file
        err = self.last_stderr

        self.status_message.set(self.tr("auto_fix_sent"))
        prompt = (
            f"واجهت هذا الخطأ أثناء تشغيل الملف '{fp}':\n"
            f"```\n{err}\n```\n"
            f"يرجى تشخيص سبب المشكلة بدقة، وتصحيح الكود بالكامل، وتحديث الملف وإعادة شرح الحل باللغة العربية."
        )
        self._set_chat_input(prompt)
        self.send_chat_message()

    def _install_missing_package(self):
        if not self.detected_pkg:
            return
        pkg = self.detected_pkg["package"]
        mgr = self.detected_pkg["manager"]
        project_dir = self.project_dir.get().strip()

        self.install_pkg_btn.configure(
            state="disabled",
            text=f"جاري تثبيت {pkg}... ⏳" if self.is_rtl else f"Installing {pkg}... ⏳"
        )
        self.status_message.set(f"جاري تثبيت {pkg} عبر {mgr}...")

        def _installer_thread():
            res = install_package(pkg, manager=mgr, cwd=project_dir)
            self.root.after(0, lambda r=res, p=pkg: self._on_package_installed(r, p))

        threading.Thread(target=_installer_thread, daemon=True).start()

    def _on_package_installed(self, res: dict, pkg: str):
        self.install_pkg_btn.pack_forget()
        self.console_box.insert(tk.END, f"\n=== Package Installation / تثبيت الحزمة: {pkg} ===\n")
        if res.get("stdout"):
            self.console_box.insert(tk.END, res["stdout"] + "\n")
        if res.get("stderr"):
            self.console_box.insert(tk.END, res["stderr"] + "\n")

        if res.get("success"):
            msg = f"✓ تم تثبيت الحزمة {pkg} بنجاح! يمكنك الآن تشغيل الكود مجدداً."
            self.status_message.set(msg)
            messagebox.showinfo("تم التثبيت بنجاح", msg)
        else:
            msg = f"❌ تعذر تثبيت الحزمة {pkg}."
            self.status_message.set(msg)
            messagebox.showerror("خطأ في التثبيت", f"فشل تثبيت {pkg}:\n{res.get('stderr')}")

    # -------------------------------------------------------------------------
    # Enhancement 4: ZIP Export & Project Directory Scanner
    # -------------------------------------------------------------------------

    def export_project_as_zip(self):
        project_dir = self.project_dir.get().strip()
        if not project_dir:
            messagebox.showwarning("تنبيه", "يرجى تحديد مسار المشروع أولاً.")
            return

        if 0 <= self.active_file_idx < len(self.project_files):
            self.project_files[self.active_file_idx]["code"] = self.code_box.get("1.0", "end-1c")

        try:
            write_project_bundle(project_dir, self.project_files)
        except Exception as e:
            messagebox.showerror("خطأ", f"تعذر حفظ الملفات قبل التصدير: {str(e)}")
            return

        base_name = Path(project_dir).name or "project"
        dest_path = filedialog.asksaveasfilename(
            initialdir=str(Path(project_dir).parent),
            initialfile=f"{base_name}_export.zip",
            defaultextension=".zip",
            filetypes=[("ZIP Archive", "*.zip")],
            title=self.tr("export_zip_btn")
        )
        if not dest_path:
            return

        try:
            res = export_project_zip(project_dir, dest_path)
            self.status_message.set(f"✓ تم تصدير {res['file_count']} ملفات كملف ZIP بنجاح!")
            ans = messagebox.askyesno(
                self.tr("zip_success_title"),
                self.tr("zip_success_msg", path=dest_path) + ("\n\nهل ترغب في فتح المجلد الآن؟" if self.is_rtl else "\n\nWould you like to open the folder now?")
            )
            if ans:
                if sys.platform == "win32":
                    os.startfile(os.path.dirname(dest_path))
        except Exception as e:
            messagebox.showerror("خطأ", f"فشل تصدير ZIP: {str(e)}")

    def scan_and_load_folder(self):
        project_dir = self.project_dir.get().strip()
        if not project_dir or not Path(project_dir).exists():
            messagebox.showwarning("تنبيه", "مسار المشروع غير موجود على القرص.")
            return

        scanned = scan_existing_project(project_dir)
        if not scanned:
            messagebox.showinfo(self.tr("scan_success_title"), self.tr("scan_empty_msg"))
            return

        # Record current file versions
        self.previous_file_versions = {f["filepath"]: f.get("code", "") for f in self.project_files}
        self.project_files = scanned
        self.active_file_idx = 0
        self._render_file_tabs()
        self._select_file_index(0)

        self._add_agent_bubble(
            message=f"📥 تم فحص المجلد '{Path(project_dir).name}' وتحميل {len(scanned)} ملفات بنجاح إلى الاستوديو! أصبحت كافة الملفات البرمجية جاهزة في بيئة العمل ويمكنك طلب تعديلها وتطويرها الآن.",
            files=scanned,
            model_info="Project Scanner"
        )
        self.status_message.set(self.tr("scan_success_msg", count=len(scanned)))

    # -------------------------------------------------------------------------
    # Enhancement 5: Live Streaming Bubbles
    # -------------------------------------------------------------------------

    def _start_streaming_bubble(self, model: str):
        bubble_frame = ctk.CTkFrame(
            self.chat_scroll,
            fg_color=("gray90", "#1c202a"),
            border_width=1,
            border_color=("gray80", "#2d3342"),
            corner_radius=12
        )
        bubble_frame.pack(fill="x", padx=8, pady=6)

        top_row = ctk.CTkFrame(bubble_frame, fg_color="transparent")
        top_row.pack(fill="x", padx=10, pady=(6, 2))

        header = ctk.CTkLabel(
            top_row,
            text="🤖 " + ("المساعد البرمجي" if self.is_rtl else "AI Agent"),
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color="#10b981",
            anchor=self.text_anchor
        )
        header.pack(side=self.side_start)

        badge = ctk.CTkLabel(
            top_row,
            text=f"{model} (جاري التدفق... ⏳)" if self.is_rtl else f"{model} (Streaming... ⏳)",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color="#38bdf8"
        )
        badge.pack(side=self.side_end)

        msg_lbl = ctk.CTkLabel(
            bubble_frame,
            text=self.tr("streaming_typing"),
            font=ctk.CTkFont(family="Segoe UI", size=12),
            wraplength=400,
            justify="right" if self.is_rtl else "left",
            anchor=self.text_anchor
        )
        msg_lbl.pack(fill="x", padx=10, pady=(2, 6))

        self.streaming_bubble = {
            "frame": bubble_frame,
            "badge": badge,
            "msg_lbl": msg_lbl,
            "model": model,
            "top_row": top_row
        }
        self._scroll_chat_to_bottom()

    def _update_streaming_bubble(self, extracted_reply: str, byte_count: int):
        if not self.streaming_bubble:
            return
        if extracted_reply:
            self.streaming_bubble["msg_lbl"].configure(text=extracted_reply)
        else:
            txt = f"جاري توليد الرد والأكواد... ⏳ ({byte_count} حرف)" if self.is_rtl else f"Generating reply and files... ⏳ ({byte_count} chars)"
            self.streaming_bubble["msg_lbl"].configure(text=txt)
        self._scroll_chat_to_bottom()

    def _finalize_streaming_bubble(self, message: str, files: Optional[List[Dict[str, str]]], model_info: str):
        if not self.streaming_bubble:
            return
        bubble_frame = self.streaming_bubble["frame"]
        self.streaming_bubble["badge"].configure(text=model_info, text_color="gray60")
        self.streaming_bubble["msg_lbl"].configure(text=message)

        if files:
            self._render_bubble_files_and_artifacts(bubble_frame, files)

        self.streaming_bubble = None
        self._scroll_chat_to_bottom()

    # -------------------------------------------------------------------------
    # Helpers, RTL, Theme & Models
    # -------------------------------------------------------------------------

    def _apply_textbox_alignment(self, textbox: ctk.CTkTextbox, align: Optional[str] = None):
        try:
            if align is None:
                align = "right" if self.is_rtl else "left"
            textbox._textbox.tag_configure("dir_align", justify=align)
            textbox._textbox.tag_add("dir_align", "1.0", "end")
            try:
                textbox._textbox.edit_modified(False)
            except Exception:
                pass
        except Exception:
            pass

    def _apply_syntax_highlighting(self):
        filename = self.active_filepath.get().strip() or "index.html"
        try:
            self.highlighter.highlight(filename)
        except Exception:
            pass

    def _copy_code_to_clipboard(self):
        code = self.code_box.get("1.0", tk.END).rstrip()
        if code:
            self.root.clipboard_clear()
            self.root.clipboard_append(code)
            self.status_message.set(self.tr("copied_toast"))

    def _clear_console(self):
        self.console_box.delete("1.0", tk.END)

    def _browse_directory(self):
        chosen = filedialog.askdirectory(
            initialdir=self.project_dir.get(),
            title="تحديد مسار المشروع" if self.lang == "ar" else "Select Project Directory"
        )
        if chosen:
            self.project_dir.set(os.path.normpath(chosen))

    def _open_project_folder(self):
        path_str = self.project_dir.get().strip()
        if not path_str:
            return
        p = Path(path_str)
        if not p.exists():
            p.mkdir(parents=True, exist_ok=True)
        try:
            if sys.platform == "win32":
                os.startfile(p)
            elif sys.platform == "darwin":
                import subprocess
                subprocess.Popen(["open", str(p)])
            else:
                import subprocess
                subprocess.Popen(["xdg-open", str(p)])
        except Exception as e:
            messagebox.showerror("خطأ", str(e))

    def _toggle_theme(self):
        if self.theme_switch.get() == 1:
            ctk.set_appearance_mode("Dark")
            self.highlighter.set_mode("dark")
            self.console_box.configure(fg_color="#121212", text_color="#00FF66")
            if hasattr(self, "line_gutter"):
                self.line_gutter.configure(background="#1a1c23", foreground="#64748b")
        else:
            ctk.set_appearance_mode("Light")
            self.highlighter.set_mode("light")
            self.console_box.configure(fg_color="#F5F5F5", text_color="#1B5E20")
            if hasattr(self, "line_gutter"):
                self.line_gutter.configure(background="#f1f5f9", foreground="#94a3b8")
        self._apply_syntax_highlighting()

    def _on_language_change(self, value: str):
        new_lang = "ar" if value == "العربية" else "en"
        if new_lang == self.lang:
            return

        # Save the editor buffer before rebuilding translated controls.
        self._on_code_edited()
        saved_files = self.project_files
        saved_active = self.active_file_idx

        self.lang = new_lang
        self.t = TRANSLATIONS[self.lang]
        self.is_rtl = (self.lang == "ar")
        self.root.title(self.t["app_title"])
        self.api_status_text.set(
            self.tr("api_server_running", port=self.api_port)
            if self.api_server and self.api_server.is_running()
            else self.tr("api_server_stopped"))
        self.claude_status_text.set(self.tr(
            "claude_active_badge" if self.claude_key else "claude_inactive_badge"))

        # Rebuild layout
        for w in self.main_container.winfo_children():
            w.destroy()

        self._build_studio_layout()

        # Restore state
        self.project_files = saved_files
        # The freshly created editor is empty; do not save it over the buffer.
        self.active_file_idx = -1
        self._render_file_tabs()
        self._select_file_index(saved_active)

        if self.models:
            self.model_dropdown.configure(values=self.models)
            count = len(self.models)
            self.connection_status.set(self.tr("connected", count=count))
            self.status_badge.configure(text_color="#00E676")

    def _safe_after(self, ms: int, func):
        try:
            if hasattr(self, "root") and self.root and self.root.winfo_exists():
                self.root.after(ms, func)
        except Exception:
            pass

    def refresh_models(self):
        self._safe_after(0, lambda: self.connection_status.set(self.tr("checking_ollama")))
        self._safe_after(0, lambda: self.status_badge.configure(text_color="#FFA500"))

        try:
            models = self.agent.list_models()
            self.models = models
            if models:
                self._safe_after(0, lambda m=models: self._on_models_loaded(m))
            else:
                self._safe_after(0, self._on_models_empty)
        except Exception as e:
            err_text = str(e)
            self._safe_after(0, lambda err=err_text: self._on_ollama_offline(err))

    def _on_models_loaded(self, models: List[str]):
        self.model_dropdown.configure(values=models)
        if not self.current_model.get() or self.current_model.get() not in models:
            self.current_model.set(models[0])

        count = len(models)
        self.connection_status.set(self.tr("connected", count=count))
        self.status_badge.configure(text_color="#00E676")
        if self.lang == "ar":
            self.status_message.set(f"متصل بـ Ollama. النموذج: {self.current_model.get()}")
        else:
            self.status_message.set(f"Connected to Ollama: {self.current_model.get()}")

    def _on_models_empty(self):
        self.model_dropdown.configure(values=["No models"])
        self.current_model.set("No models")
        self.connection_status.set(self.tr("connected", count=0))
        self.status_badge.configure(text_color="#FFA500")
        self.status_message.set(self.tr("no_models_found"))

    def _on_ollama_offline(self, err: str):
        self.model_dropdown.configure(values=["Offline"])
        self.current_model.set("Offline")
        self.connection_status.set(self.tr("offline"))
        self.status_badge.configure(text_color="#FF3D00")
        self.status_message.set(self.tr("ollama_offline_msg"))

    # -------------------------------------------------------------------------
    # Enhancement 6: Local API Server for VS Code Integration
    # -------------------------------------------------------------------------

    def toggle_api_server(self):
        if self.api_server and self.api_server.is_running():
            self.api_server.stop()
            self.api_server = None
            self.api_status_text.set(self.tr("api_server_stopped"))
            self.api_badge.configure(text_color="#94a3b8")
            self.api_toggle_btn.configure(fg_color="#3b82f6", text=self.tr("api_server_btn"))
            self.status_message.set(self.tr("api_stopped_msg"))
        else:
            try:
                self.api_server = LocalAPIServer(port=self.api_port, agent=self.agent)
                self.api_server.start()
                self.api_status_text.set(self.tr("api_server_running", port=self.api_port))
                self.api_badge.configure(text_color="#00E676")
                self.api_toggle_btn.configure(fg_color="#059669", text="✓ " + self.tr("api_server_btn"))
                self.status_message.set(self.tr("api_started_msg", port=self.api_port))
            except Exception as e:
                messagebox.showerror(
                    "خطأ" if self.is_rtl else "Error",
                    f"تعذر تشغيل الخادم على المنفذ {self.api_port}:\n{str(e)}" if self.is_rtl else f"Failed to start server on port {self.api_port}:\n{str(e)}"
                )

    def copy_api_url(self):
        url = f"http://127.0.0.1:{self.api_port}/v1"
        self.root.clipboard_clear()
        self.root.clipboard_append(url)
        self.status_message.set(self.tr("api_copied_toast", url=url))

    def show_vscode_guide(self):
        guide = ctk.CTkToplevel(self.root)
        guide.title(self.tr("api_guide_title"))
        guide.geometry("640x560")
        guide.attributes("-topmost", True)
        guide.grab_set()

        container = ctk.CTkFrame(guide, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=16, pady=16)

        title_lbl = ctk.CTkLabel(
            container,
            text="⚡ " + self.tr("api_guide_title"),
            font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
            anchor=self.text_anchor
        )
        title_lbl.pack(fill="x", pady=(0, 8))

        active_model = self.current_model.get() or "qwen2.5-coder:14b"
        api_url = f"http://127.0.0.1:{self.api_port}/v1"

        continue_cfg = json.dumps({
            "models": [
                {
                    "title": f"Local Studio ({active_model})",
                    "provider": "openai",
                    "model": active_model,
                    "apiBase": api_url,
                    "apiKey": "local-key"
                }
            ]
        }, indent=2)

        cline_info = (
            "1. افتح إضافة Cline أو Roo Code في VS Code.\n"
            "2. اختر API Provider: 'OpenAI-Compatible'.\n"
            f"3. ضع Base URL: {api_url}\n"
            "4. ضع API Key: أي نص عشوائي (مثل: local-key).\n"
            f"5. ضع Model ID: {active_model}\n"
        ) if self.is_rtl else (
            "1. Open Cline or Roo Code extension settings in VS Code.\n"
            "2. Select API Provider: 'OpenAI-Compatible'.\n"
            f"3. Set Base URL: {api_url}\n"
            "4. Set API Key: any string (e.g. local-key).\n"
            f"5. Set Model ID: {active_model}\n"
        )

        # Tabview for guides
        tabs = ctk.CTkTabview(container)
        tabs.pack(fill="both", expand=True, pady=(0, 12))

        tab_cont = tabs.add("Continue.dev")
        tab_cline = tabs.add("Cline / Roo Code")

        # Continue Tab
        c_box = ctk.CTkTextbox(tab_cont, font=ctk.CTkFont(family="Consolas", size=11), wrap="none")
        c_box.pack(fill="both", expand=True, pady=(4, 8))
        c_box.insert("1.0", continue_cfg)

        def _copy_continue():
            self.root.clipboard_clear()
            self.root.clipboard_append(continue_cfg)
            self.status_message.set("تم نسخ إعدادات Continue إلى الحافظة!")

        c_copy_btn = ctk.CTkButton(
            tab_cont,
            text="📋 نسخ كود الإعدادات لـ Continue.dev" if self.is_rtl else "📋 Copy Continue.dev Config",
            command=_copy_continue
        )
        c_copy_btn.pack(fill="x")

        # Cline Tab
        cl_box = ctk.CTkTextbox(tab_cline, font=ctk.CTkFont(family="Segoe UI", size=12), wrap="word")
        cl_box.pack(fill="both", expand=True, pady=(4, 8))
        cl_box.insert("1.0", cline_info)

        def _copy_url_guide():
            self.root.clipboard_clear()
            self.root.clipboard_append(api_url)
            self.status_message.set("تم نسخ رابط API!")

        cl_copy_btn = ctk.CTkButton(
            tab_cline,
            text=f"📋 {self.tr('api_copy_url')} ({api_url})",
            command=_copy_url_guide
        )
        cl_copy_btn.pack(fill="x")

    # -------------------------------------------------------------------------
    # Enhancement 7: Claude Official Models & Live Interactive Artifacts
    # -------------------------------------------------------------------------

    def _render_bubble_files_and_artifacts(self, bubble_frame, files: Optional[List[Dict[str, str]]]):
        if not files:
            return

        # 1. Claude Interactive Artifacts Cards
        artifacts = [f for f in files if f.get("filepath", "").lower().endswith((".html", ".htm", ".svg"))]
        for art in artifacts:
            fp = art.get("filepath", "index.html")
            card = ctk.CTkFrame(
                bubble_frame,
                fg_color=("gray85", "#1e1b4b"),
                border_width=1,
                border_color="#7c3aed",
                corner_radius=10
            )
            card.pack(fill="x", padx=8, pady=(0, 6))

            c_head = ctk.CTkFrame(card, fg_color="transparent")
            c_head.pack(fill="x", padx=10, pady=(6, 2))

            c_title = ctk.CTkLabel(
                c_head,
                text=self.tr("artifact_card_title", name=fp),
                font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                text_color="#c084fc",
                anchor=self.text_anchor
            )
            c_title.pack(side=self.side_start)

            c_type = ctk.CTkLabel(
                c_head,
                text="⚡ " + ("تطبيق ويب تفاعلي" if self.is_rtl else "Interactive Web App"),
                font=ctk.CTkFont(family="Segoe UI", size=10),
                text_color="gray60"
            )
            c_type.pack(side=self.side_end)

            c_btns = ctk.CTkFrame(card, fg_color="transparent")
            c_btns.pack(fill="x", padx=8, pady=(2, 6))

            preview_btn = ctk.CTkButton(
                c_btns,
                text=self.tr("artifact_preview_card_btn"),
                height=24,
                font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
                fg_color="#7c3aed",
                hover_color="#6d28d9",
                command=lambda p=fp: self.open_artifact_tab(p)
            )
            preview_btn.pack(side=self.side_start, padx=2)

            browser_btn = ctk.CTkButton(
                c_btns,
                text=self.tr("artifact_in_browser_btn"),
                height=24,
                font=ctk.CTkFont(family="Segoe UI", size=10),
                fg_color="#059669",
                hover_color="#047857",
                command=lambda p=fp: self.open_specific_file_in_browser(p)
            )
            browser_btn.pack(side=self.side_start, padx=2)

            code_btn = ctk.CTkButton(
                c_btns,
                text="💻 " + ("شفرة الكود" if self.is_rtl else "Code"),
                height=24,
                font=ctk.CTkFont(family="Segoe UI", size=10),
                fg_color="gray30",
                hover_color="gray40",
                command=lambda p=fp: self._select_file_by_name(p)
            )
            code_btn.pack(side=self.side_start, padx=2)

        # 2. General Project Files Bar
        files_card = ctk.CTkFrame(bubble_frame, fg_color=("gray80", "#14171f"), corner_radius=8)
        files_card.pack(fill="x", padx=8, pady=(0, 8))

        f_title = ctk.CTkLabel(
            files_card,
            text="📁 " + ("الملفات التي تم إنشاؤها أو تعديلها" if self.is_rtl else "Generated / Updated Files"),
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            anchor=self.text_anchor
        )
        f_title.pack(fill="x", padx=8, pady=(4, 2))

        chips_row = ctk.CTkFrame(files_card, fg_color="transparent")
        chips_row.pack(fill="x", padx=6, pady=(0, 4))

        for idx, f in enumerate(files):
            fp = f.get("filepath", "file.txt")
            icon = get_file_icon(fp)
            btn = ctk.CTkButton(
                chips_row,
                text=f"{icon} {fp}",
                font=ctk.CTkFont(family="Consolas" if not self.is_rtl else "Segoe UI", size=10),
                height=22,
                corner_radius=6,
                fg_color=("#cbd5e1", "#2563eb"),
                text_color=("black", "white"),
                command=lambda i=idx: self._select_file_index(i)
            )
            btn.pack(side=self.side_start, padx=2, pady=2)

        # Update Artifact selector
        self._update_artifact_file_selector()

    def _select_file_by_name(self, filename: str):
        for idx, f in enumerate(self.project_files):
            if f.get("filepath") == filename:
                self._select_file_index(idx)
                self.tabview.set(self.tr("tab_code"))
                return

    def open_specific_file_in_browser(self, filename: str):
        content = ""
        for f in self.project_files:
            if f.get("filepath") == filename:
                content = f.get("code", "")
                break
        if not content:
            return
        import tempfile
        tmp_dir = tempfile.gettempdir()
        out_path = os.path.join(tmp_dir, Path(filename).name)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(content)
        webbrowser.open(f"file:///{out_path.replace(os.sep, '/')}")
        self.status_message.set(f"🌐 تم فتح الأرتيفاكت في المتصفح: {filename}")

    def _build_artifact_preview_canvas(self):
        for widget in self.art_viewport_container.winfo_children():
            widget.destroy()

        if self.artifact_viewport_mode == "mobile":
            phone_shell = ctk.CTkFrame(
                self.art_viewport_container,
                width=375,
                fg_color=("#f1f5f9", "#0f172a"),
                border_width=3,
                border_color=("#94a3b8", "#334155"),
                corner_radius=24
            )
            phone_shell.pack(expand=True, pady=10)
            phone_shell.pack_propagate(False)

            notch = ctk.CTkFrame(phone_shell, height=18, fg_color=("#cbd5e1", "#1e293b"), corner_radius=10)
            notch.pack(fill="x", padx=40, pady=(6, 4))
            canvas_parent = phone_shell
        else:
            canvas_parent = self.art_viewport_container

        if HAS_TKINTERWEB:
            try:
                self.html_frame = tkinterweb.HtmlFrame(canvas_parent, messages_enabled=False)
                self.html_frame.pack(fill="both", expand=True, padx=4, pady=4)
                self.has_html_renderer = True
            except Exception:
                self.has_html_renderer = False
                self.html_frame = None
        else:
            self.has_html_renderer = False
            self.html_frame = None

        if not self.has_html_renderer:
            self.art_code_box = ctk.CTkTextbox(
                canvas_parent,
                wrap="none",
                font=ctk.CTkFont(family="Consolas", size=12)
            )
            self.art_code_box.pack(fill="both", expand=True, padx=4, pady=4)

    def _on_artifact_combo_selected(self, choice: str):
        if choice and choice != "(No HTML/SVG artifacts)":
            self.render_artifact(filepath=choice)

    def set_artifact_viewport(self, mode: str):
        self.artifact_viewport_mode = mode
        if mode == "mobile":
            self.art_mobile_btn.configure(fg_color="#2563eb", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"))
            self.art_desktop_btn.configure(fg_color="gray30", font=ctk.CTkFont(family="Segoe UI", size=11))
        else:
            self.art_desktop_btn.configure(fg_color="#2563eb", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"))
            self.art_mobile_btn.configure(fg_color="gray30", font=ctk.CTkFont(family="Segoe UI", size=11))

        self._build_artifact_preview_canvas()
        if self.last_rendered_html:
            self.render_artifact(html_content=self.last_rendered_html)

    def _update_artifact_file_selector(self):
        if not hasattr(self, "art_file_selector"):
            return
        art_files = [
            f.get("filepath") for f in self.project_files
            if f.get("filepath", "").lower().endswith((".html", ".htm", ".svg", ".md"))
        ]
        if art_files:
            self.art_file_selector.configure(values=art_files)
            if not self.active_artifact_file or self.active_artifact_file not in art_files:
                self.active_artifact_file = art_files[0]
                self.art_file_selector.set(art_files[0])
        else:
            self.art_file_selector.configure(values=["(No HTML/SVG artifacts)"])
            self.art_file_selector.set("(No HTML/SVG artifacts)")

    def open_artifact_tab(self, filepath: Optional[str] = None):
        self.tabview.set(self.tr("tab_artifacts"))
        self.render_artifact(filepath=filepath)

    def open_current_artifact_in_browser(self):
        content = self.last_rendered_html
        if not content:
            if 0 <= self.active_file_idx < len(self.project_files):
                content = self.project_files[self.active_file_idx].get("code", "")
        if not content:
            return

        import tempfile
        tmp_dir = tempfile.gettempdir()
        fn = self.active_artifact_file or "preview_artifact.html"
        if not fn.lower().endswith((".html", ".htm")):
            fn = f"{fn}.html"
        out_path = os.path.join(tmp_dir, fn)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(content)
        webbrowser.open(f"file:///{out_path.replace(os.sep, '/')}")
        self.status_message.set(f"🌐 تم فتح الأرتيفاكت في المتصفح: {fn}")

    def refresh_active_artifact(self):
        if 0 <= self.active_file_idx < len(self.project_files):
            cur_fp = self.project_files[self.active_file_idx].get("filepath")
            if cur_fp == self.active_artifact_file:
                editor_code = self.code_box.get("1.0", tk.END).rstrip()
                self.project_files[self.active_file_idx]["code"] = editor_code
                self.render_artifact(filepath=cur_fp, html_content=editor_code)
                return
        self.render_artifact(filepath=self.active_artifact_file)

    def render_artifact(self, filepath: Optional[str] = None, html_content: Optional[str] = None):
        self._update_artifact_file_selector()
        if filepath:
            self.active_artifact_file = filepath
            if hasattr(self, "art_file_selector"):
                self.art_file_selector.set(filepath)
            if html_content is None:
                for f in self.project_files:
                    if f.get("filepath") == filepath:
                        html_content = f.get("code", "")
                        break
        elif not html_content:
            if hasattr(self, "art_file_selector"):
                cur = self.art_file_selector.get()
                if cur and cur != "(No HTML/SVG artifacts)":
                    self.active_artifact_file = cur
                    for f in self.project_files:
                        if f.get("filepath") == cur:
                            html_content = f.get("code", "")
                            break
            if not html_content:
                if 0 <= self.active_file_idx < len(self.project_files):
                    af = self.project_files[self.active_file_idx]
                    if af.get("filepath", "").lower().endswith((".html", ".htm", ".svg")):
                        html_content = af.get("code", "")
                        self.active_artifact_file = af.get("filepath")

        if not html_content or not html_content.strip():
            html_content = """<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><style>body{font-family:'Segoe UI',sans-serif;background:#18181b;color:#e4e4e7;display:flex;flex-direction:column;align-items:center;justify-content:center;height:80vh;text-align:center;}h2{color:#a855f7;}p{color:#a1a1aa;max-width:400px;}</style></head>
<body>
  <h2>🎨 استوديو المعاينة الحية للأرتيفاكتس</h2>
  <p>اطلب من المساعد إنشاء صفحة ويب أو لعبة أو واجهة تفاعلية، وسيتم عرضها فوراً هنا كما في Claude Artifacts!</p>
</body>
</html>"""

        self.last_rendered_html = html_content

        if hasattr(self, "html_frame") and self.html_frame:
            try:
                self.html_frame.load_html(html_content)
            except Exception:
                pass
        if hasattr(self, "art_code_box") and self.art_code_box:
            try:
                self.art_code_box.delete("1.0", tk.END)
                self.art_code_box.insert("1.0", html_content)
            except Exception:
                pass

    def show_claude_settings_dialog(self):
        dialog = ctk.CTkToplevel(self.root)
        dialog.title(self.tr("claude_setup_title"))
        dialog.geometry("540x480")
        dialog.transient(self.root)
        dialog.grab_set()

        try:
            x = self.root.winfo_x() + (self.root.winfo_width() - 540) // 2
            y = self.root.winfo_y() + (self.root.winfo_height() - 480) // 2
            dialog.geometry(f"+{max(0, x)}+{max(0, y)}")
        except Exception:
            pass

        content = ctk.CTkFrame(dialog, corner_radius=12)
        content.pack(fill="both", expand=True, padx=16, pady=16)

        header_row = ctk.CTkFrame(content, fg_color="transparent")
        header_row.pack(fill="x", pady=(8, 12))

        c_icon = ctk.CTkLabel(header_row, text="🟣", font=ctk.CTkFont(size=24))
        c_icon.pack(side=self.side_start, padx=6)

        c_title = ctk.CTkLabel(
            header_row,
            text=self.tr("claude_setup_title"),
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold")
        )
        c_title.pack(side=self.side_start)

        desc = (
            "يدعم الاستوديو الاتصال المباشر بنماذج Anthropic الرسمية:\n"
            "• Claude 3.5 Sonnet (الأقوى والأذكى في كتابة وتطوير الأكواد)\n"
            "• Claude 3.5 Haiku (فائق السرعة وخفيف التكلفة)\n"
            "• Claude 3 Opus (للتحليل المعماري المتقدم)\n\n"
            "أدخل مفتاحك الخاص من console.anthropic.com ليتم تفعيل النماذج فوراً:"
            if self.is_rtl else
            "Connect directly to official Anthropic models:\n"
            "• Claude 3.5 Sonnet (Leading coding intelligence)\n"
            "• Claude 3.5 Haiku (Ultra-fast and cost-efficient)\n"
            "• Claude 3 Opus (Complex architectural reasoning)\n\n"
            "Enter your key from console.anthropic.com to activate:"
        )

        desc_lbl = ctk.CTkLabel(
            content,
            text=desc,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            justify="right" if self.is_rtl else "left",
            anchor=self.text_anchor
        )
        desc_lbl.pack(fill="x", pady=(0, 12))

        key_lbl = ctk.CTkLabel(
            content,
            text=self.tr("claude_key_lbl"),
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            anchor=self.text_anchor
        )
        key_lbl.pack(fill="x", pady=(4, 2))

        entry_row = ctk.CTkFrame(content, fg_color="transparent")
        entry_row.pack(fill="x", pady=(0, 8))

        key_var = ctk.StringVar(value=self.claude_key or "")
        key_entry = ctk.CTkEntry(
            entry_row,
            textvariable=key_var,
            font=ctk.CTkFont(family="Consolas", size=12),
            show="*",
            placeholder_text="sk-ant-api03-..."
        )
        key_entry.pack(side=self.side_start, fill="x", expand=True, padx=(0, 6) if not self.is_rtl else (6, 0))

        show_hide_state = [True]
        def _toggle_key_vis():
            if show_hide_state[0]:
                key_entry.configure(show="")
                show_btn.configure(text="🔒")
                show_hide_state[0] = False
            else:
                key_entry.configure(show="*")
                show_btn.configure(text="👁️")
                show_hide_state[0] = True

        show_btn = ctk.CTkButton(
            entry_row,
            text="👁️",
            width=36,
            height=28,
            font=ctk.CTkFont(size=12),
            fg_color="gray30",
            hover_color="gray40",
            command=_toggle_key_vis
        )
        show_btn.pack(side=self.side_end)

        status_feedback = ctk.CTkLabel(
            content,
            text="",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            wraplength=480,
            justify="right" if self.is_rtl else "left",
            anchor=self.text_anchor
        )
        status_feedback.pack(fill="x", pady=6)

        btn_row = ctk.CTkFrame(content, fg_color="transparent")
        btn_row.pack(fill="x", pady=(12, 6))

        def _on_test_click():
            key = key_var.get().strip()
            if not key:
                status_feedback.configure(text="⚠️ يرجى إدخال مفتاح صالح للاختبار.", text_color="#f59e0b")
                return
            status_feedback.configure(text="جاري فحص الاتصال بـ Anthropic... ⏳", text_color="#38bdf8")
            test_btn.configure(state="disabled")

            def _test_thread():
                ok, msg = test_anthropic_key(key)
                def _ui_update():
                    test_btn.configure(state="normal")
                    if ok:
                        status_feedback.configure(text=f"✓ {msg}", text_color="#10b981")
                    else:
                        status_feedback.configure(text=f"❌ {msg}", text_color="#f87171")
                dialog.after(0, _ui_update)

            threading.Thread(target=_test_thread, daemon=True).start()

        test_btn = ctk.CTkButton(
            btn_row,
            text=self.tr("claude_test_btn"),
            width=120,
            height=30,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            fg_color="gray30",
            hover_color="gray40",
            command=_on_test_click
        )
        test_btn.pack(side=self.side_start, padx=4)

        def _on_save_click():
            key = key_var.get().strip()
            if not key:
                status_feedback.configure(text="⚠️ مفتاح API فارغ.", text_color="#f59e0b")
                return
            saved = save_anthropic_api_key(key)
            if saved:
                self.claude_key = key
                self.claude_status_text.set(self.tr("claude_active_badge"))
                self.claude_badge.configure(text_color="#10b981")
                self.claude_setup_btn.configure(fg_color="#7c3aed")
                threading.Thread(target=self.refresh_models, daemon=True).start()
                messagebox.showinfo("تم الحفظ", self.tr("claude_key_saved"))
                dialog.destroy()
            else:
                status_feedback.configure(text="❌ فشل حفظ المفتاح في القرص المحلي.", text_color="#f87171")

        save_btn = ctk.CTkButton(
            btn_row,
            text=self.tr("claude_save_btn"),
            width=130,
            height=30,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            fg_color="#7c3aed",
            hover_color="#6d28d9",
            command=_on_save_click
        )
        save_btn.pack(side=self.side_start, padx=4)

        def _on_remove_click():
            save_anthropic_api_key("")
            self.claude_key = ""
            self.claude_status_text.set(self.tr("claude_inactive_badge"))
            self.claude_badge.configure(text_color="#94a3b8")
            self.claude_setup_btn.configure(fg_color="gray30")
            threading.Thread(target=self.refresh_models, daemon=True).start()
            messagebox.showinfo("تم الحذف", "تم إزالة مفتاح Claude بنجاح.")
            dialog.destroy()

        if self.claude_key:
            remove_btn = ctk.CTkButton(
                btn_row,
                text=self.tr("claude_remove_btn"),
                width=110,
                height=30,
                font=ctk.CTkFont(family="Segoe UI", size=11),
                fg_color="#b91c1c",
                hover_color="#991b1b",
                command=_on_remove_click
            )
            remove_btn.pack(side=self.side_end, padx=4)

    def activate_claude_mode(self):
        """
        Activate Claude mode directly within the GUI application without opening external terminals.
        Switches model, focuses chat, and provides immediate Claude coding capability.
        """
        if self.claude_key:
            claude_model = "claude-3-5-sonnet-20241022"
            values = list(self.model_dropdown.cget("values"))
            if claude_model not in values:
                self.model_dropdown.configure(values=[claude_model, *values])
            self.current_model.set(claude_model)
            self.agent.claude_mode = True
            self.claude_status_text.set("🟢 Claude نشط (Sonnet 3.5)")
            self.claude_badge.configure(text_color="#10b981")
            self.status_message.set("✓ تم تفعيل وضع Claude 3.5 Sonnet مباشرة داخل التطبيق!")

            self._add_agent_bubble(
                message=(
                    "✨ تم تفعيل وضع Claude 3.5 Sonnet داخل هذا التطبيق بنجاح!\n\n"
                    "يمكنك الآن كتابة طلبك البرمجي هنا مباشرة، وسيتم كتابة الأكواد وتعديل الملفات "
                    "وتوليد المعاينة الحية للأرتيفاكتس (HTML/SVG) في الواجهة دون فتح أي نوافذ خارجية."
                ),
                model_info="claude-3-5-sonnet"
            )
            self.chat_textbox.focus_set()
        else:
            self._show_claude_mode_activation_dialog()

    def _show_claude_mode_activation_dialog(self):
        """Show dialog to choose how to activate Claude inside the app."""
        dialog = ctk.CTkToplevel(self.root)
        dialog.title("تفعيل استخدام Claude داخل التطبيق" if self.is_rtl else "Activate Claude In App")
        dialog.geometry("520x320")
        dialog.grab_set()
        dialog.resizable(False, False)

        box = ctk.CTkFrame(dialog, corner_radius=12)
        box.pack(fill="both", expand=True, padx=16, pady=16)

        title_lbl = ctk.CTkLabel(
            box,
            text="🤖 تفعيل وضع Claude مباشرة داخل التطبيق",
            font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
            text_color="#ea580c"
        )
        title_lbl.pack(pady=(8, 4))

        info_lbl = ctk.CTkLabel(
            box,
            text=(
                "سيعمل Claude مباشرة داخل هذا التطبيق (الشات، وتعديل الكود، والمعاينة الحية للأرتيفاكتس)\n"
                "دون الحاجة لفتح أي نافذة تيرمينال أو موجه أوامر خارجي.\n\n"
                "اختر الطريقة المناسبة لك:"
            ),
            font=ctk.CTkFont(family="Segoe UI", size=12),
            wraplength=460,
            justify="center"
        )
        info_lbl.pack(pady=(2, 12))

        def _choose_key():
            dialog.destroy()
            self.show_claude_settings_dialog()

        btn_key = ctk.CTkButton(
            box,
            text="🔑 إدخال مفتاح Anthropic API (لتشغيل Sonnet 3.5 الأصلي)",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            height=36,
            fg_color="#7c3aed",
            hover_color="#6d28d9",
            command=_choose_key
        )
        btn_key.pack(fill="x", padx=16, pady=4)

        def _choose_local():
            dialog.destroy()
            self.agent.claude_mode = True
            cur = self.current_model.get()
            self.claude_status_text.set("🟢 وضع Claude (محلي)")
            self.claude_badge.configure(text_color="#10b981")
            self.status_message.set(f"✓ تم تفعيل وضع Claude الذكي مع نموذج {cur} داخل التطبيق!")
            self._add_agent_bubble(
                message=(
                    f"✨ تم تفعيل وضع Claude الذكي مع النموذج المحلي ({cur}) داخل التطبيق بنجاح!\n\n"
                    "يتم الآن توجيه النموذج بمعمارية وهندسة مطالبات Claude لإنتاج كود احترافي "
                    "وأرتيفاكتس تفاعلية حية مباشرة في التطبيق."
                ),
                model_info=f"Claude Mode ({cur})"
            )
            self.chat_textbox.focus_set()

        btn_local = ctk.CTkButton(
            box,
            text="⚡ تفعيل وضع Claude مع نموذجك المحلي الحالي (مجاناً 100%)",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            height=36,
            fg_color="#ea580c",
            hover_color="#c2410c",
            command=_choose_local
        )
        btn_local.pack(fill="x", padx=16, pady=4)

        def _choose_cli():
            dialog.destroy()
            self.launch_claude_code_terminal(embedded=True)

        btn_cli = ctk.CTkButton(
            box,
            text="💻 تشغيل جلسة Claude Code في الكونسول الداخلي للتطبيق",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            height=30,
            fg_color="gray30",
            hover_color="gray40",
            command=_choose_cli
        )
        btn_cli.pack(fill="x", padx=16, pady=4)

    def launch_claude_code_terminal(self, embedded: bool = True):
        """
        Launch Claude Code agent via Ollama.
        When embedded=True (default), it runs INSIDE the application's Console tab
        without opening any external terminal window.
        """
        project_dir = self.project_dir.get().strip() or os.getcwd()
        os.makedirs(project_dir, exist_ok=True)

        cur_model = self.current_model.get().strip()
        if cur_model and not cur_model.startswith("claude") and cur_model not in ("Searching...", "Offline", "No models"):
            cmd = f"ollama launch claude -y --model '{cur_model}'"
        else:
            cmd = "ollama launch claude -y"

        if embedded:
            self.tabview.set(self.tr("tab_console"))
            self.console_box.delete("1.0", tk.END)
            self.console_box.insert(tk.END, "=== [ Claude Code Console / جلسة Claude داخل التطبيق ] ===\n")
            self.console_box.insert(tk.END, f"Directory: {project_dir}\nCommand: {cmd}\n")
            self.console_box.insert(tk.END, "=" * 60 + "\n\n")
            self.status_message.set(self.tr("claude_code_launched"))

            self.kill_console_process()

            creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            try:
                self.console_process = subprocess.Popen(
                    cmd,
                    shell=True,
                    cwd=project_dir,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    creationflags=creationflags
                )

                def _reader():
                    proc = self.console_process
                    if not proc or not proc.stdout:
                        return
                    for line in proc.stdout:
                        self._safe_after(0, lambda l=line: self._append_to_console(l))
                    self._safe_after(0, lambda: self._append_to_console("\n[اكتملت أو أغلقت جلسة Claude]\n"))

                self.console_reader_thread = threading.Thread(target=_reader, daemon=True)
                self.console_reader_thread.start()
            except Exception as e:
                self.console_box.insert(tk.END, f"[خطأ في تشغيل العملية: {str(e)}]\n")
        else:
            launch_cmd = f'start "Claude Code - Ollama Agent" powershell -NoExit -Command "Set-Location -LiteralPath \'{project_dir}\'; {cmd}"'
            try:
                subprocess.Popen(launch_cmd, shell=True, cwd=project_dir)
                self.status_message.set(self.tr("claude_code_launched"))
            except Exception as e:
                messagebox.showerror("خطأ", f"تعذر تشغيل Claude Code: {str(e)}")

    def _append_to_console(self, text: str):
        try:
            self.console_box.insert(tk.END, text)
            self.console_box.see(tk.END)
        except Exception:
            pass

    def _send_console_input(self):
        text = self.console_input_entry.get().strip()
        if not text:
            return
        self.console_input_entry.delete(0, tk.END)
        self.console_box.insert(tk.END, f"\n> {text}\n")
        self.console_box.see(tk.END)
        if self.console_process and self.console_process.poll() is None and self.console_process.stdin:
            try:
                self.console_process.stdin.write(text + "\n")
                self.console_process.stdin.flush()
            except Exception as e:
                self.console_box.insert(tk.END, f"[خطأ في إرسال المدخلات: {str(e)}]\n")

    def kill_console_process(self):
        if self.console_process and self.console_process.poll() is None:
            try:
                self.console_process.terminate()
                self._append_to_console("\n[تم إنهاء العملية من قبل المستخدم]\n")
            except Exception:
                pass
        self.console_process = None

    def _on_window_close(self):
        self.kill_console_process()
        if self.api_server:
            try:
                self.api_server.stop()
            except Exception:
                pass
        self.root.destroy()
