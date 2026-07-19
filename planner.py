"""
MiMo TUI — Planner
Autonomous task decomposition and execution.
"""

import json
import os
import re
import threading
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Callable, Optional

from rich.console import Console

console = Console()


@dataclass
class SubTask:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:6])
    description: str = ""
    tool_hint: str = ""
    depends_on: list = field(default_factory=list)
    status: str = "pending"
    result: str = ""
    error: str = ""


@dataclass
class Plan:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    goal: str = ""
    subtasks: list = field(default_factory=list)
    status: str = "pending"
    result: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    context: str = ""


def _plan_to_dict(p: Plan) -> dict:
    d = asdict(p)
    d["subtasks"] = [asdict(s) if isinstance(s, SubTask) else s for s in p.subtasks]
    return d


def _plan_from_dict(d: dict) -> Plan:
    subtasks = [SubTask(**s) for s in d.pop("subtasks", [])]
    p = Plan(**d)
    p.subtasks = subtasks
    return p


class Planner:
    PLAN_PROMPT = """You are a task planner. Break down the goal into 2-6 concrete subtasks.

Goal: {goal}
Context: {context}
Available tools: {tool_names}

Respond with ONLY valid JSON (no markdown, no explanation):
{{
  "subtasks": [
    {{
      "description": "what to do",
      "tool_hint": "tool_name or empty string",
      "depends_on": []
    }}
  ]
}}

Rules:
- Use tool_hint = "" for subtasks that are pure LLM reasoning
- Keep descriptions concrete and actionable
- Maximum 6 subtasks
- If goal is simple (1 step), return 1 subtask"""

    SUMMARIZE_PROMPT = """You completed a multi-step task. Write a concise summary for the user.

Goal: {goal}
Results:
{results}

Write a clear, helpful answer. Be concise."""

    def __init__(self, brain, tools_schema: list, tool_executor: Callable[[str, dict], str]):
        self.brain = brain
        self.tools_schema = tools_schema
        self.tool_executor = tool_executor
        self._tool_names = ", ".join(t["function"]["name"] for t in tools_schema) if tools_schema else "none"

    def make_plan(self, goal: str, context: str = "") -> Plan:
        prompt = self.PLAN_PROMPT.format(goal=goal, context=context[:500] if context else "none", tool_names=self._tool_names)
        messages = [{"role": "user", "content": prompt}]
        raw = self.brain.think(messages, model_key="fast")
        subtasks = self._parse_subtasks(raw, goal)
        return Plan(goal=goal, subtasks=subtasks, context=context)

    def _parse_subtasks(self, raw: str, goal: str) -> list:
        try:
            text = raw.strip()
            if text.startswith("```"):
                text = "\n".join(text.split("\n")[1:])
            if text.endswith("```"):
                text = "\n".join(text.split("\n")[:-1])
            data = json.loads(text.strip())
            subtasks = []
            for item in data.get("subtasks", []):
                subtasks.append(SubTask(
                    description=item.get("description", ""),
                    tool_hint=item.get("tool_hint", ""),
                    depends_on=item.get("depends_on", []),
                ))
            return subtasks if subtasks else [SubTask(description=goal)]
        except Exception:
            return [SubTask(description=goal)]

    def execute(self, plan: Plan, history: list | None = None) -> str:
        plan.status = "running"
        completed = {}

        for st in plan.subtasks:
            if any(completed.get(dep) is None for dep in st.depends_on):
                st.status = "skipped"
                continue

            st.status = "running"
            console.print(f"[dim cyan]  ▷ {st.description[:80]}[/dim cyan]")

            try:
                result = self._execute_subtask(st, completed, history or [])
                st.result = result
                st.status = "done"
                completed[st.id] = result
            except Exception as e:
                st.error = str(e)
                st.status = "failed"
                console.print(f"[red]  ✗ {st.description[:60]}: {e}[/red]")

        plan.status = "done" if all(s.status in ("done", "skipped") for s in plan.subtasks) else "failed"
        plan.result = self._summarize(plan)
        return plan.result

    def _execute_subtask(self, st, completed, history) -> str:
        context_parts = [f"Current task: {st.description}"]
        if completed:
            prev = "\n".join(f"- {v[:200]}" for v in list(completed.values())[-3:])
            context_parts.append(f"Previous results:\n{prev}")
        context = "\n".join(context_parts)

        if st.tool_hint and st.tool_hint in self._tool_names:
            arg_prompt = f"Call tool '{st.tool_hint}' to accomplish:\n{st.description}\nContext: {context}\n\nRespond with ONLY the JSON arguments dict."
            raw_args = self.brain.think([{"role": "user", "content": arg_prompt}], model_key="fast")
            try:
                text = raw_args.strip()
                if text.startswith("```"):
                    text = "\n".join(text.split("\n")[1:])
                if text.endswith("```"):
                    text = "\n".join(text.split("\n")[:-1])
                args = json.loads(text.strip())
            except Exception:
                args = {}
            return self.tool_executor(st.tool_hint, args)
        else:
            messages = history[-6:] + [{"role": "user", "content": context}]
            for _ in range(4):
                content, tool_calls, finish = self.brain.stream(messages, tools=self.tools_schema, model_key="fast")
                messages.append({"role": "assistant", "content": content, **({"tool_calls": tool_calls} if tool_calls else {})})
                if not tool_calls:
                    return content
                for tc in tool_calls:
                    fname = tc["function"]["name"]
                    try:
                        args = json.loads(tc["function"]["arguments"])
                    except Exception:
                        args = {}
                    result = self.tool_executor(fname, args)
                    messages.append({"role": "tool", "tool_call_id": tc["id"], "content": str(result)})
            return content or ""

    def _summarize(self, plan: Plan) -> str:
        results_text = "\n".join(f"[{st.status}] {st.description}: {st.result[:300]}" for st in plan.subtasks)
        prompt = self.SUMMARIZE_PROMPT.format(goal=plan.goal, results=results_text)
        return self.brain.think([{"role": "user", "content": prompt}], model_key="fast")


