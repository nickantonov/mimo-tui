"""
MiMo TUI — Brain
LLM engine: MiMo free-tier (opencode.ai) + Ollama local fallback.
Streaming, tool calling, model cascade, token tracking.

Based on JARVIS core/brain.py, adapted for MiMo API.
"""

import json
import re
import time
import urllib.request as _urlreq
from rich.console import Console
from rich.live import Live
from rich.panel import Panel

console = Console()

# ── MiMo free-tier config ─────────────────────────────────────────────────────
MIMO_API_URL = "https://opencode.ai/zen/v1/chat/completions"
MIMO_MODELS = {
    "smart": "mimo-auto",
    "fast": "hy3-free",
    "free": "mimo-v2.5-free",
}

# Ollama fallback
OLLAMA_PRIORITY = [
    "qwen2.5:72b", "qwen2.5:32b", "qwen2.5:14b", "qwen2.5:7b",
    "llama3.3:70b", "llama3.1:70b", "llama3.1:8b", "llama3.2:3b",
    "mistral:7b", "mistral:latest",
    "qwen2.5:3b", "qwen2.5:1.5b", "qwen2.5:0.5b",
]
OLLAMA_TOOLS_CAPABLE = {"qwen2.5", "llama3.1", "llama3.3", "mistral"}
OLLAMA_CHAT_URL = "http://localhost:11434/api/chat"
OLLAMA_TAGS_URL = "http://localhost:11434/api/tags"


