"""Deterministic, stream-separated RNG for reproducible simulations.

Python's built-in hash() is salted per process, so all seeding goes through a
stable SHA-256 derivation. Each subsystem uses a named stream: consuming more
randomness in dialogue can never shift schedule or economy outcomes.
"""

from __future__ import annotations

import hashlib
import random
from collections.abc import Iterable


def stable_hash(*parts: object) -> int:
    payload = "\u241f".join(str(p) for p in parts).encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")


class RngHub:
    """Holds one root seed and hands out deterministic named streams."""

    def __init__(self, seed: int):
        self.seed = int(seed)
        self._streams: dict[str, random.Random] = {}
        self._counters: dict[str, int] = {}

    def stream(self, name: str) -> random.Random:
        rng = self._streams.get(name)
        if rng is None:
            rng = random.Random(stable_hash(self.seed, name))
            self._streams[name] = rng
        return rng

    def fork(self, name: str) -> random.Random:
        """A fresh sub-stream that is independent of call order within `name`."""
        idx = self._counters.get(name, 0)
        self._counters[name] = idx + 1
        return random.Random(stable_hash(self.seed, name, idx))

    def pick(self, stream: str, items: Iterable):
        seq = list(items)
        if not seq:
            return None
        return seq[self.stream(stream).randrange(len(seq))]

    def chance(self, stream: str, p: float) -> bool:
        return self.stream(stream).random() < p

    def jitter(self, stream: str, low: float, high: float) -> float:
        return self.stream(stream).uniform(low, high)


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def weighted_pick(rng: random.Random, items: list, weights: list[float]):
    total = sum(weights)
    if total <= 0:
        return items[0] if items else None
    roll = rng.random() * total
    upto = 0.0
    for item, weight in zip(items, weights, strict=False):
        upto += weight
        if roll <= upto:
            return item
    return items[-1]
