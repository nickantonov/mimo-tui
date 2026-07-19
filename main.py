"""
MiMo TUI — Main
Autonomous AI coding assistant for legacy hardware.
No Bun, no opencode, no SolidJS — just Python + Rich + MiMo API.
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

from core.brain import Brain
from core.auth import get_fingerprint
from core.memory import Memory
from core.tools import TOOLS_SCHEMA, tool_executor, run_python, ast_check
from core.vibecoder import VibeCoder
from core.planner import Planner, PlanQueue, PlanRunner, Plan
from core.cerebro import Cerebro

console = Console()

# ── Config ─────────────────────────────────────────────────────────────────────
DATA_DIR = Path(__file__).parent / "data"
SESSION_FILE = DATA_DIR / "session.json"
PLAN_FILE = str(DATA_DIR / "plans.json")
MAX_ITER = 8

# ── Modes ──────────────────────────────────────────────────────────────────────
_mode = "auto"
MODES = {
    "auto":  {"label": "AUTO",  "color": "bright_cyan", "model": "smart",  "iter": 8, "desc": "Smart automatic"},
    "code":  {"label": "CODE",  "color": "green",       "model": "smart",  "iter": 12, "desc": "Vibe coding + auto-retry"},
    "plan":  {"label": "PLAN",  "color": "magenta",     "model": "smart",  "iter": 10, "desc": "Autonomous task planning"},
    "local": {"label": "LOCAL", "color": "yellow",      "model": "local",  "iter": 6, "desc": "Ollama only (offline)"},
    "fast":  {"label": "FAST",  "color": "cyan",        "model": "fast",   "iter": 5, "desc": "Fast (small model, save tokens)"},
}

# ── System prompt ──────────────────────────────────────────────────────────────
def system_prompt(memory: Memory, query: str = "") -> str:
    m = MODES.get(_mode, MODES["auto"])
    base = (
        f"You are MiMo TUI v1.0 — autonomous AI coding assistant.\n"
        f"Current mode: {m['label']} — {m['desc']}\n"
        "Built by Borodachamba Studio.\n\n"
        "You have REAL access to:\n"
        "  • File system (read/write/search/list)\n"
        "  • Python execution (run_python)\n"
        "  • Shell commands (execute_cmd)\n"
        "  • Git (status, log, diff, commit)\n"
        "  • System monitoring (CPU/RAM)\n"
        "  • Calculator\n\n"
        "RULES:\n"
        "1. NEVER say 'I don't have access' — use tools immediately.\n"
        "2. For files — call list_files or read_file FIRST.\n"
        "3. For code tasks — write and test code.\n"
        "4. Simple questions — answer directly.\n\n"
        "Respond in Russian or Ukrainian (match user's language).\n"
        "Be concise, direct, confident.\n"
    )
    ctx = memory.context_for(query)
    if ctx:
        base += f"\n## Memory context:\n{ctx}\n"
    return base


# ── Agent loop ─────────────────────────────────────────────────────────────────
def run_agent(task: str, history: list, brain: Brain, memory: Memory, model_key: str = "smart") -> str:
    m_cfg = MODES.get(_mode, MODES["auto"])
    use_model = m_cfg["model"] if _mode != "auto" else model_key
    max_iter = m_cfg["iter"]

    messages = (
        [{"role": "system", "content": system_prompt(memory, task)}]
        + history[-10:]
        + [{"role": "user", "content": task}]
    )

    def panel_fn(text):
        return Panel(text or "[dim]...[/dim]",
                     title=f"[bold bright_cyan]▶  MiMo [{_mode.upper()}][/{_mode.upper()}]",
                     border_style="bright_cyan", padding=(0, 1))

    for _ in range(max_iter):
        content, tool_calls, finish = brain.stream(messages, tools=TOOLS_SCHEMA, model_key=use_model, panel_fn=panel_fn)

        assistant_msg = {"role": "assistant", "content": content}
        if tool_calls:
            assistant_msg["tool_calls"] = tool_calls
        messages.append(assistant_msg)

        if not tool_calls:
            return content

        for tc in tool_calls:
            fname = tc["function"]["name"]
            try:
                args = json.loads(tc["function"]["arguments"])
            except Exception:
                args = {}
            result = tool_executor(fname, args)
            messages.append({"role": "tool", "tool_call_id": tc["id"], "content": str(result)})

    return content or "Iteration limit reached."


# ── Session ────────────────────────────────────────────────────────────────────
def save_session(history: list) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(SESSION_FILE, "w", encoding="utf-8") as f:
        json.dump({"history": history, "saved_at": datetime.now().isoformat()}, f, ensure_ascii=False, indent=2)


def load_session() -> list:
    try:
        with open(SESSION_FILE, encoding="utf-8") as f:
            d = json.load(f)
        h = d.get("history", [])
        t = d.get("saved_at", "")[:16]
        console.print(f"[dim]  Session loaded ({t}), {len(h) // 2} turns.[/dim]")
        return h
    except Exception:
        return []


# ── Slash commands ─────────────────────────────────────────────────────────────
_POSITIVE = re.compile(r"(отлично|правильно|верно|супер|молодец|good|perfect|yes|да|дякую|чудово)", re.I)
_NEGATIVE = re.compile(r"(неверно|ошибка|не то|не так|wrong|bad|нет|ні)", re.I)

import re


def handle_slash(cmd: str, history: list, model: str, brain: Brain, memory: Memory, plan_queue: PlanQueue, cerebro: Cerebro) -> tuple:
    global _mode
    parts = cmd.strip().split(maxsplit=1)
    name = parts[0].lower()
    arg = parts[1] if len(parts) > 1 else ""

    if name == "/help":
        t = Table(show_header=False, box=box.SIMPLE, pad_edge=False)
        t.add_column("cmd", style="bold cyan", no_wrap=True)
        t.add_column("desc", style="white")
        for r in [
            ("/help", "Help"),
            ("/clear", "Clear history"),
            ("/mode [name]", "Mode: auto|code|plan|local|fast"),
            ("/model s|f", "Switch model (smart/fast)"),
            ("/plan <goal>", "Add task to planner"),
            ("/plans", "Show plan queue"),
            ("/memory", "Memory stats"),
            ("/fact k=v", "Remember a fact"),
            ("/cerebro", "Cerebro stats"),
            ("/status", "System status"),
            ("/tokens", "Token stats"),
            ("/ast <file>", "AST check Python file"),
            ("/cwd [path]", "Change/show working directory"),
        ]:
            t.add_row(*r)
        console.print(Panel(t, title="[bold cyan]MiMo TUI — Commands[/bold cyan]", border_style="cyan"))
        return True, history, model

    if name == "/clear":
        console.print("[green]  History cleared.[/green]")
        return True, [], model

    if name == "/mode":
        if not arg:
            t2 = Table(show_header=True, box=box.SIMPLE, pad_edge=False)
            t2.add_column("Mode", style="bold cyan", no_wrap=True)
            t2.add_column("Model", style="dim")
            t2.add_column("Description")
            for k, v in MODES.items():
                marker = " ◀" if k == _mode else ""
                t2.add_row(f"[{v['color']}]{v['label']}[/{v['color']}]{marker}", v["model"], v["desc"])
            console.print(Panel(t2, title="[cyan]MiMo Modes[/cyan]", border_style="cyan"))
        elif arg in MODES:
            _mode = arg
            m = MODES[arg]
            model = m["model"]
            console.print(f"[{m['color']}]  Mode: {m['label']} — {m['desc']}[/{m['color']}]")
        else:
            console.print(f"[red]  Unknown mode. Available: {' | '.join(MODES.keys())}[/red]")
        return True, history, model

    if name == "/model":
        if arg in ("smart", "fast", "s", "f"):
            model = "smart" if arg in ("smart", "s") else "fast"
            console.print(f"[green]  Model: {model}[/green]")
        return True, history, model

    if name == "/plan":
        if not arg:
            console.print("[red]  Usage: /plan <description>[/red]")
        else:
            plan_queue.enqueue(Plan(goal=arg))
            console.print("[green]  Task added to queue.[/green]")
        return True, history, model

    if name == "/plans":
        plans = plan_queue.all()
        if not plans:
            console.print("[dim]  Queue empty.[/dim]")
        else:
            for p in plans[-10:]:
                icon = {"pending": "○", "running": "◎", "done": "●", "failed": "✗"}.get(p.status, "?")
                console.print(f"  {icon} [{p.id}] {p.goal[:60]} [{p.status}]")
        return True, history, model

    if name == "/memory":
        s = memory.stats()
        t2 = Table(show_header=False, box=box.SIMPLE)
        t2.add_column("k", style="cyan")
        t2.add_column("v")
        t2.add_row("Facts", str(s["facts"]))
        t2.add_row("Interactions", str(s["interactions"]))
        t2.add_row("Code snippets", str(s["code"]))
        t2.add_row("DB size", f"{s['db_size_mb']} MB")
        console.print(Panel(t2, title="[cyan]Memory[/cyan]", border_style="cyan"))
        return True, history, model

    if name == "/fact":
        if "=" in arg:
            k, v = arg.split("=", 1)
            memory.facts.set(k.strip(), v.strip(), source="user")
            console.print(f"[green]  Remembered: {k.strip()} = {v.strip()}[/green]")
        return True, history, model

    if name == "/cerebro":
        s = cerebro.get_stats()
        console.print(f"[cyan]  Cerebro: {s['interactions']} learned responses[/cyan]")
        return True, history, model

    if name == "/status":
        from core.tools import system_status
        console.print(f"[dim]  {system_status()}[/dim]")
        return True, history, model

    if name == "/tokens":
        console.print(f"[dim]  {brain.token_line()}[/dim]")
        return True, history, model

    if name == "/ast":
        if not arg:
            console.print("[red]  Usage: /ast <python_file>[/red]")
        else:
            try:
                code = Path(arg).read_text(encoding="utf-8")
                issues = ast_check(code)
                if issues:
                    console.print(f"[yellow]  Issues: {', '.join(issues)}[/yellow]")
                else:
                    console.print("[green]  No issues found.[/green]")
            except Exception as e:
                console.print(f"[red]  ERROR: {e}[/red]")
        return True, history, model

    if name == "/cwd":
        if arg:
            os.chdir(arg)
            console.print(f"[green]  CWD: {os.getcwd()}[/green]")
        else:
            console.print(f"[dim]  {os.getcwd()}[/dim]")
        return True, history, model

    return False, history, model


# ── Banner ─────────────────────────────────────────────────────────────────────
BANNER = r"""
   ███╗   ███╗██╗███████╗███████╗ ██████╗
   ████╗ ████║██║██╔════╝██╔════╝██╔════╝
   ██╔████╔██║██║███████╗█████╗  ██║
   ██║╚██╔╝██║██║╚════██║██╔══╝  ██║
   ██║ ╚═╝ ██║██║███████║███████╗╚██████╗
   ╚═╝     ╚═╝╚═╝╚══════╝╚══════╝ ╚═════╝
