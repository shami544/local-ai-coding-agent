import os
import sys
import subprocess
import time
import webbrowser
import zipfile
import re
from pathlib import Path
from typing import Dict, Any, List, Optional


class ExecutionError(Exception):
    """Custom exception for execution or filesystem errors."""
    pass


def resolve_safe_path(base_dir: str, filepath: str) -> Path:
    """
    Safely resolve a relative filepath against a base project directory,
    preventing directory traversal attacks (e.g. ../../).
    """
    if not base_dir:
        raise ExecutionError("Project directory is not set.")

    base_path = Path(base_dir).resolve()
    clean_filepath = filepath.strip().replace("\\", "/").lstrip("/")
    if not clean_filepath:
        raise ExecutionError("Target file path cannot be empty.")

    target_path = (base_path / clean_filepath).resolve()

    try:
        target_path.relative_to(base_path)
    except ValueError:
        raise ExecutionError(f"Target path '{filepath}' escapes project directory '{base_dir}'.")

    return target_path


def write_code_file(base_dir: str, filepath: str, code: str) -> Dict[str, Any]:
    """
    Writes code to the specified relative filepath within base_dir.
    Automatically creates intermediate directories if needed.
    """
    target_path = resolve_safe_path(base_dir, filepath)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(code, encoding="utf-8")

    stat = target_path.stat()
    line_count = len(code.splitlines())

    return {
        "success": True,
        "full_path": str(target_path),
        "filename": target_path.name,
        "relative_path": str(target_path.relative_to(Path(base_dir).resolve())).replace("\\", "/"),
        "bytes_written": stat.st_size,
        "lines": line_count,
    }


def write_project_bundle(base_dir: str, files: List[Dict[str, str]]) -> Dict[str, Any]:
    """
    Writes all files in a multi-file project to disk in one batch operation.
    """
    if not base_dir:
        raise ExecutionError("Project directory is not set.")
    if not files:
        raise ExecutionError("No files to write.")

    results = []
    total_bytes = 0
    total_lines = 0

    for file_info in files:
        fp = file_info.get("filepath", "file.txt")
        code = file_info.get("code", "")
        res = write_code_file(base_dir, fp, code)
        results.append(res)
        total_bytes += res["bytes_written"]
        total_lines += res["lines"]

    return {
        "success": True,
        "files_written": len(results),
        "total_bytes": total_bytes,
        "total_lines": total_lines,
        "files": results
    }


def open_file_in_browser(base_dir: str, filepath: str = "index.html") -> Dict[str, Any]:
    """
    Opens an HTML or web file in the default web browser.
    """
    if not base_dir:
        raise ExecutionError("Project directory is not set.")

    # Try requested filepath first
    try:
        target = resolve_safe_path(base_dir, filepath)
    except Exception:
        target = None

    # If target doesn't exist, search for index.html or any .html file
    if target is None or not target.exists():
        base_path = Path(base_dir).resolve()
        candidate = base_path / "index.html"
        if candidate.exists():
            target = candidate
        else:
            html_files = list(base_path.glob("**/*.html"))
            if html_files:
                target = html_files[0]
            else:
                return {
                    "success": False,
                    "error": f"No HTML files found in '{base_dir}'. Please write your project files first."
                }

    uri = target.as_uri()
    webbrowser.open(uri)
    return {
        "success": True,
        "file": str(target),
        "uri": uri
    }


def execute_script(
    base_dir: str,
    filepath: str,
    timeout_sec: int = 45,
    custom_args: list = None
) -> Dict[str, Any]:
    """
    Executes the specified Python script within the project directory.
    Captures stdout, stderr, execution duration, and exit code.
    """
    target_path = resolve_safe_path(base_dir, filepath)

    if not target_path.exists():
        return {
            "success": False,
            "returncode": -1,
            "stdout": "",
            "stderr": f"الملف غير موجود على القرص: {target_path}\nيرجى الضغط على 'حفظ كامل المشروع' أولاً.",
            "duration": 0.0,
            "timed_out": False
        }

    # Detect execution runner: Python vs Node.js vs NPM
    ext = target_path.suffix.lower()
    base_p = Path(base_dir).resolve()
    has_package_json = (base_p / "package.json").exists()

    if ext in [".js", ".mjs", ".cjs"]:
        # If it's a Next.js / Node project with package.json
        cmd = ["node", str(target_path)]
    elif ext in [".py"]:
        cmd = [sys.executable, str(target_path)]
    elif has_package_json and filepath in ["package.json", "next.config.js"]:
        cmd = ["npm.cmd" if sys.platform == "win32" else "npm", "run", "dev"]
    else:
        cmd = [sys.executable, str(target_path)]

    if custom_args:
        cmd.extend(custom_args)

    start_time = time.time()
    try:
        run_env = os.environ.copy()
        run_env["PYTHONIOENCODING"] = "utf-8"
        run_env["PYTHONUTF8"] = "1"

        process = subprocess.run(
            cmd,
            cwd=base_dir,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            encoding="utf-8",
            errors="replace",
            env=run_env
        )
        duration = time.time() - start_time
        return {
            "success": process.returncode == 0,
            "returncode": process.returncode,
            "stdout": process.stdout,
            "stderr": process.stderr,
            "duration": round(duration, 3),
            "timed_out": False
        }
    except subprocess.TimeoutExpired as exc:
        duration = time.time() - start_time
        return {
            "success": False,
            "returncode": -1,
            "stdout": exc.stdout or "" if isinstance(exc.stdout, str) else "",
            "stderr": f"Execution timed out after {timeout_sec} seconds.",
            "duration": round(duration, 3),
            "timed_out": True
        }
    except Exception as e:
        duration = time.time() - start_time
        return {
            "success": False,
            "returncode": -1,
            "stdout": "",
            "stderr": f"Execution failed with error: {str(e)}",
            "duration": round(duration, 3),
            "timed_out": False
        }


