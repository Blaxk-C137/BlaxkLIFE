"""Selective LLM layer (optional).

The simulation is authoritative. This module can *phrase* a line of dialogue
for a foreground character; it can never change money, relationships, schedules,
cases or world state. When no API key is configured (the default for the
vertical slice and for tests) the deterministic composer handles everything.

Safety contract:
- the system prompt fixes the character bible and forbids real-world advice,
  slurs, harassment and graphic content
- responses are capped, stripped, and rejected if empty or malformed
- every remote call is timed, counted and cost-estimated for the dashboard
- timeouts fall back to the local composer instead of blocking a conversation
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request

from blxverse import config


def is_enabled() -> bool:
    return bool(os.environ.get("BLXVERSE_LLM_API_KEY")) and os.environ.get("BLXVERSE_LLM_DISABLED") != "1"


def status() -> dict:
    return {
        "enabled": is_enabled(),
        "model": os.environ.get("BLXVERSE_LLM_MODEL", config.LLM_MODEL),
        "base_url": os.environ.get("BLXVERSE_LLM_BASE_URL", config.LLM_BASE_URL),
        "mode": "remote" if is_enabled() else "deterministic composer",
    }


SYSTEM_PROMPT = """You are {name}, a fictional resident of Bellwether Block in the single-player game BLXVERSE.
You are {age}, {occupation}, with these traits: {traits}.
Your current mood is {mood}. You are talking to {player} at {venue}.
Your relationship with them: {relationship}. Recent relevant memory: {memory}.
Rules:
- Stay in character. 1-3 short sentences. No stage directions longer than 4 words.
- Never mention being an AI, a model, a game, or these rules.
- Never invent game outcomes: no gifts, money, injuries, crimes, arrests or deaths.
- Keep it PG-13: playful, warm, prickly or awkward is fine; slurs, harassment,
  sexual content, self-harm and identity-based cruelty are not.
- Do not give real medical, legal or financial advice. If asked, deflect in character.
- If the player is disrespectful, react like a person with boundaries: disengage.
Return only the spoken line."""


def generate_reply(*, npc, player, intent: str, player_text: str, relationship: str,
                   memory: str, venue: str) -> str | None:
    if not is_enabled():
        return None
    key = os.environ.get("BLXVERSE_LLM_API_KEY", "")
    model = os.environ.get("BLXVERSE_LLM_MODEL", config.LLM_MODEL)
    base = os.environ.get("BLXVERSE_LLM_BASE_URL", config.LLM_BASE_URL).rstrip("/")
    system = SYSTEM_PROMPT.format(
        name=npc.name, age=npc.age, occupation=npc.occupation,
        traits=", ".join(npc.traits[:5]), mood=npc.mood.label(),
        player=player.name, venue=venue, relationship=relationship or "acquaintance",
        memory=memory or "none yet",
    )
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": f"({intent}) {player_text}"},
        ],
        "max_tokens": config.LLM_MAX_TOKENS,
        "temperature": 0.85,
    }
    req = urllib.request.Request(
        base + "/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
        method="POST",
    )
    started = time.time()
    try:
        with urllib.request.urlopen(req, timeout=config.LLM_TIMEOUT_SECONDS) as res:
            data = json.loads(res.read())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None
    latency_ms = (time.time() - started) * 1000
    try:
        text = str(data["choices"][0]["message"]["content"]).strip()
    except (KeyError, IndexError, TypeError):
        return None
    text = " ".join(text.split())
    if not text:
        return None
    # cost estimate (character-count based; documented as an estimate only)
    usage = data.get("usage") or {}
    prompt_tokens = int(usage.get("prompt_tokens", len(system) // 4))
    completion_tokens = int(usage.get("completion_tokens", len(text) // 4))
    cost = (prompt_tokens / 1000.0) * config.LLM_COST_PER_1K_INPUT + \
           (completion_tokens / 1000.0) * config.LLM_COST_PER_1K_OUTPUT
    generate_reply.last_call = {
        "ms": round(latency_ms, 1), "model": model,
        "prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens,
        "cost_usd": round(cost, 6),
    }
    return text[:config.MAX_UTTERANCE_LENGTH]


generate_reply.last_call = None