"""
AUTHOR = "Nick Antonov · Borodachamba Studio"
VERSION = "v1.0"


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Auth
    console.print("[yellow]  Authenticating...[/yellow]")
    fingerprint = get_fingerprint()
    console.print(f"[dim]  Fingerprint: {fingerprint[:16]}...[/dim]")

    # Init components
    brain = Brain(fingerprint=fingerprint)
    memory = Memory(str(DATA_DIR))
    cerebro = Cerebro(str(DATA_DIR))
    plan_queue = PlanQueue(PLAN_FILE)
    vibe_coder = VibeCoder(brain=brain, memory=memory, run_fn=run_python)
    planner = Planner(brain=brain, tools_schema=TOOLS_SCHEMA, tool_executor=tool_executor)
    plan_runner = PlanRunner(
        queue=plan_queue, planner=planner,
        on_done=lambda p: console.print(f"\n[bold green]  ✓ Plan completed:[/bold green] {p.goal[:60]}")
    )
    plan_runner.start()

    # Banner
    console.print(f"[bold bright_cyan]{BANNER}[/bold bright_cyan]")
    console.print(f"[bold cyan]      MiMo TUI {VERSION} — Autonomous AI Assistant[/bold cyan]")
    console.print(f"[dim]      {AUTHOR}[/dim]")
    console.print("[dim]      Free-tier mode (opencode.ai) — No Bun required[/dim]")
    console.print()

    # Startup
    ollama = brain.ollama_info()
    s = memory.stats()
    console.print(f"  MiMo: [green]connected[/green] │ Ollama: [dim]{ollama}[/dim]")
    console.print(f"  Memory: {s['facts']} facts · {s['interactions']} interactions · {s['db_size_mb']} MB")
    console.print(f"  [dim]/help — commands │ /plan — planner │ exit — quit[/dim]\n")

    # Load session
    history = load_session()
    _last_q = ""

    # Main loop
    while True:
        try:
            m_cfg = MODES.get(_mode, MODES["auto"])
            prompt = f"[{m_cfg['label']}:{model if 'model' in dir() else 'smart'}] > "
            q = input(prompt).strip()
        except (KeyboardInterrupt, EOFError):
            break

        if q.lower() in ("exit", "quit", "выход", "вихід"):
            plan_runner.stop()
            save_session(history)
            memory.close()
            console.print("[bold bright_cyan]  Session saved. Goodbye.[/bold bright_cyan]")
            break

        if not q:
            continue

        # Positive/negative feedback
        if _last_q and _POSITIVE.search(q):
            memory.feedback(_last_q, positive=True)
            console.print("[dim green]  ✓ Marked as correct.[/dim green]")
        elif _last_q and _NEGATIVE.search(q):
            memory.feedback(_last_q, positive=False)
            console.print("[dim yellow]  ✗ Marked as incorrect.[/dim yellow]")

        if q.startswith("/"):
            handled, history, model = handle_slash(q, history, model if 'model' in dir() else "smart", brain, memory, plan_queue, cerebro)
            if handled:
                continue

        console.print()
        console.print(Panel(f"[bold white]{q}[/bold white]", title="[bold cyan]◀  YOU[/bold cyan]", border_style="cyan", padding=(0, 1)))

        answer = run_agent(q, history, brain, memory, model_key=model if 'model' in dir() else "smart")
        console.print(f"[dim]  {brain.token_line()}[/dim]")

        # Learn
        if answer and len(answer) > 60:
            memory.learn(q, answer, quality=0.8)
        cerebro.learn_response(q, answer)

        history.append({"role": "user", "content": q})
        history.append({"role": "assistant", "content": answer})
        if len(history) > 20:
            history = history[-20:]
        _last_q = q

    plan_runner.stop()
    save_session(history)
    memory.close()


if __name__ == "__main__":
    main()
