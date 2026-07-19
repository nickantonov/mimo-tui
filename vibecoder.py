"""
MiMo TUI — VibeCoder
Autonomous coding loop: generate → execute → fix → retry.
"""

import re

MAX_ATTEMPTS = 5

_SYS = """You are MiMo VibeCoder — autonomous expert programmer.

Rules:
1. Write COMPLETE, RUNNABLE code — no placeholders, no "# TODO"
2. Always wrap code in ```python\\n...\\n``` block
3. On error: read the traceback carefully, fix the EXACT problem, rewrite the FULL code
4. Never repeat the same mistake twice
5. Prefer stdlib over external packages unless the task explicitly requires them
6. Output ONLY the code block + one short sentence describing what you changed (on retry)
"""


def _extract_code(text: str) -> str:
    m = re.search(r"```(?:python)?\n(.*?)```", text, re.DOTALL)
    return m.group(1).strip() if m else text.strip()


def _is_error(output: str) -> bool:
    return (
        output.startswith("ERROR:")
        or "Traceback (most recent call last)" in output
        or "SyntaxError:" in output
        or "NameError:" in output
        or "ImportError:" in output
        or "ModuleNotFoundError:" in output
    )


class VibeCoder:
    """
    Generate → Execute → Fix loop backed by skill library.

    Usage:
        vc = VibeCoder(brain, memory, run_python_fn)
        code, output, ok = vc.code("parse CSV file and print top 5 rows")
    """

    def __init__(self, brain, memory, run_fn):
        self.brain = brain
        self.memory = memory
        self._run = run_fn

    def code(self, task: str, context: str = "", max_attempts: int = MAX_ATTEMPTS) -> tuple[str, str, bool]:
        """Returns (final_code, last_output, success)."""
        system = _SYS + self._skill_context(task)
        if context:
            system += f"\n\n## Project context:\n{context}"

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": f"Task: {task}"},
        ]
        last_code = last_output = ""

        for attempt in range(max_attempts):
            content, _, _ = self.brain.stream(messages, tools=None, model_key="smart")
            code = _extract_code(content)
            last_code = code
            output = self._run(code)
            last_output = output

            if not _is_error(output):
                if len(code) > 30:
                    self.memory.code.save(task, code, language="python")
                return code, output, True

            messages.append({"role": "assistant", "content": content})
            messages.append({
                "role": "user",
                "content": (
                    f"Attempt {attempt + 1}/{max_attempts} failed:\n"
                    f"```\n{output[:800]}\n```\n"
                    "Fix the error. Rewrite the COMPLETE code."
                ),
            })

        return last_code, last_output, False

    def _skill_context(self, task: str) -> str:
        snippets = self.memory.code.find(task, top_k=2)
        if not snippets:
            return ""
        lines = ["\n\n## Skills from library (reuse if relevant):"]
        for s in snippets:
            lines.append(f"### {s.purpose}")
            lines.append(f"```python\n{s.code[:500]}\n```")
        return "\n".join(lines)
