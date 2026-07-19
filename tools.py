"""
MiMo TUI — Tools
File ops, git, python execution, system monitoring.
"""

import ast
import os
import subprocess
import sys
import tempfile
from pathlib import Path

WORK_DIR = Path(os.getenv("MIMO_WORK_DIR", os.getcwd()))


# ── File tools ─────────────────────────────────────────────────────────────────
def write_file(filename: str, content: str) -> str:
    p = Path(filename)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return f"Written: {filename} ({len(content)} chars)"


def append_file(filename: str, content: str) -> str:
    with open(filename, "a", encoding="utf-8") as f:
        f.write(content)
    return f"Appended to {filename}"


def read_file(filename: str) -> str:
    try:
        return Path(filename).read_text(encoding="utf-8")
    except Exception as e:
        return f"ERROR: {e}"


def list_files(path: str = "") -> str:
    target = Path(path) if path else WORK_DIR
    try:
        entries = sorted(target.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
        lines = [("[DIR] " if e.is_dir() else "      ") + e.name for e in entries]
        return "\n".join(lines) or "(empty)"
    except Exception as e:
        return f"ERROR: {e}"


def search_files(pattern: str, path: str = "", extensions: str = ".py .js .ts .txt .md .json") -> str:
    target = Path(path) if path else WORK_DIR
    exts = [e.strip() for e in extensions.split()]
    found = []
    for root, _, files in os.walk(target):
        for fname in files:
            if exts and not any(fname.endswith(e) for e in exts):
                continue
            fp = os.path.join(root, fname)
            try:
                with open(fp, encoding="utf-8", errors="ignore") as f:
                    for i, line in enumerate(f, 1):
                        if pattern.lower() in line.lower():
                            found.append(f"{fp}:{i}: {line.rstrip()}")
                            if len(found) >= 50:
                                break
            except Exception:
                pass
        if len(found) >= 50:
            break
    return "\n".join(found) if found else "Nothing found."


# ── Execution ──────────────────────────────────────────────────────────────────
def run_python(code: str) -> str:
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", encoding="utf-8", delete=False) as f:
        f.write(code)
        tmp = f.name
    try:
        r = subprocess.run(
            [sys.executable, tmp],
            capture_output=True, text=True, timeout=30, cwd=str(WORK_DIR),
        )
        out = (r.stdout + r.stderr).strip()
        return out[:2000] or "(no output)"
    except subprocess.TimeoutExpired:
        return "ERROR: timeout 30s"
    except Exception as e:
        return f"ERROR: {e}"
    finally:
        try:
            os.unlink(tmp)
        except Exception:
            pass


def execute_cmd(command: str) -> str:
    try:
        r = subprocess.run(
            command, shell=True, capture_output=True, text=True,
            timeout=30, cwd=str(WORK_DIR),
        )
        return (r.stdout + r.stderr).strip()[:2000] or "(no output)"
    except subprocess.TimeoutExpired:
        return "ERROR: timeout 30s"
    except Exception as e:
        return f"ERROR: {e}"


# ── Git ────────────────────────────────────────────────────────────────────────
def git_status(path: str = "") -> str:
    try:
        r = subprocess.run(
            ["git", "-C", path or str(WORK_DIR), "status", "--short"],
            capture_output=True, text=True, timeout=10,
        )
        return r.stdout or "Clean."
    except Exception as e:
        return f"ERROR: {e}"


def git_log(path: str = "", n: int = 10) -> str:
    try:
        r = subprocess.run(
            ["git", "-C", path or str(WORK_DIR), "log", "--oneline", f"-{n}"],
            capture_output=True, text=True, timeout=10,
        )
        return r.stdout or "No commits."
    except Exception as e:
        return f"ERROR: {e}"


def git_diff(path: str = "", staged: bool = False) -> str:
    try:
        args = ["git", "-C", path or str(WORK_DIR), "diff"]
        if staged:
            args.append("--cached")
        r = subprocess.run(args, capture_output=True, text=True, timeout=10)
        return r.stdout[:4000] or "No changes."
    except Exception as e:
        return f"ERROR: {e}"


def git_commit(message: str, path: str = "") -> str:
    try:
        subprocess.run(
            ["git", "-C", path or str(WORK_DIR), "add", "-A"],
            capture_output=True, timeout=10,
        )
        r = subprocess.run(
            ["git", "-C", path or str(WORK_DIR), "commit", "-m", message],
            capture_output=True, text=True, timeout=15,
        )
        return (r.stdout + r.stderr).strip() or "Committed."
    except Exception as e:
        return f"ERROR: {e}"


# ── System ─────────────────────────────────────────────────────────────────────
def system_status() -> str:
    try:
        import psutil
        cpu = psutil.cpu_percent(interval=0.5)
        ram = psutil.virtual_memory()
        return f"CPU: {cpu}% | RAM: {ram.used // 1024**2}/{ram.total // 1024**2} MB ({ram.percent}%)"
    except ImportError:
        return "ERROR: pip install psutil"
    except Exception as e:
        return f"ERROR: {e}"


def calculate(expression: str) -> str:
    try:
        tree = ast.parse(expression, mode="eval")
        ops = {
            ast.Add: lambda a, b: a + b, ast.Sub: lambda a, b: a - b,
            ast.Mult: lambda a, b: a * b, ast.Div: lambda a, b: a / b,
            ast.Pow: lambda a, b: a**b, ast.Mod: lambda a, b: a % b,
        }

        def ev(n):
            if isinstance(n, ast.Expression):
                return ev(n.body)
            if isinstance(n, ast.Constant):
                return n.value
            if isinstance(n, ast.BinOp):
                return ops[type(n.op)](ev(n.left), ev(n.right))
            if isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.USub):
                return -ev(n.operand)
            raise ValueError(f"unsupported: {type(n)}")

        return str(ev(tree))
    except Exception as e:
        return f"ERROR: {e}"


