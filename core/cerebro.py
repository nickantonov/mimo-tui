"""
MiMo TUI — Cerebro
Personality and learning system.
"""

import json
import random
from pathlib import Path


class Cerebro:
    def __init__(self, data_dir: str):
        self.path = Path(data_dir) / "cerebro"
        self.path.mkdir(parents=True, exist_ok=True)

        self.personality = {
            "name": "MiMo",
            "character": "helpful, smart, direct",
            "tone": "professional but friendly",
            "version": "1.0",
            "creator": "Borodachamba Studio",
        }

        self.response_templates = {
            "greeting": ["Hello! How can I help?", "Hey! What's up?", "Ready to work!"],
            "goodbye": ["See you!", "Goodbye!", "Until next time!"],
            "thanks": ["You're welcome!", "No problem!", "Happy to help!"],
        }

        self.learned_responses = {}
        self._load()

    def _load(self):
        f = self.path / "personality.json"
        if f.exists():
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                self.personality = data.get("personality", self.personality)
                self.learned_responses = data.get("learned_responses", {})
            except Exception:
                pass

    def _save(self):
        f = self.path / "personality.json"
        data = {
            "personality": self.personality,
            "learned_responses": self.learned_responses,
        }
        f.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def get_greeting(self) -> str:
        return random.choice(self.response_templates.get("greeting", ["Hello!"]))

    def get_response(self, query: str) -> str | None:
        q = query.lower()[:30]
        return self.learned_responses.get(q)

    def learn_response(self, query: str, response: str):
        key = query.lower()[:30]
        self.learned_responses[key] = response
        if len(self.learned_responses) > 100:
            self.learned_responses = dict(list(self.learned_responses.items())[-50:])
        self._save()

    def get_system_prompt(self) -> str:
        return (
            f"You are {self.personality['name']}, a {self.personality['character']} AI assistant. "
            f"Your tone: {self.personality['tone']}. "
            "You work locally on the user's computer. "
            "Be helpful, concise, and direct."
        )

    def get_stats(self) -> dict:
        return {"interactions": len(self.learned_responses)}
