import os
import tkinter as tk
from pygments import lex
from pygments.lexers import get_lexer_by_name, guess_lexer, PythonLexer
from pygments.token import Token

DARK_PALETTE = {
    Token.Keyword: "#569CD6",
    Token.Keyword.Constant: "#569CD6",
    Token.Keyword.Declaration: "#569CD6",
    Token.Keyword.Namespace: "#C586C0",
    Token.Keyword.Type: "#4EC9B0",
    Token.Name.Function: "#DCDCAA",
    Token.Name.Class: "#4EC9B0",
    Token.Name.Builtin: "#4EC9B0",
    Token.Name.Decorator: "#DCDCAA",
    Token.Name.Variable: "#9CDCFE",
    Token.String: "#CE9178",
    Token.String.Doc: "#6A9955",
    Token.Number: "#B5CEA8",
    Token.Comment: "#6A9955",
    Token.Comment.Single: "#6A9955",
    Token.Comment.Multiline: "#6A9955",
    Token.Operator: "#D4D4D4",
    Token.Operator.Word: "#569CD6",
    Token.Punctuation: "#D4D4D4",
    Token.Text: "#D4D4D4",
}

LIGHT_PALETTE = {
    Token.Keyword: "#0000FF",
    Token.Keyword.Constant: "#0000FF",
    Token.Keyword.Declaration: "#0000FF",
    Token.Keyword.Namespace: "#AF00DB",
    Token.Keyword.Type: "#267F99",
    Token.Name.Function: "#795E26",
    Token.Name.Class: "#267F99",
    Token.Name.Builtin: "#267F99",
    Token.Name.Decorator: "#795E26",
    Token.Name.Variable: "#001080",
    Token.String: "#A31515",
    Token.String.Doc: "#008000",
    Token.Number: "#098658",
    Token.Comment: "#008000",
    Token.Comment.Single: "#008000",
    Token.Comment.Multiline: "#008000",
    Token.Operator: "#000000",
    Token.Operator.Word: "#0000FF",
    Token.Punctuation: "#000000",
    Token.Text: "#000000",
}


def get_lexer_for_filename(filename: str):
    """Determine the Pygments lexer based on file extension."""
    if not filename:
        return PythonLexer()
    ext = os.path.splitext(filename)[1].lower()
    mapping = {
        ".py": "python",
        ".js": "javascript",
        ".ts": "typescript",
        ".html": "html",
        ".css": "css",
        ".json": "json",
        ".sql": "sql",
        ".sh": "bash",
        ".ps1": "powershell",
        ".md": "markdown",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".c": "c",
        ".cpp": "cpp",
        ".rs": "rust",
        ".go": "go",
    }
    lexer_name = mapping.get(ext)
    if lexer_name:
        try:
            return get_lexer_by_name(lexer_name)
        except Exception:
            pass
    return PythonLexer()


class CodeHighlighter:
    """Applies syntax highlighting tags to a Tkinter / CustomTkinter Text widget."""

    def __init__(self, text_widget: tk.Text, mode: str = "dark"):
        self.text_widget = text_widget
        self.mode = mode
        self.palette = DARK_PALETTE if mode == "dark" else LIGHT_PALETTE
        self._setup_tags()

    def set_mode(self, mode: str):
        self.mode = mode
        self.palette = DARK_PALETTE if mode == "dark" else LIGHT_PALETTE
        self._setup_tags()

    def _setup_tags(self):
        for token_type, color in self.palette.items():
            tag_name = str(token_type)
            self.text_widget.tag_configure(tag_name, foreground=color)

    def highlight(self, filename: str = "main.py"):
        """Scan and apply syntax tags to the content of the text widget."""
        content = self.text_widget.get("1.0", tk.END)
        if not content.strip():
            return

        # Remove existing token tags
        for token_type in self.palette.keys():
            self.text_widget.tag_remove(str(token_type), "1.0", tk.END)

        lexer = get_lexer_for_filename(filename)

        # Pygments returns (token_type, value)
        start_index = "1.0"
        for token_type, value in lex(content, lexer):
            if not value:
                continue

            # Find matching style token
            matched_style = None
            curr = token_type
            while curr:
                if curr in self.palette:
                    matched_style = curr
                    break
                curr = curr.parent

            # Calculate end index in tk.Text format
            end_index = self.text_widget.index(f"{start_index} + {len(value)}c")

            if matched_style:
                self.text_widget.tag_add(str(matched_style), start_index, end_index)

            start_index = end_index