def detect_missing_package(stderr: str) -> Optional[Dict[str, str]]:
    """
    Analyzes stderr to detect missing Python packages (ModuleNotFoundError)
    or missing Node.js packages (Cannot find module).
    """
    if not stderr:
        return None

    # Python: ModuleNotFoundError: No module named 'xyz'
    # or ImportError: No module named 'xyz'
    py_match = re.search(r"(?:ModuleNotFoundError|ImportError):\s*No module named ['\"]([^'\"]+)['\"]", stderr)
    if py_match:
        pkg = py_match.group(1).split(".")[0]
        # Mapping for common packages whose pip name differs from module name
        pkg_map = {
            "cv2": "opencv-python",
            "PIL": "pillow",
            "bs4": "beautifulsoup4",
            "yaml": "pyyaml",
            "sklearn": "scikit-learn",
            "dotenv": "python-dotenv",
            "serial": "pyserial",
        }
        pkg = pkg_map.get(pkg, pkg)
        return {"package": pkg, "manager": "pip"}

    # Node.js: Error: Cannot find module 'xyz'
    node_match = re.search(r"Cannot find module ['\"]([^'\"]+)['\"]", stderr)
    if node_match:
        pkg = node_match.group(1)
        # Filter out local relative imports (e.g. ./app or ../utils)
        if not pkg.startswith("."):
            return {"package": pkg, "manager": "npm"}

    return None


def install_package(
    package_name: str,
    manager: str = "pip",
    cwd: Optional[str] = None
) -> Dict[str, Any]:
    """
    Installs a missing package using pip or npm.
    """
    clean_pkg = package_name.strip()
    if not clean_pkg:
        return {"success": False, "stdout": "", "stderr": "Package name is empty.", "returncode": -1}

    if manager == "npm":
        cmd = ["npm.cmd" if sys.platform == "win32" else "npm", "install", clean_pkg]
    else:
        cmd = [sys.executable, "-m", "pip", "install", clean_pkg]

    try:
        proc = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=180,
            encoding="utf-8",
            errors="replace"
        )
        return {
            "success": proc.returncode == 0,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "returncode": proc.returncode,
            "command": " ".join(cmd)
        }
    except Exception as e:
        return {
            "success": False,
            "stdout": "",
            "stderr": str(e),
            "returncode": -1,
            "command": " ".join(cmd)
        }


def export_project_zip(
    base_dir: str,
    output_zip_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Compresses all files in base_dir into a zip archive.
    Ignores git, node_modules, cache dirs, and existing zips.
    """
    base_path = Path(base_dir).resolve()
    if not base_path.exists() or not base_path.is_dir():
        raise ExecutionError(f"Directory '{base_dir}' does not exist.")

    if not output_zip_path:
        output_zip_path = str(base_path.parent / f"{base_path.name}_export.zip")

    dest = Path(output_zip_path).resolve()
    dest.parent.mkdir(parents=True, exist_ok=True)

    ignored_dirs = {
        ".git", "__pycache__", "node_modules", ".venv", "venv",
        ".next", ".cache", ".pytest_cache", ".idea", ".vscode"
    }
    ignored_exts = {".zip", ".tar", ".gz", ".rar", ".7z"}

    count = 0
    total_bytes = 0

    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(base_path):
            dirs[:] = [d for d in dirs if d not in ignored_dirs and not d.startswith(".")]
            for file in files:
                f_path = Path(root) / file
                if f_path.resolve() == dest:
                    continue
                if f_path.suffix.lower() in ignored_exts:
                    continue

                rel_path = f_path.relative_to(base_path)
                zf.write(f_path, arcname=str(rel_path).replace("\\", "/"))
                count += 1
                total_bytes += f_path.stat().st_size

    return {
        "success": True,
        "zip_path": str(dest),
        "file_count": count,
        "total_bytes": total_bytes
    }


def scan_existing_project(dir_path: str) -> List[Dict[str, str]]:
    """
    Scans a directory for code/text files and returns them as a project bundle
    so the user and agent can immediately inspect and modify existing projects.
    """
    base = Path(dir_path).resolve()
    if not base.exists() or not base.is_dir():
        return []

    ignored_dirs = {
        ".git", "__pycache__", "node_modules", ".venv", "venv",
        ".next", "dist", "build", ".idea", ".vscode", ".cache"
    }

    allowed_exts = {
        ".py", ".js", ".mjs", ".cjs", ".jsx", ".ts", ".tsx",
        ".html", ".htm", ".css", ".scss", ".json", ".md",
        ".txt", ".sql", ".sh", ".bat", ".yaml", ".yml", ".env"
    }

    files: List[Dict[str, str]] = []

    for root, dirs, filenames in os.walk(base):
        dirs[:] = [d for d in dirs if d not in ignored_dirs and not d.startswith(".")]
        for fn in filenames:
            ext = Path(fn).suffix.lower()
            if ext in allowed_exts:
                full_p = Path(root) / fn
                # Skip files larger than 1 MB to prevent memory bloat
                try:
                    if full_p.stat().st_size > 1_000_000:
                        continue
                    content = full_p.read_text(encoding="utf-8", errors="replace")
                    rel_fp = str(full_p.relative_to(base)).replace("\\", "/")
                    files.append({
                        "filepath": rel_fp,
                        "code": content,
                        "description": f"ملف محلي تم تحميله: {rel_fp}"
                    })
                except Exception:
                    pass

    return files