# ── AST analyzer ──────────────────────────────────────────────────────────────
def ast_check(code: str) -> list:
    issues = set()
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return ["syntax_error"]
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler):
            if node.type is None:
                issues.add("bare_except")
            if getattr(node.type, "id", "") == "Exception":
                issues.add("broad_exception")
        if isinstance(node, ast.Try):
            if len(node.handlers) == 0:
                issues.add("no_except_handler")
    return list(issues)


# ── Tool registry ──────────────────────────────────────────────────────────────
TOOL_FUNCTIONS = {
    "write_file": lambda **kw: write_file(**kw),
    "append_file": lambda **kw: append_file(**kw),
    "read_file": lambda **kw: read_file(**kw),
    "list_files": lambda **kw: list_files(**kw),
    "search_files": lambda **kw: search_files(**kw),
    "run_python": lambda **kw: run_python(**kw),
    "execute_cmd": lambda **kw: execute_cmd(**kw),
    "git_status": lambda **kw: git_status(**kw),
    "git_log": lambda **kw: git_log(**kw),
    "git_diff": lambda **kw: git_diff(**kw),
    "git_commit": lambda **kw: git_commit(**kw),
    "system_status": lambda **kw: system_status(),
    "calculate": lambda **kw: calculate(**kw),
}

TOOLS_SCHEMA = [
    {"type": "function", "function": {"name": "write_file", "description": "Write/overwrite a file.", "parameters": {"type": "object", "properties": {"filename": {"type": "string"}, "content": {"type": "string"}}, "required": ["filename", "content"]}}},
    {"type": "function", "function": {"name": "append_file", "description": "Append to end of file.", "parameters": {"type": "object", "properties": {"filename": {"type": "string"}, "content": {"type": "string"}}, "required": ["filename", "content"]}}},
    {"type": "function", "function": {"name": "read_file", "description": "Read a file.", "parameters": {"type": "object", "properties": {"filename": {"type": "string"}}, "required": ["filename"]}}},
    {"type": "function", "function": {"name": "list_files", "description": "List files in directory.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": []}}},
    {"type": "function", "function": {"name": "search_files", "description": "Search for text in files.", "parameters": {"type": "object", "properties": {"pattern": {"type": "string"}, "path": {"type": "string"}, "extensions": {"type": "string"}}, "required": ["pattern"]}}},
    {"type": "function", "function": {"name": "run_python", "description": "Execute Python code.", "parameters": {"type": "object", "properties": {"code": {"type": "string"}}, "required": ["code"]}}},
    {"type": "function", "function": {"name": "execute_cmd", "description": "Execute shell command.", "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}},
    {"type": "function", "function": {"name": "git_status", "description": "Git status.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": []}}},
    {"type": "function", "function": {"name": "git_log", "description": "Git log.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "n": {"type": "integer"}}, "required": []}}},
    {"type": "function", "function": {"name": "git_diff", "description": "Git diff.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "staged": {"type": "boolean"}}, "required": []}}},
    {"type": "function", "function": {"name": "git_commit", "description": "Git add + commit.", "parameters": {"type": "object", "properties": {"message": {"type": "string"}, "path": {"type": "string"}}, "required": ["message"]}}},
    {"type": "function", "function": {"name": "system_status", "description": "CPU/RAM status.", "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {"name": "calculate", "description": "Math calculator.", "parameters": {"type": "object", "properties": {"expression": {"type": "string"}}, "required": ["expression"]}}},
]


def tool_executor(name: str, args: dict) -> str:
    fn = TOOL_FUNCTIONS.get(name)
    if fn is None:
        return f"ERROR: unknown tool '{name}'"
    try:
        return str(fn(**args))
    except Exception as e:
        return f"ERROR in {name}: {e}"