class PlanQueue:
    def __init__(self, path: str):
        self.path = path
        self._lock = threading.Lock()
        self._data: list[Plan] = []
        self._load()

    def _load(self) -> None:
        try:
            with open(self.path, encoding="utf-8") as f:
                self._data = [_plan_from_dict(d) for d in json.load(f)]
        except Exception:
            self._data = []

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump([_plan_to_dict(p) for p in self._data], f, ensure_ascii=False, indent=2)

    def enqueue(self, plan: Plan) -> None:
        with self._lock:
            self._data.append(plan)
            self._save()

    def next_pending(self) -> Optional[Plan]:
        with self._lock:
            for p in self._data:
                if p.status == "pending":
                    return p
            return None

    def update(self, plan: Plan) -> None:
        with self._lock:
            for i, p in enumerate(self._data):
                if p.id == plan.id:
                    self._data[i] = plan
                    break
            self._save()

    def all(self) -> list:
        return list(self._data)


class PlanRunner(threading.Thread):
    def __init__(self, queue: PlanQueue, planner: Planner, on_done: Callable[[Plan], None] | None = None, interval: float = 5.0):
        super().__init__(daemon=True, name="PlanRunner")
        self.queue = queue
        self.planner = planner
        self.on_done = on_done
        self.interval = interval
        self._stop = threading.Event()

    def run(self) -> None:
        while not self._stop.is_set():
            plan = self.queue.next_pending()
            if plan:
                try:
                    self.planner.execute(plan)
                    self.queue.update(plan)
                    if self.on_done:
                        self.on_done(plan)
                except Exception as e:
                    plan.status = "failed"
                    plan.result = str(e)
                    self.queue.update(plan)
            self._stop.wait(self.interval)

    def stop(self) -> None:
        self._stop.set()
