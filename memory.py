"""
MiMo TUI — Memory (SQLite)
Knowledge graph, interactions, code library.
"""

import json
import math
import os
import re
import sqlite3
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

# ── Similarity helpers ─────────────────────────────────────────────────────────
_STOP = {
    "и", "в", "на", "с", "по", "за", "для", "не", "это", "то", "а", "но", "как", "из", "у",
    "о", "об", "к", "что", "все", "так", "же", "от", "до", "при", "под",
    "the", "a", "an", "is", "it", "in", "of", "to", "and", "or", "for", "with", "that",
    "this", "be", "are", "was", "were", "has", "have", "do", "does", "did",
}


def _tokens(text: str) -> set:
    words = re.findall(r"[a-zA-Zа-яёА-ЯЁ0-9_]+", text.lower())
    return {w for w in words if w not in _STOP and len(w) > 2}


def _jaccard(a: set, b: set) -> float:
    return len(a & b) / len(a | b) if a and b else 0.0


def _sim(a: str, b: str) -> float:
    return _jaccard(_tokens(a), _tokens(b))


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


# ── KnowledgeGraph (SQLite) ────────────────────────────────────────────────────
class KnowledgeGraph:
    SCHEMA = """
    CREATE TABLE IF NOT EXISTS facts (
        id TEXT PRIMARY KEY, key TEXT, content TEXT NOT NULL,
        source TEXT DEFAULT 'conversation', topics TEXT DEFAULT '[]',
        confidence REAL DEFAULT 1.0, created_at TEXT,
        last_accessed TEXT, access_count INTEGER DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS interactions (
        id TEXT PRIMARY KEY, query TEXT NOT NULL, response TEXT NOT NULL,
        quality REAL DEFAULT 1.0, tags TEXT DEFAULT '[]', created_at TEXT
    );
    CREATE TABLE IF NOT EXISTS code_library (
        id TEXT PRIMARY KEY, purpose TEXT NOT NULL, code TEXT NOT NULL,
        language TEXT DEFAULT 'python', success_count INTEGER DEFAULT 1,
        created_at TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_facts_key ON facts(key);
    CREATE INDEX IF NOT EXISTS idx_facts_access ON facts(access_count);
    CREATE INDEX IF NOT EXISTS idx_inter_date ON interactions(created_at);
    CREATE INDEX IF NOT EXISTS idx_code_lang ON code_library(language);
    """

    def __init__(self, db_path: str):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(self.SCHEMA)
        self._conn.commit()

    def _exec(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        with self._lock:
            cur = self._conn.execute(sql, params)
            self._conn.commit()
            return cur

    def _fetch(self, sql: str, params: tuple = ()) -> list:
        with self._lock:
            return [dict(r) for r in self._conn.execute(sql, params).fetchall()]

    def _fetchone(self, sql: str, params: tuple = ()) -> Optional[dict]:
        with self._lock:
            row = self._conn.execute(sql, params).fetchone()
            return dict(row) if row else None

    # ── Facts ──────────────────────────────────────────────────────────────────
    def fact_set(self, key: str, value: str, confidence: float = 1.0, source: str = "user") -> str:
        key = key.lower().strip()
        existing = self._fetchone("SELECT id FROM facts WHERE key = ?", (key,))
        fid = existing["id"] if existing else uuid.uuid4().hex[:12]
        now = _now()
        with self._lock:
            self._conn.execute("""
                INSERT INTO facts (id, key, content, source, confidence, created_at, last_accessed, access_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, 0)
                ON CONFLICT(id) DO UPDATE SET content=excluded.content, confidence=excluded.confidence, last_accessed=excluded.last_accessed
            """, (fid, key, value, source, confidence, now, now))
            self._conn.commit()
        return fid

    def fact_get(self, key: str) -> Optional[str]:
        row = self._fetchone("SELECT content FROM facts WHERE key = ?", (key.lower().strip(),))
        return row["content"] if row else None

    def fact_search(self, query: str, top_k: int = 5) -> list:
        rows = self._fetch("SELECT id, key, content, confidence, access_count FROM facts ORDER BY access_count DESC LIMIT 300")
        q_tok = _tokens(query)
        scored = []
        for r in rows:
            score = _jaccard(q_tok, _tokens((r["key"] or "") + " " + r["content"]))
            score *= r["confidence"] * math.log1p(1 + r["access_count"])
            if score > 0:
                scored.append((score, r))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [r for _, r in scored[:top_k]]

    def fact_all(self) -> list:
        return self._fetch("SELECT * FROM facts ORDER BY access_count DESC LIMIT 100")

    def fact_count(self) -> int:
        r = self._fetchone("SELECT COUNT(*) AS n FROM facts")
        return r["n"] if r else 0

    # ── Interactions ───────────────────────────────────────────────────────────
    def interaction_store(self, query: str, response: str, quality: float = 1.0, tags: list = None) -> str:
        iid = uuid.uuid4().hex[:12]
        self._exec(
            "INSERT INTO interactions (id, query, response, quality, tags, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (iid, query, response, max(0.1, min(2.0, quality)), json.dumps(tags or []), _now()),
        )
        return iid

    def interaction_recall(self, query: str, top_k: int = 3) -> list:
        rows = self._fetch("SELECT id, query, response, quality, tags FROM interactions ORDER BY created_at DESC LIMIT 500")
        q_tok = _tokens(query)
        scored = []
        for r in rows:
            score = _jaccard(q_tok, _tokens(r["query"])) * r["quality"]
            if score > 0.05:
                scored.append((score, r))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [r for _, r in scored[:top_k]]

    def interaction_boost(self, query: str, delta: float) -> None:
        matches = self.interaction_recall(query, top_k=1)
        if matches:
            m = matches[0]
            new = max(0.1, min(2.0, m["quality"] + delta))
            self._exec("UPDATE interactions SET quality = ? WHERE id = ?", (new, m["id"]))

    def interaction_count(self) -> int:
        r = self._fetchone("SELECT COUNT(*) AS n FROM interactions")
        return r["n"] if r else 0

    # ── Code library ───────────────────────────────────────────────────────────
    def code_save(self, purpose: str, code: str, language: str = "python") -> str:
        rows = self._fetch("SELECT id, purpose, success_count FROM code_library LIMIT 300")
        for e in rows:
            if _sim(purpose, e["purpose"]) > 0.7:
                self._exec("UPDATE code_library SET code=?, success_count=success_count+1 WHERE id=?", (code, e["id"]))
                return e["id"]
        cid = uuid.uuid4().hex[:12]
        self._exec(
            "INSERT INTO code_library (id, purpose, code, language, success_count, created_at) VALUES (?, ?, ?, ?, 1, ?)",
            (cid, purpose, code, language, _now()),
        )
        return cid

    def code_find(self, purpose: str, top_k: int = 3) -> list:
        rows = self._fetch("SELECT * FROM code_library ORDER BY success_count DESC LIMIT 200")
        scored = []
        for r in rows:
            score = _sim(purpose, r["purpose"]) * math.log1p(r["success_count"])
            if score > 0.05:
                scored.append((score, r))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [r for _, r in scored[:top_k]]

    def code_count(self) -> int:
        r = self._fetchone("SELECT COUNT(*) AS n FROM code_library")
        return r["n"] if r else 0

    # ── Stats ──────────────────────────────────────────────────────────────────
    def stats(self) -> dict:
        size = (Path(self.db_path).stat().st_size / 1024 / 1024 if Path(self.db_path).exists() else 0)
        return {
            "facts": self.fact_count(),
            "interactions": self.interaction_count(),
            "code": self.code_count(),
            "db_size_mb": round(size, 2),
        }

    def close(self) -> None:
        try:
            self._conn.close()
        except Exception:
            pass


# ── Facades ────────────────────────────────────────────────────────────────────
class _FactRow:
    __slots__ = ("key", "value", "confidence", "source")

    def __init__(self, r: dict):
        self.key = r.get("key", "")
        self.value = r.get("content", "")
        self.confidence = r.get("confidence", 1.0)
        self.source = r.get("source", "")


class FactStore:
    def __init__(self, kg: KnowledgeGraph):
        self._kg = kg

    def set(self, key: str, value: str, confidence: float = 1.0, source: str = "") -> None:
        self._kg.fact_set(key, value, confidence, source)

    def get(self, key: str) -> Optional[str]:
        return self._kg.fact_get(key)

    def search(self, query: str, top_k: int = 5) -> list:
        return [_FactRow(r) for r in self._kg.fact_search(query, top_k)]

    def all(self) -> list:
        return [_FactRow(r) for r in self._kg.fact_all()]


class _InteractionRow:
    __slots__ = ("query", "response", "quality", "tags")

    def __init__(self, r: dict):
        self.query = r.get("query", "")
        self.response = r.get("response", "")
        self.quality = r.get("quality", 1.0)
        raw = r.get("tags", "[]")
        self.tags = json.loads(raw) if isinstance(raw, str) else (raw or [])


class InteractionMemory:
    def __init__(self, kg: KnowledgeGraph):
        self._kg = kg

    def store(self, query: str, response: str, quality: float = 1.0, tags: list | None = None) -> None:
        self._kg.interaction_store(query, response, quality, tags)

    def recall(self, query: str, top_k: int = 3) -> list:
        return [_InteractionRow(r) for r in self._kg.interaction_recall(query, top_k)]

    def boost(self, query: str, delta: float = 0.2) -> None:
        self._kg.interaction_boost(query, delta)


class _CodeRow:
    __slots__ = ("purpose", "code", "language", "success_count")

    def __init__(self, r: dict):
        self.purpose = r.get("purpose", "")
        self.code = r.get("code", "")
        self.language = r.get("language", "python")
        self.success_count = r.get("success_count", 1)


class CodeLibrary:
    def __init__(self, kg: KnowledgeGraph):
        self._kg = kg

    def save(self, purpose: str, code: str, language: str = "python") -> None:
        self._kg.code_save(purpose, code, language)

    def find(self, purpose: str, top_k: int = 3) -> list:
        return [_CodeRow(r) for r in self._kg.code_find(purpose, top_k)]


# ── Memory facade ──────────────────────────────────────────────────────────────
class Memory:
    def __init__(self, data_dir: str):
        Path(data_dir).mkdir(parents=True, exist_ok=True)
        db_path = os.path.join(data_dir, "knowledge.db")
        self._kg = KnowledgeGraph(db_path)
        self.facts = FactStore(self._kg)
        self.interactions = InteractionMemory(self._kg)
        self.code = CodeLibrary(self._kg)

    def context_for(self, query: str, max_facts: int = 5, max_interactions: int = 2) -> str:
        parts = []
        facts = self.facts.search(query, top_k=max_facts)
        if facts:
            parts.append("## Facts:\n" + "\n".join(f"  {f.key}: {f.value}" for f in facts))
        past = self.interactions.recall(query, top_k=max_interactions)
        if past:
            parts.append("## Similar past tasks:\n" + "\n".join(
                f"  Q: {ix.query[:80]}\n  A: {ix.response[:150]}…" for ix in past
            ))
        snippets = self.code.find(query, top_k=1)
        if snippets:
            s = snippets[0]
            parts.append(f"## Ready code ({s.purpose[:60]}):\n```{s.language}\n{s.code[:400]}\n```")
        return "\n\n".join(parts)

    def learn(self, query: str, response: str, quality: float = 0.8, tags: list | None = None) -> None:
        if len(response) > 30:
            self.interactions.store(query, response, quality=quality, tags=tags)

    def feedback(self, query: str, positive: bool) -> None:
        self.interactions.boost(query, 0.2 if positive else -0.2)

    def stats(self) -> dict:
        return self._kg.stats()

    def close(self) -> None:
        self._kg.close()