class Brain:
    """
    Unified LLM interface.
    
    Usage:
        brain = Brain(fingerprint="abc123")
        content, tool_calls, finish = brain.stream(messages, tools=TOOLS_SCHEMA)
    """

    def __init__(self, fingerprint: str, default_model: str = "smart"):
        self.fingerprint = fingerprint
        self.default_model = default_model
        self.tokens = {"prompt": 0, "completion": 0, "total": 0, "calls": 0}

        self.ollama_model: str = "qwen2.5:0.5b"
        self.ollama_tools_ok: bool = False
        self._detect_ollama()

    # ── Ollama detection ───────────────────────────────────────────────────────
    def _detect_ollama(self) -> None:
        try:
            with _urlreq.urlopen(OLLAMA_TAGS_URL, timeout=5) as r:
                data = json.loads(r.read().decode())
            installed = [m["name"] for m in data.get("models", [])]
            for candidate in OLLAMA_PRIORITY:
                base = candidate.split(":")[0]
                tag = candidate.split(":")[1] if ":" in candidate else ""
                for m in installed:
                    if (tag and m == candidate) or (tag and m.startswith(base + ":" + tag)):
                        self.ollama_model = m
                        self.ollama_tools_ok = base in OLLAMA_TOOLS_CAPABLE
                        return
            for candidate in OLLAMA_PRIORITY:
                base = candidate.split(":")[0]
                for m in installed:
                    if m.startswith(base + ":"):
                        self.ollama_model = m
                        self.ollama_tools_ok = base in OLLAMA_TOOLS_CAPABLE
                        return
        except Exception:
            pass

    def ollama_info(self) -> str:
        cap = "tools ✓" if self.ollama_tools_ok else "no tools"
        return f"{self.ollama_model} ({cap})"

    # ── MiMo API call ──────────────────────────────────────────────────────────
    def _mimo_stream(
        self,
        messages: list,
        model_name: str,
        tools: list | None,
        panel_fn,
    ) -> tuple:
        """Stream from MiMo free-tier via opencode.ai."""
        collected, raw_tc, finish, live_ctx = "", {}, "stop", None

        payload = {
            "model": model_name,
            "messages": messages,
            "stream": True,
            "key": self.fingerprint,
        }
        if tools:
            payload["tools"] = tools

        data = json.dumps(payload).encode()
        req = _urlreq.Request(
            MIMO_API_URL,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with _urlreq.urlopen(req, timeout=120) as resp:
                for raw_line in resp:
                    line = raw_line.strip()
                    if not line:
                        continue
                    if line.startswith(b":"):
                        continue
                    if line.startswith(b"data: "):
                        line = line[6:]
                    if line == b"[DONE]":
                        break
                    try:
                        chunk = json.loads(line.decode("utf-8"))
                    except json.JSONDecodeError:
                        continue

                    if "usage" in chunk and chunk["usage"]:
                        u = chunk["usage"]
                        self.tokens["prompt"] += u.get("prompt_tokens", 0)
                        self.tokens["completion"] += u.get("completion_tokens", 0)
                        self.tokens["total"] += u.get("total_tokens", 0)
                        self.tokens["calls"] += 1

                    if not chunk.get("choices"):
                        continue
                    choice = chunk["choices"][0]
                    if choice.get("finish_reason"):
                        finish = choice["finish_reason"]
                    delta = choice.get("delta", {})
                    if delta.get("content"):
                        if live_ctx is None:
                            live_ctx = Live(
                                panel_fn(""),
                                console=console,
                                refresh_per_second=20,
                                transient=False,
                            )
                            live_ctx.start()
                        collected += delta["content"]
                        live_ctx.update(panel_fn(collected))
                    if tools and delta.get("tool_calls"):
                        for tc in delta["tool_calls"]:
                            idx = tc.get("index", 0)
                            if idx not in raw_tc:
                                raw_tc[idx] = {
                                    "id": "",
                                    "type": "function",
                                    "function": {"name": "", "arguments": ""},
                                }
                            if tc.get("id"):
                                raw_tc[idx]["id"] += tc["id"]
                            fn = tc.get("function", {})
                            if fn.get("name"):
                                raw_tc[idx]["function"]["name"] += fn["name"]
                            if fn.get("arguments"):
                                raw_tc[idx]["function"]["arguments"] += fn["arguments"]
        finally:
            if live_ctx:
                live_ctx.stop()

        tool_calls = [raw_tc[k] for k in sorted(raw_tc.keys())]
        return collected, tool_calls, finish

    # ── Ollama stream ──────────────────────────────────────────────────────────
    def _ollama_stream(
        self,
        messages: list,
        tools: list | None,
        panel_fn,
    ) -> tuple:
        """Stream from Ollama."""
        payload = {"model": self.ollama_model, "messages": messages, "stream": True}
        if tools and self.ollama_tools_ok:
            payload["tools"] = tools

        data = json.dumps(payload).encode()
        req = _urlreq.Request(
            OLLAMA_CHAT_URL,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        collected, raw_tc, live_ctx = "", [], None
        with _urlreq.urlopen(req, timeout=120) as resp:
            for raw_line in resp:
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    chunk = json.loads(line.decode("utf-8"))
                except json.JSONDecodeError:
                    continue
                msg = chunk.get("message", {})
                delta = msg.get("content", "")
                if delta:
                    if live_ctx is None:
                        live_ctx = Live(
                            panel_fn(""),
                            console=console,
                            refresh_per_second=20,
                            transient=False,
                        )
                        live_ctx.start()
                    collected += delta
                    live_ctx.update(panel_fn(collected))
                if chunk.get("done"):
                    raw_tc = msg.get("tool_calls", [])
                    break

        if live_ctx:
            live_ctx.stop()

        tool_calls = []
        for i, tc in enumerate(raw_tc):
            fn = tc.get("function", {})
            args = fn.get("arguments", {})
            tool_calls.append({
                "id": f"olm_{i}",
                "type": "function",
                "function": {
                    "name": fn.get("name", ""),
                    "arguments": json.dumps(args) if isinstance(args, dict) else str(args),
                },
            })
        return collected, tool_calls, ("tool_calls" if tool_calls else "stop")

    # ── Public: stream ─────────────────────────────────────────────────────────
    def stream(
        self,
        messages: list,
        tools: list | None = None,
        model_key: str | None = None,
        panel_fn=None,
    ) -> tuple:
        """
        Stream a response. Cascade: MiMo → Ollama.
        Returns (content, tool_calls, finish_reason).
        """
        if panel_fn is None:
            panel_fn = lambda t: Panel(
                t or "[dim]...[/dim]",
                title="[bold bright_cyan]▶  MiMo[/bold bright_cyan]",
                border_style="bright_cyan",
                padding=(0, 1),
            )

        active_model = MIMO_MODELS.get(model_key or self.default_model, MIMO_MODELS["smart"])

        for attempt in range(3):
            try:
                content, tcs, finish = self._mimo_stream(
                    messages, active_model, tools, panel_fn
                )
                return content, tcs, finish
            except Exception as e:
                err = str(e).lower()
                if "rate_limit" in err or "429" in err:
                    if active_model != MIMO_MODELS["fast"]:
                        console.print(f"[yellow]  ⚠ Rate limit → fast model[/yellow]")
                        active_model = MIMO_MODELS["fast"]
                        continue
                    break
                console.print(f"[dim yellow]  ⚠ {type(e).__name__}: {e}[/dim yellow]")
                break

        # Ollama fallback
        cap = "tools ✓" if self.ollama_tools_ok else "no tools"
        console.print(f"[bold yellow]  ↪ Ollama ({self.ollama_model}, {cap})...[/bold yellow]")
        try:
            content, tcs, _ = self._ollama_stream(messages, tools, panel_fn)
            return content, tcs, "ollama"
        except Exception as e:
            console.print(f"[red]  ✗ Ollama: {e}[/red]")
            return "", [], "error"

    # ── Public: think (non-streaming) ──────────────────────────────────────────
    def think(
        self,
        messages: list,
        tools: list | None = None,
        model_key: str = "fast",
    ) -> str:
        """Non-streaming call for internal reasoning."""
        model_name = MIMO_MODELS.get(model_key, MIMO_MODELS["fast"])
        payload = {
            "model": model_name,
            "messages": messages,
            "stream": False,
            "key": self.fingerprint,
        }
        if tools:
            payload["tools"] = tools

        data = json.dumps(payload).encode()
        req = _urlreq.Request(
            MIMO_API_URL,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with _urlreq.urlopen(req, timeout=60) as resp:
                result = json.loads(resp.read().decode())
            if "usage" in result and result["usage"]:
                u = result["usage"]
                self.tokens["prompt"] += u.get("prompt_tokens", 0)
                self.tokens["completion"] += u.get("completion_tokens", 0)
                self.tokens["total"] += u.get("total_tokens", 0)
                self.tokens["calls"] += 1
            return result.get("choices", [{}])[0].get("message", {}).get("content", "")
        except Exception as e:
            console.print(f"[red]  ✗ think(): {e}[/red]")
            return ""

    # ── Token stats ────────────────────────────────────────────────────────────
    def token_line(self) -> str:
        t = self.tokens
        return (
            f"tokens: {t['total']:,} ({t['prompt']:,}p + {t['completion']:,}c) "
            f"│ calls: {t['calls']}"
        )

    def reset_tokens(self) -> None:
        self.tokens = {"prompt": 0, "completion": 0, "total": 0, "calls": 0}
