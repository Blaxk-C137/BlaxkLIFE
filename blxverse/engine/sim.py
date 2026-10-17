"""BLXVERSE deterministic world simulation.

Server-authoritative. Dialogue proposes; this engine validates and applies.

Simulation clock
----------------
`minute` is absolute game minutes since Monday 00:00. `minute` starts at 450
(Monday 07:30). One real second = one game minute at speed 1x. `advance()`
accepts arbitrary game-minute deltas and processes in small deterministic
steps, which makes time-skips (sleep, work, dates) and tests reproducible.

Persistence
-----------
The whole canonical state serialises to a versioned JSON save. Saves are
atomic (temp file + rename) with one rolling backup.
"""

from __future__ import annotations

import heapq
import json
import math
import os
import random
import time
from typing import Any

from blxverse import config
from blxverse.content import events as event_calendar
from blxverse.content.dialogue_content import ARCHETYPES
from blxverse.content.feed_content import (
    ARCHETYPE_POSTS,
    COMMENT_TEMPLATES,
    MESSAGE_TEMPLATES,
    MISSED_CALL_LINES,
    POST_BY_LOCATION,
    POST_TEMPLATES,
)
from blxverse.content.items import CONSUMABLES_LIST, ITEM_BY_ID, ITEMS
from blxverse.content.locations import HOMES, LOCATION_BY_ID, LOCATIONS
from blxverse.engine import chaos, director, economy
from blxverse.engine.economy import EconomyError
from blxverse.engine.models import (
    NPC,
    Arc,
    Belief,
    Case,
    Comment,
    Memory,
    Message,
    Player,
    Post,
    Relationship,
    Rivalry,
    Thread,
    new_id,
)
from blxverse.engine.rng import RngHub, clamp, stable_hash

WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
WEATHERS = ["clear skies", "light clouds", "warm breeze", "drizzle", "golden haze", "cool evening"]


def clock_label_for(minute: float) -> str:
    """Format an absolute game minute as 'Wed 14:20'."""
    day = int(minute // 1440)
    rest = minute - day * 1440
    h = int(rest // 60)
    m = int(rest % 60)
    return f"{WEEKDAYS[day % 7]} {h:02d}:{m:02d}"


class SimError(Exception):
    """Domain error returned to the client as a structured failure."""

    def __init__(self, message: str, code: str = "bad_request", status: int = 400):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status = status


def _rects() -> list[tuple[float, float, float, float]]:
    out = [(loc["x"], loc["y"], loc["w"], loc["h"]) for loc in LOCATIONS]
    for hx, hy, _ in HOMES:
        out.append((hx, hy, 92, 74))
    return out


BUILDING_RECTS = _rects()


def _circle_hits_rect(x: float, y: float, r: float, rect: tuple[float, float, float, float]) -> bool:
    rx, ry, rw, rh = rect
    closest_x = min(max(x, rx), rx + rw)
    closest_y = min(max(y, ry), ry + rh)
    return (x - closest_x) ** 2 + (y - closest_y) ** 2 < r * r


def walkable(x: float, y: float, r: float = config.PLAYER_RADIUS) -> bool:
    if not (30 <= x <= config.WORLD_WIDTH - 30 and 60 <= y <= config.WORLD_HEIGHT - 30):
        return False
    return not any(_circle_hits_rect(x, y, r, rect) for rect in BUILDING_RECTS)


def nearest_walkable(x: float, y: float) -> tuple[float, float]:
    """Closest point a body of PLAYER_RADIUS can actually stand on.

    The old version pushed straight down from the nearest building edge and
    never checked the result, so a spot between two buildings could resolve to
    a point *inside* the second one — the player then walked at a wall forever.
    """
    x = clamp(x, 30, config.WORLD_WIDTH - 30)
    y = clamp(y, 60, config.WORLD_HEIGHT - 30)
    if walkable(x, y):
        return x, y

    best: tuple[float, float, float] | None = None
    for rx, ry, rw, rh in BUILDING_RECTS:
        if rx - 44 <= x <= rx + rw + 44 and ry - 44 <= y <= ry + rh + 44:
            for pad in (config.PLAYER_RADIUS + 6, config.PLAYER_RADIUS + 24,
                        config.PLAYER_RADIUS + 46):
                cy = ry + rh + pad
                for cx in (clamp(x, rx - 20, rx + rw + 20), rx - 22, rx + rw + 22):
                    if walkable(cx, cy):
                        score = abs(cy - y) + abs(cx - x) * 0.35
                        if best is None or score < best[0]:
                            best = (score, cx, cy)
    if best:
        return best[1], best[2]

    for radius in range(8, 260, 8):
        for k in range(16):
            ang = k * math.pi / 8
            cx = clamp(x + math.cos(ang) * radius, 30, config.WORLD_WIDTH - 30)
            cy = clamp(y + math.sin(ang) * radius, 60, config.WORLD_HEIGHT - 30)
            if walkable(cx, cy):
                return cx, cy
    return 900.0, 800.0


NAV_CELL = 30
_NAV: tuple[int, int, list[list[bool]]] | None = None
_PATH_CACHE: dict[tuple[int, int, int, int], list[tuple[float, float]]] = {}


def _cache_path(key: tuple[int, int, int, int], path: list[tuple[float, float]]) -> list[tuple[float, float]]:
    if len(_PATH_CACHE) > 2400:
        _PATH_CACHE.clear()
    _PATH_CACHE[key] = path
    return path


def nav_grid() -> tuple[int, int, list[list[bool]]]:
    """Coarse walkability grid, built lazily and reused by A*."""
    global _NAV
    if _NAV is None:
        cols = int(config.WORLD_WIDTH // NAV_CELL) + 1
        rows = int(config.WORLD_HEIGHT // NAV_CELL) + 1
        grid = [[walkable(c * NAV_CELL + NAV_CELL / 2, r * NAV_CELL + NAV_CELL / 2)
                 for c in range(cols)] for r in range(rows)]
        _NAV = (cols, rows, grid)
    return _NAV


def _line_clear(x1: float, y1: float, x2: float, y2: float, step: float = 6.0) -> bool:
    """True when a body can walk the straight segment without touching a wall.

    Sampled every 6 px with a 2 px clearance margin. At the old 13 px / exact
    radius settings a building corner could slip between samples: the path
    looked legal, the walker then bumped the corner and replanned forever.
    """
    dist = math.hypot(x2 - x1, y2 - y1)
    n = max(1, int(dist // step))
    margin = config.PLAYER_RADIUS + 2.0
    for i in range(1, n + 1):
        t = i / n
        if not walkable(x1 + (x2 - x1) * t, y1 + (y2 - y1) * t, margin):
            return False
    return True


def find_path(x1: float, y1: float, x2: float, y2: float) -> list[tuple[float, float]]:
    """A tiny 8-way A* over the neighborhood grid, then line-of-sight smoothing.

    Returns a list of waypoints ending at the destination, or [] when the
    destination is unreachable. Buildings are obstacles, so residents walk
    around them rather than through them.
    """
    tx, ty = nearest_walkable(x2, y2)
    if not walkable(tx, ty):
        tx, ty = 900.0, 800.0
    if math.hypot(tx - x1, ty - y1) < 1.0:
        return [(tx, ty)]
    if _line_clear(x1, y1, tx, ty):
        return [(tx, ty)]
    cols, rows, grid = nav_grid()

    def snap(c: int, r: int) -> tuple[int, int]:
        """Nearest walkable cell to (c, r).

        A destination can be a perfectly legal standing spot while its grid
        cell centre is not (the point may sit 20 px from a wall, the centre
        15 px). Treating that cell as unreachable made A* return [] and the
        walk die half-way, which is one of the "player freezes" bugs.
        """
        c = max(0, min(cols - 1, c))
        r = max(0, min(rows - 1, r))
        if grid[r][c]:
            return c, r
        for rad in range(1, 9):
            best = None
            for dy in range(-rad, rad + 1):
                for dx in range(-rad, rad + 1):
                    nx, ny = c + dx, r + dy
                    if 0 <= nx < cols and 0 <= ny < rows and grid[ny][nx]:
                        dist = dx * dx + dy * dy
                        if best is None or dist < best[0]:
                            best = (dist, nx, ny)
            if best:
                return best[1], best[2]
        return c, r

    start_cell = snap(int(x1 // NAV_CELL), int(y1 // NAV_CELL))
    goal_cell = snap(int(tx // NAV_CELL), int(ty // NAV_CELL))
    cache_key = (start_cell[0], start_cell[1], goal_cell[0], goal_cell[1])
    cached = _PATH_CACHE.get(cache_key)
    if cached and _line_clear(x1, y1, cached[0][0], cached[0][1]):
        return list(cached)

    def center(c: int, r: int) -> tuple[float, float]:
        return (c * NAV_CELL + NAV_CELL / 2, r * NAV_CELL + NAV_CELL / 2)

    start = start_cell
    goal = goal_cell
    if start == goal:
        return [(tx, ty)]
    open_heap = [(0.0, start)]
    came: dict[tuple[int, int], tuple[int, int] | None] = {start: None}
    cost = {start: 0.0}
    found = False
    expansions = 0
    while open_heap and expansions < 5000:
        _, cur = heapq.heappop(open_heap)
        expansions += 1
        if cur == goal:
            found = True
            break
        cx, cy = cur
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                nx, ny = cx + dx, cy + dy
                if not (0 <= nx < cols and 0 <= ny < rows) or not grid[ny][nx]:
                    continue
                if dx and dy and (not grid[cy][nx] or not grid[ny][cx]):
                    continue
                step_cost = 1.4142 if dx and dy else 1.0
                new_cost = cost[cur] + step_cost
                nxt = (nx, ny)
                if new_cost < cost.get(nxt, 1e9):
                    cost[nxt] = new_cost
                    gx, gy = goal
                    h = math.hypot(nx - gx, ny - gy) * 1.12
                    came[nxt] = cur
                    heapq.heappush(open_heap, (new_cost + h, nxt))
    if not found:
        return []
    cells = []
    node: tuple[int, int] | None = goal
    while node is not None:
        cells.append(node)
        node = came.get(node)
    cells.reverse()
    points = [center(c, r) for c, r in cells]
    # Smooth from the walker's *actual* position, not from its cell centre:
    # a body standing 20 px off-centre can be unable to reach a leg that looks
    # clear between two grid centres ("walks into a wall and stops").
    points.insert(0, (x1, y1))
    out: list[tuple[float, float]] = []
    i = 0
    while i < len(points) - 1:
        j = len(points) - 1
        while j > i + 1 and not _line_clear(points[i][0], points[i][1], points[j][0], points[j][1]):
            j -= 1
        out.append(points[j])
        i = j
    out = out or [points[-1]]
    # Finish exactly on the requested point when the last leg can reach it.
    # Pocketed spots (a 20 px gap between two buildings is "walkable" but has
    # no way in) keep the grid centre instead of replanning forever.
    if _line_clear(out[-1][0], out[-1][1], tx, ty):
        out[-1] = (tx, ty)
    return _cache_path(cache_key, out)


def home_xy(home_id: int) -> tuple[float, float]:
    hx, hy, _ = HOMES[home_id % len(HOMES)]
    return hx + 46.0, hy + 88.0


def venue_spot(npc: NPC, loc_id: str) -> tuple[float, float]:
    """Where this resident stands at this venue.

    The ring is an ellipse sized to the *building*, so the first candidate is
    always outside the walls. The old fixed 170 px ring started inside the
    cafe's footprint, failed every attempt, and fell through to a shared
    ``nearest_walkable`` point — which stacked residents (and nameplates) on
    the same pixel.
    """
    if loc_id == "home":
        hx, hy = home_xy(npc.home_id)
        rng = random.Random(f"{npc.id}:home")
        return hx + rng.uniform(-26, 26), hy + rng.uniform(-6, 18)
    loc = LOCATION_BY_ID.get(loc_id)
    if not loc:
        return 900.0, 800.0
    idx = int(npc.id.split("_")[-1]) if npc.id.startswith("npc_") else 7
    cx, cy = loc["x"] + loc["w"] / 2, loc["y"] + loc["h"] / 2
    hw, hh = loc["w"] / 2, loc["h"] / 2

    # Golden-angle ellipse: stable per index, distinct per resident.
    for ring in range(3):
        angle = idx * 2.399963229728653 + ring * 0.83
        # Radii differ per index as well as per ring: golden-angle *angles*
        # nearly repeat every 34 steps (13/34 of a turn), so two residents far
        # apart in the id sequence can face the same direction.
        rx = hw + 38 + (idx % 4) * 19 + ring * 26
        ry = hh + 32 + (idx % 3) * 17 + ring * 22
        x = clamp(cx + math.cos(angle) * rx, 40, config.WORLD_WIDTH - 40)
        y = clamp(cy + math.sin(angle) * ry + 14, 70, config.WORLD_HEIGHT - 40)
        if walkable(x, y):
            return x, y

    # Something is built right there: sweep outward from this resident's own
    # seeded angle so neighbours never collapse onto one spot.
    seed_angle = (stable_hash("venue-spot", npc.id) % 3600) / 10.0
    for attempt in range(24):
        ang = math.radians((seed_angle + attempt * 137.507) % 360)
        grow = (attempt // 6) * 30
        rx = hw + 42 + grow
        ry = hh + 36 + grow
        x = clamp(cx + math.cos(ang) * rx, 40, config.WORLD_WIDTH - 40)
        y = clamp(cy + math.sin(ang) * ry + 14, 70, config.WORLD_HEIGHT - 40)
        if walkable(x, y):
            return x, y
    return nearest_walkable(cx, cy + hh + config.PLAYER_RADIUS + 16)


class Simulation:
    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------
    def __init__(self, *, seed: int, save_path: str | None = None, save_name: str = "world.json"):
        self.seed = int(seed)
        self.hub = RngHub(seed)
        self.save_path = save_path or os.path.join(config.data_dir(), "saves", save_name)
        self.schema = config.SCHEMA_VERSION
        self.minute: float = float(config.DAY_START_MINUTE)
        self.speed: int = 1
        self.npcs: list[NPC] = []
        self.by_id: dict[str, NPC] = {}
        self.player: Player | None = None
        self.rels: dict[str, dict] = {}
        self.posts: list[Post] = []
        self.threads: dict[str, Thread] = {}
        self.notifications: list[dict] = []
        self.notices: list[dict] = []
        self.events: list[dict] = []
        self.rivalries: list[Rivalry] = []
        self.cases: list[Case] = []
        self.arcs: list[Arc] = []
        self.rumors: list[dict] = []
        self.calls: dict[str, dict] = {}
        self.world_flags: dict[str, Any] = {}
        self.metrics: dict[str, Any] = {
            "events": 0, "posts": 0, "messages": 0, "calls": 0, "dialogue_turns": 0,
            "chaos_scenes": 0, "gifts": 0, "dates": 0, "rumor_spreads": 0,
            "llm_calls": 0, "started_real": time.time(),
            "voice_metrics": [],
        }
        self.created_at: float = time.time()
        self.last_save_real: float = 0.0
        self._dirty = False
        self._player_dest: tuple[float, float] | None = None
        self._player_path: list[tuple[float, float]] = []
        self._last_safe: tuple[float, float] | None = None
        self._replans = 0
        self._npc_paths: dict[str, list[tuple[float, float]]] = {}
        self._npc_replan: dict[str, float] = {}

    # -- lifecycle -----------------------------------------------------
    @classmethod
    def new(cls, seed: int, player_spec: dict, save_path: str | None = None) -> Simulation:
        from blxverse.engine.generate import (
            generate_npcs,
            initial_world_flags,
            seed_relationships,
        )

        sim = cls(seed=seed, save_path=save_path)
        sim.npcs = generate_npcs(sim.hub)
        sim.by_id = {n.id: n for n in sim.npcs}
        sim.rels = seed_relationships(sim.npcs)
        spec = player_spec or {}
        sim.player = Player(
            id="player",
            name=str(spec.get("name", "You"))[:24] or "You",
            gender=spec.get("gender", "female") if spec.get("gender") in ("male", "female", "nonbinary") else "female",
            pronouns={"male": "he/him", "female": "she/her", "nonbinary": "they/them"}.get(spec.get("gender", "female"), "she/her"),
            age=int(spec.get("age", 26)),
            occupation="newcomer",
            look=spec.get("look", {}),
            home_id=17,
            wallet=config.STARTING_BALANCE,
            energy=100.0,
            mood=__import__("blxverse.engine.models", fromlist=["Mood"]).Mood(valence=16, stress=8, excitement=48, irritation=0, social_energy=86),
            reputation=50.0,
            x=home_xy(17)[0],
            y=home_xy(17)[1] + 26,
            inventory={},
            ledger=[],
            flags={"cart_owned": False, "call_consent": False, "known_rumors": [], "moved_in_day": 0},
            stats={},
            created_at=time.time(),
            last_active=time.time(),
        )
        # merge default look fields the client may not have sent
        defaults = {"skin": "#d9a066", "hair": "#3b2417", "hairStyle": "short",
                    "outfit": "#e0663b", "accent": "#ffd166", "accessory": "none", "height": 1.0}
        for k, v in defaults.items():
            sim.player.look.setdefault(k, v)
        sim.player.home_id = 17
        hx, hy = home_xy(sim.player.home_id)
        sim.player.x, sim.player.y = hx, hy + 26
        # normalise player relationship entries
        for n in sim.npcs:
            for key in (f"{n.id}|player", f"player|{n.id}"):
                r = sim.rels.setdefault(key, {})
                r.update({k: r.get(k, d) for k, d in {
                    "familiarity": 0.0, "trust": 20.0, "affinity": 0.0, "romance": 0.0,
                    "tension": 0.0, "flags": [], "interactions": 0, "last": -9999.0,
                    "gifts": {}, "dates": 0, "conflicts": 0,
                }.items()})
        sim.world_flags = initial_world_flags()
        sim.world_flags["weather"] = sim._weather_for_day(0)
        sim.world_flags["next_message_minute"] = sim.minute + 55
        sim.world_flags["next_call_minute"] = sim.minute + 120
        sim.world_flags["next_rumor_minute"] = sim.minute + 60
        sim.world_flags["last_day_tick"] = 0
        sim.world_flags["pending_messages"] = []
        sim.world_flags["pending_call"] = None
        sim.world_flags["date_offers"] = []
        sim.world_flags["ambient_host"] = None
        sim._place_npcs_at_schedule()
        sim._seed_initial_life()
        sim._seed_backstory_memories()
        sim.last_save_real = time.time() - 3600
        sim.save(force=True)
        return sim

    def _seed_backstory_memories(self) -> None:
        """Give every resident a small pre-existing history.

        Memories are the character's own recollection, not world truth: two
        people can remember the same afternoon differently. This is what makes
        the first profile feel like a person who existed before the player.
        """
        rng = self.hub.stream("backstory")
        templates_positive = [
            "{other} helped them carry groceries up the stairs last week.",
            "{other} saved them a seat at the cafe during the rain.",
            "They and {other} argued about the best song of the summer and agreed to disagree.",
            "{other} fixed their bike chain in the square, narrating every step.",
            "A long conversation with {other} about leaving town and staying anyway.",
        ]
        templates_negative = [
            "{other} never returned the book they borrowed in spring.",
            "{other} made a joke at their expense in front of everyone at the square.",
            "They and {other} have disagreed about parking since the beginning of time.",
        ]
        for npc in self.npcs:
            friends = []
            for other_id, rel in self.outgoing_rels(npc.id):
                other = self.npc(other_id)
                if other:
                    friends.append((other, rel))
            if not friends:
                continue
            friends.sort(key=lambda item: -item[1].get("affinity", 0))
            chosen = friends[:2] + friends[-1:]
            for other, rel in chosen[:3]:
                positive = rel.get("affinity", 0) >= 0
                pool = templates_positive if positive else templates_negative
                summary = pool[rng.randrange(len(pool))].format(other=other.first)
                mem = Memory(
                    id=new_id("mem"), minute=self.minute - rng.uniform(700, 2400),
                    day=max(0, self.day_number - rng.randint(1, 3)), event_id=new_id("evt"),
                    kind="backstory", summary=summary, importance=rng.uniform(0.2, 0.45),
                    valence=0.4 if positive else -0.3, source="participated",
                    with_ids=[other.id], location=npc.location_id or "home", tag="backstory",
                )
                npc.remember(mem)
        self._dirty = True

    def _seed_initial_life(self) -> None:
        welcome = (
            f"Welcome to Bellwether Block. {len(self.npcs)} residents, one square, "
            f"eleven places to be seen, and a fountain with strong opinions."
        )
        self.add_notice(kind="news", title="Welcome to BLXVERSE", body=welcome, location="square")
        self.note("Welcome to Bellwether", "You just moved in. Walk around, say hi — the block already has a rhythm of its own.", kind="welcome")
        self.note("Tip: click a resident to interact", "You can talk, text, call, gift and more. Press Temple to open your phone.", kind="welcome")
        awake = [n for n in self.npcs if n.spotlight]
        picks = awake[:3]
        for i, npc in enumerate(picks):
            tpl = POST_TEMPLATES["morning"][i % len(POST_TEMPLATES["morning"])]
            text = tpl.replace("{venue}", self.location_names.get(npc.location_id, "the block"))
            self.push_feed(author_id=npc.id, text=text, mood="hopeful", tag="morning", loc=npc.location_id)
        # Zara's first post is part of the chain's texture
        zara = self.npc_by_first("Zara")
        if zara:
            self.push_feed(
                author_id=zara.id,
                text="Just moved into a place on Juniper Row. Boxes everywhere, one working lamp, and a ceiling that drips in rhythm. Maybe it's a sign. Maybe it's a leak. 🎹",
                mood="nervous", tag="moving", loc="home",
            )
        for loc in ("cafe", "park", "square"):
            self.add_notice(
                kind="event",
                title={"cafe": "Two Rivers Cafe is open", "park": "Juniper Park: all are welcome",
                       "square": "Bellwether Square notice board"}[loc],
                body={"cafe": "Fresh mango cake at 10:00. The barista is taking song requests again whether you want them or not.",
                      "park": "The swings were fixed. The pigeons were not.",
                      "square": "Lantern Festival planning meeting this Sunday. Bring an opinion, leave with two."}[loc],
                location=loc,
            )

    # ------------------------------------------------------------------
    # Clock helpers
    # ------------------------------------------------------------------
    @property
    def day_index(self) -> int:
        return int(self.minute // 1440)

    @property
    def day_number(self) -> int:
        return self.day_index + 1

    @property
    def hour_of_day(self) -> float:
        return (self.minute % 1440) / 60.0

    @property
    def weekday(self) -> str:
        return WEEKDAYS[self.day_index % 7]

    def clock_label(self) -> str:
        h = int(self.hour_of_day)
        m = int((self.hour_of_day - h) * 60)
        return f"{self.weekday} {h:02d}:{m:02d}"

    def time_label(self) -> str:
        return f"Day {self.day_number} · {self.clock_label()}"

    def _weather_for_day(self, day: int) -> str:
        rng = RngHub(self.seed)
        return WEATHERS[(day * 3 + rng.stream("weather").randrange(6)) % len(WEATHERS)]

    @property
    def location_names(self) -> dict[str, str]:
        names = {loc["id"]: loc["name"] for loc in LOCATIONS}
        names["home"] = "home"
        return names

    # ------------------------------------------------------------------
    # Lookups
    # ------------------------------------------------------------------
    def npc(self, npc_id: str) -> NPC | None:
        return self.by_id.get(npc_id)

    def npc_by_first(self, first: str) -> NPC | None:
        return next((n for n in self.npcs if n.first.lower() == first.lower()), None)

    def npc_by_flag(self, flag: str) -> NPC | None:
        return next((n for n in self.npcs if n.flags.get(flag)), None)

    def pick_gossip_npc(self, exclude: set[str] | None = None) -> NPC | None:
        exclude = exclude or set()
        pool = [n for n in self.npcs if n.spotlight and n.id not in exclude]
        pool.sort(key=lambda n: -(n.stats.get("chatter", 0) + n.stats.get("curiosity", 0) * 0.5
                                   + (0.4 if n.archetype in ("spark", "trickster", "storm") else 0)))
        return pool[0] if pool else None

    def outgoing_rels(self, npc_id: str):
        prefix = f"{npc_id}|"
        for key, rel in self.rels.items():
            if key.startswith(prefix):
                yield key.split("|", 1)[1], rel

    # ------------------------------------------------------------------
    # Relationships
    # ------------------------------------------------------------------
    def _rel_key(self, a: str, b: str) -> str:
        return f"{a}|{b}"

    def rel(self, a: str, b: str) -> dict:
        key = self._rel_key(a, b)
        r = self.rels.get(key)
        if r is None:
            r = {
                "familiarity": 0.0, "trust": 20.0, "affinity": 0.0, "romance": 0.0,
                "tension": 0.0, "flags": [], "interactions": 0, "last": -9999.0,
                "gifts": {}, "dates": 0, "conflicts": 0,
            }
            self.rels[key] = r
        return r

    def adjust_rel(self, a: str, b: str, *, familiarity: float = 0.0, trust: float = 0.0,
                   affinity: float = 0.0, romance: float = 0.0, tension: float = 0.0,
                   dates: int = 0, conflicts: int = 0, count_interaction: bool = False) -> dict:
        r = self.rel(a, b)
        r["familiarity"] = clamp(float(r.get("familiarity", 0)) + familiarity, 0, config.FAMILIARITY_MAX)
        r["trust"] = clamp(float(r.get("trust", 20)) + trust, 0, config.TRUST_MAX)
        r["affinity"] = clamp(float(r.get("affinity", 0)) + affinity, config.REL_MIN, config.REL_MAX)
        r["romance"] = clamp(float(r.get("romance", 0)) + romance, 0, config.ROMANCE_MAX)
        r["tension"] = clamp(float(r.get("tension", 0)) + tension, 0, config.TENSION_MAX)
        r["dates"] = int(r.get("dates", 0)) + dates
        r["conflicts"] = int(r.get("conflicts", 0)) + conflicts
        r["last"] = self.minute
        if count_interaction:
            r["interactions"] = int(r.get("interactions", 0)) + 1
        self._apply_rel_flags(a, b)
        self._dirty = True
        return r

    def _apply_rel_flags(self, a: str, b: str) -> None:
        ab = self.rel(a, b)
        flags = list(ab.get("flags", []))
        if ab["tension"] >= config.RIVAL_TENSION and "dating" not in flags and "ex" not in flags and "rival" not in flags:
            flags.append("rival")
        if ab["tension"] < config.RECONCILE_TENSION and "rival" in flags and ab.get("conflicts", 0) > 0:
            # reconciliation only clears the rival flag after an apology or time; keep until action
            pass
        if ab["romance"] >= 55 and ab["affinity"] >= 42 and "dating" not in flags and "ex" not in flags:
            flags.append("crush")
        # de-duplicate: this runs on every relationship tick, and repeating
        # "crush" five times broke label logic and the profile chips.
        ab["flags"] = sorted(set(flags))

    def set_rel_flag(self, a: str, b: str, flag: str, value: bool = True) -> None:
        r = self.rel(a, b)
        flags = set(r.get("flags", []))
        if value:
            flags.add(flag)
            if flag in ("dating", "partner"):
                flags.discard("crush")
        else:
            flags.discard(flag)
        r["flags"] = sorted(flags)
        self._dirty = True

    def record_rivalry(self, a: str, b: str, *, cause: str, tension: float) -> Rivalry:
        existing = next((r for r in self.rivalries if {r.a, r.b} == {a, b}), None)
        if existing:
            existing.tension = max(existing.tension, tension)
            existing.status = "clashing" if tension >= config.CHAOS_TENSION_THRESHOLD else existing.status
            existing.last_minute = self.minute
            existing.clashes += 1
            return existing
        rv = Rivalry(id=new_id("rivalry"), a=a, b=b, cause=cause, tension=tension,
                     status="clashing" if tension >= config.CHAOS_TENSION_THRESHOLD else "simmering",
                     created=self.minute, last_minute=self.minute, clashes=1)
        self.rivalries.append(rv)
        return rv

    # ------------------------------------------------------------------
    # Events & memory
    # ------------------------------------------------------------------
    def add_event(self, *, kind: str, actor: str, targets: list[str], location: str,
                  facts: dict, witnesses: list[str], visibility: str, summary: str) -> dict:
        event = {
            "id": new_id("evt"), "minute": round(self.minute, 2), "day": self.day_number,
            "kind": kind, "actor": actor, "targets": list(targets), "location": location,
            "facts": facts, "witnesses": list(witnesses), "visibility": visibility,
            "summary": summary,
        }
        self.events.append(event)
        self.events = self.events[-240:]
        self.metrics["events"] += 1
        if kind == "slapstick":
            self.metrics["chaos_scenes"] += 1
        return event

    def remember(self, npc: NPC, event: dict, *, importance: float = 0.4,
                 valence: float = 0.0, source: str = "witnessed") -> Memory:
        for mem in npc.memory:
            if mem.event_id == event["id"]:
                return mem
        mem = Memory(
            id=new_id("mem"), minute=self.minute, day=self.day_number,
            event_id=event["id"], kind=event["kind"], summary=event["summary"],
            importance=clamp(importance, 0, 1), valence=clamp(valence, -1, 1),
            source=source, with_ids=list(event.get("targets", [])), location=event.get("location", ""),
            tag=event["kind"],
        )
        npc.remember(mem)
        return mem

    def player_memory(self, summary: str, kind: str = "life", valence: float = 0.2) -> None:
        if not self.player:
            return
        self.player.stats["memories"] = int(self.player.stats.get("memories", 0)) + 1
        self.player.flags.setdefault("journal", [])
        self.player.flags["journal"].append({
            "minute": round(self.minute, 1), "day": self.day_number,
            "summary": summary[:220], "kind": kind, "valence": round(valence, 2),
        })
        self.player.flags["journal"] = self.player.flags["journal"][-120:]

    # ------------------------------------------------------------------
    # Notifications, notices, feed
    # ------------------------------------------------------------------
    def note(self, title: str, body: str, kind: str = "info") -> dict:
        n = {"id": new_id("ntf"), "minute": round(self.minute, 1), "day": self.day_number,
             "title": title[:80], "body": body[:240], "kind": kind, "read": False}
        self.notifications.append(n)
        self.notifications = self.notifications[-80:]
        return n

    def add_notice(self, *, kind: str, title: str, body: str, location: str = "") -> dict:
        n = {"id": new_id("notice"), "minute": round(self.minute, 1), "day": self.day_number,
             "kind": kind, "title": title[:90], "body": body[:400], "location": location}
        self.notices.append(n)
        self.notices = self.notices[-60:]
        return n

    def push_feed(self, *, author_id: str, text: str, mood: str = "", tag: str = "", loc: str = "") -> Post:
        text = text.strip()[:config.MAX_POST_LENGTH]
        post = Post(id=new_id("post"), author_id=author_id, text=text, minute=self.minute,
                    mood=mood, tag=tag, loc=loc)
        self.posts.append(post)
        self.posts = self.posts[-config.FEED_CAP:]
        self.metrics["posts"] += 1
        if author_id != "player":
            self._feed_reactions(post)
        return post

    def _feed_reactions(self, post: Post) -> None:
        """NPC likes/comments on a post, consistent with relationships."""
        author = self.npc(post.author_id)
        if not author:
            return
        rng = self.hub.stream("feed-reactions")
        candidates = [n for n in self.npcs if n.id != author.id and n.spotlight]
        for n in rng.sample(candidates, min(6, len(candidates))):
            r = self.rel(n.id, author.id)
            p_like = 0.18 + r.get("affinity", 0) / 220.0 + (0.15 if r.get("flags") else 0)
            if rng.random() < p_like:
                post.likes.append(n.id)
            if rng.random() < 0.07 + max(0.0, r.get("affinity", 0)) / 600.0:
                comment = COMMENT_TEMPLATES[rng.randrange(len(COMMENT_TEMPLATES))]
                post.comments.append(Comment(id=new_id("cmt"), author_id=n.id, text=comment,
                                             minute=self.minute, likes=rng.randint(0, 4)))
        post.comments = post.comments[-6:]

    # ------------------------------------------------------------------
    # Rumors & beliefs
    # ------------------------------------------------------------------
    def add_rumor(self, *, claim: str, subject_id: str, truth: str, origin_id: str,
                  confidence: float, location: str) -> dict:
        rumor = {
            "id": new_id("rumor"), "claim": claim, "subject": subject_id, "truth": truth,
            "origin": origin_id, "created": round(self.minute, 1), "location": location,
            "spread": [], "corrections": [],
        }
        self.rumors.append(rumor)
        origin = self.npc(origin_id)
        if origin:
            self._teach_rumor(origin, rumor, source_id="self", confidence=confidence)
        # immediate circle: people who are physically near the origin hear it
        origin_npc = self.npc(origin_id)
        if origin_npc:
            listeners = [n for n in self.npcs if n.id != origin_id and n.location_id == origin_npc.location_id]
            rng = self.hub.stream(f"rumor:{rumor['id']}")
            for listener in listeners[:4]:
                if rng.random() < 0.5:
                    self._teach_rumor(listener, rumor, source_id=origin_id,
                                      confidence=confidence * 0.75)
        return rumor

    def _teach_rumor(self, npc: NPC, rumor: dict, *, source_id: str, confidence: float) -> None:
        if npc.id == rumor["subject"]:
            return
        existing = next((b for b in npc.beliefs if b.rumor_id == rumor["id"]), None)
        if existing:
            existing.confidence = clamp(max(existing.confidence, confidence) + 0.06, 0, 0.96)
            existing.updated_minute = self.minute
            return
        if len(npc.beliefs) >= 14:
            npc.beliefs.sort(key=lambda b: b.confidence)
            npc.beliefs.pop(0)
        belief = Belief(
            id=new_id("belief"), claim=rumor["claim"], subject_id=rumor["subject"],
            truth="unknown", confidence=clamp(confidence, 0.05, 0.95), source_id=source_id,
            created_minute=self.minute, updated_minute=self.minute, rumor_id=rumor["id"],
        )
        npc.beliefs.append(belief)
        rumor["spread"].append({
            "npc": npc.id, "source": source_id, "confidence": round(belief.confidence, 3),
            "minute": round(self.minute, 1),
        })
        self.metrics["rumor_spreads"] += 1
        # memory of hearing the claim (belief != verified fact)
        ev = self.add_event(
            kind="heard_rumor", actor=source_id, targets=[npc.id], location=npc.location_id,
            facts={"claim": rumor["claim"], "confidence": round(belief.confidence, 2),
                   "truth": "unverified", "rumor_id": rumor["id"]},
            witnesses=[], visibility="participants",
            summary=f"Heard a claim that {rumor['claim']}.",
        )
        self.remember(npc, ev, importance=0.4, valence=-0.1, source="told")

    def spread_rumor_social(self, believer: NPC, listener: NPC, rumor: dict) -> bool:
        rng = self.hub.stream(f"spread:{believer.id}:{listener.id}:{rumor['id']}")
        p = config.RUMOR_SPREAD_BASE * (0.6 + believer.stats.get("chatter", 0.5))
        if "gossipy" in believer.traits:
            p += 0.15
        if "private" in believer.traits:
            p -= 0.18
        if rng.random() > p:
            return False
        belief = next((b for b in believer.beliefs if b.rumor_id == rumor["id"]), None)
        if not belief:
            return False
        self._teach_rumor(listener, rumor, source_id=believer.id, confidence=belief.confidence * 0.72)
        self.adjust_rel(listener.id, believer.id, familiarity=1.0, affinity=0.3)
        return True

    def resolve_case(self, case: Case, *, by: str, evidence: list[str]) -> None:
        if case.status != "open":
            return
        case.status = "cleared"
        case.found_evidence = list(dict.fromkeys(case.found_evidence + evidence))
        daniel = self.npc(case.accused)
        accuser = self.npc(case.accuser)
        for rumor in self.rumors:
            if rumor["subject"] != case.accused:
                continue
            rumor["truth"] = "false"
            rumor["corrections"].append({"minute": round(self.minute, 1), "by": by,
                                          "evidence": evidence})
            for npc in self.npcs:
                for belief in npc.beliefs:
                    if belief.rumor_id == rumor["id"]:
                        belief.truth = "false"
                        belief.confidence = clamp(belief.confidence * 0.3, 0, 0.35)
                        belief.evidence.extend(evidence[:2])
                        belief.updated_minute = self.minute
        correction = self.add_event(
            kind="truth_revealed", actor=accuser.id if accuser else case.accuser, targets=[case.accused],
            location=case.location, facts={"case": case.id, "truth": "the accusation was false"},
            witnesses=[], visibility="public",
            summary=f"The truth came out: {case.item} was never stolen. The accusation was false.",
        )
        for npc in self.npcs:
            if npc.id in (case.accused, case.accuser):
                continue
            if any(b.evidence for b in npc.beliefs):
                self.remember(npc, correction, importance=0.5, valence=0.2, source="told")
        if daniel:
            daniel.mood.valence = clamp(daniel.mood.valence + 22, -100, 100)
            daniel.mood.stress = clamp(daniel.mood.stress - 30, 0, 100)
            if by == "player":
                self.adjust_rel(daniel.id, "player", familiarity=12, trust=16, affinity=16)
                self.adjust_rel("player", daniel.id, familiarity=12, trust=16, affinity=16)
                zara = self.npc_by_first("Zara")
                if zara:
                    self.adjust_rel(zara.id, "player", familiarity=10, trust=12, affinity=14)
                    self.adjust_rel("player", zara.id, familiarity=10, trust=12, affinity=14)
        if accuser:
            accuser.mood.valence = clamp(accuser.mood.valence - 18, -100, 100)
            accuser.mood.stress = clamp(accuser.mood.stress + 14, 0, 100)
            if by == "player":
                self.adjust_rel(accuser.id, "player", affinity=-12, trust=-6, tension=8)
                self.adjust_rel("player", accuser.id, affinity=-12, trust=-6, tension=8)
        ev = self.add_event(
            kind="evidence_found", actor=by, targets=[case.accused], location=case.location,
            facts={"case": case.id, "evidence": evidence, "truth": "false"},
            witnesses=[], visibility="public",
            summary=f"Evidence cleared {daniel.first if daniel else 'the accused'}: {case.item} was never stolen.",
        )
        if daniel:
            self.remember(daniel, ev, importance=0.9, valence=0.8, source="told")
        if accuser:
            self.remember(accuser, ev, importance=0.9, valence=-0.6, source="told")
        self.player.reputation = clamp(self.player.reputation + (6 if by == "player" else 0), 0, 100)
        self.add_notice(kind="news", title="Case closed" if by == "player" else "Case resolved",
                        body=f"{case.item} was found. {case.title} is closed. The accusation was false.",
                        location=case.location)
        if by == "player":
            self.push_feed(
                author_id="player",
                text="I asked around, checked receipts, and followed the boring clues. The studio mic was in the studio locker. Daniel didn't take anything. Receipts > rumors.",
                mood="firm", tag="accountability", loc=case.location,
            )
            self.note("Case cleared", "You cleared Daniel's name. The block is quietly impressed.", kind="story")

    # ------------------------------------------------------------------
    # NPC placement & schedules
    # ------------------------------------------------------------------
    def _block_for(self, npc: NPC, hour: float) -> dict | None:
        key = "weekend" if self.day_index % 7 >= 5 else "weekday"
        blocks = npc.schedule.get(key, [])
        for b in blocks:
            if b["start"] <= hour < b["end"]:
                return b
        # A schedule gap is genuinely "nothing planned". Returning the last
        # block here used to mark half the block as asleep at 6 pm, because
        # the last block of every weekday is bedtime.
        return None

    def _gap_activity(self, npc: NPC) -> dict:
        """Stand-in block for the minutes between scheduled activities."""
        return {"start": 0.0, "end": 0.0, "loc": npc.location_id or "home",
                "activity": "between things", "kind": "gap"}

    def _npc_destination(self, npc: NPC, loc_id: str) -> tuple[float, float]:
        banned_until = npc.flags.get("banned_until", 0)
        banned_from = npc.flags.get("banned_from")
        if banned_until > self.minute and banned_from and loc_id == banned_from:
            loc_id = "home"
        return venue_spot(npc, loc_id)

    def _place_npcs_at_schedule(self) -> None:
        for npc in self.npcs:
            block = self._block_for(npc, self.hour_of_day)
            if block:
                loc = block["loc"]
                x, y = self._npc_destination(npc, loc)
                npc.x, npc.y = x, y
                npc.location_id = loc
                npc.status = "sleeping" if block["kind"] == "sleep" else "at"
                npc.activity = block["activity"]
                npc.flags["block_key"] = f"{block['start']}:{block['loc']}:{block['activity']}"
            else:
                # Loading into a gap: nobody is asleep, and we keep their home
                # as the anchor rather than guessing.
                x, y = self._npc_destination(npc, "home")
                npc.x, npc.y = x, y
                npc.location_id = "home"
                npc.status = "at"
                npc.activity = "between things"
                npc.flags["block_key"] = "gap"
            npc.mood.social_energy = clamp(npc.mood.social_energy, 5, 100)
        self._separate_crowd()

    def _separate_crowd(self, min_gap: float = 18.0) -> None:
        """Keep residents at the same venue from occupying one pixel.

        Venue spots are deterministic per resident, but two ids can still land
        close together; a short deterministic nudge keeps nameplates legible
        and stops bodies from reading as a single person.
        """
        placed: dict[str, list[tuple[float, float]]] = {}
        for npc in self.npcs:
            if not npc.location_id or npc.location_id == "home":
                continue
            crowd = placed.setdefault(npc.location_id, [])
            for _ in range(10):
                clash = next(
                    ((px, py) for px, py in crowd if math.hypot(npc.x - px, npc.y - py) < min_gap),
                    None,
                )
                if clash is None:
                    break
                base = math.atan2(npc.y - clash[1], npc.x - clash[0]) or 0.0
                moved = False
                for k in range(1, 8):
                    ang = base + k * (math.pi / 3)
                    nx = clamp(npc.x + math.cos(ang) * min_gap, 40, config.WORLD_WIDTH - 40)
                    ny = clamp(npc.y + math.sin(ang) * min_gap * 0.8, 70, config.WORLD_HEIGHT - 40)
                    if walkable(nx, ny):
                        npc.x, npc.y = nx, ny
                        moved = True
                        break
                if not moved:
                    break
            crowd.append((npc.x, npc.y))

    def _nudge_clear(self, npc: NPC, x: float, y: float, gap: float = 18.0) -> tuple[float, float]:
        """Last-step spacing: don't finish a walk on top of someone else."""
        for other in self.npcs:
            if other is npc or other.location_id != npc.location_id:
                continue
            if math.hypot(other.x - x, other.y - y) >= gap:
                continue
            base = math.atan2(y - other.y, x - other.x) or 0.0
            for k in range(1, 8):
                ang = base + k * (math.pi / 3)
                nx = clamp(x + math.cos(ang) * gap, 40, config.WORLD_WIDTH - 40)
                ny = clamp(y + math.sin(ang) * gap * 0.8, 70, config.WORLD_HEIGHT - 40)
                if walkable(nx, ny):
                    return nx, ny
        return x, y

    def force_move(self, npc: NPC, loc_id: str) -> None:
        x, y = self._npc_destination(npc, loc_id)
        npc.x, npc.y = x, y
        npc.location_id = loc_id
        npc.status = "at"
        npc.target = None
        self._npc_paths.pop(npc.id, None)
        npc.activity = f"arriving at {self.location_names.get(loc_id, loc_id)}"

    # ------------------------------------------------------------------
    # Movement
    # ------------------------------------------------------------------
    def set_player_destination(self, x: float, y: float) -> None:
        if not self.player:
            raise SimError("No active player", "no_player")
        try:
            x, y = float(x), float(y)
        except (TypeError, ValueError):
            raise SimError("Destination must be numeric", "bad_destination") from None
        if not math.isfinite(x) or not math.isfinite(y):
            raise SimError("Destination must be finite", "bad_destination")
        x, y = nearest_walkable(clamp(x, 0, config.WORLD_WIDTH), clamp(y, 0, config.WORLD_HEIGHT))
        if math.hypot(x - self.player.x, y - self.player.y) > 3200:
            raise SimError("Destination too far away", "bad_destination")
        self._player_dest = (x, y)
        self._last_safe = (self.player.x, self.player.y)
        self._replans = 0
        self._player_path = find_path(self.player.x, self.player.y, x, y) or [(x, y)]
        self._dirty = True

    def stop_player(self) -> None:
        self._player_dest = None
        self._player_path = []

    def player_route_payload(self) -> dict:
        """Remaining waypoints, so the client animates the path the server walks.

        The client used to interpolate straight to the clicked point, which
        crossed buildings and drifted away from the authoritative A* path; the
        poll then snapped it back, producing the front-and-back jitter.
        """
        if not self._player_dest:
            return {"route": [], "dest": None}
        return {
            "route": [{"x": round(x, 1), "y": round(y, 1)} for x, y in self._player_path[:48]],
            "dest": {"x": round(self._player_dest[0], 1), "y": round(self._player_dest[1], 1)},
        }

    def _move_player(self, real_dt: float) -> None:
        """Walk the authoritative A* route one tick at a time.

        The sprite must never clip a building, never wedge in a gap, and never
        stop dead in the middle of the street. So movement is confined to
        segments the pathfinder already validated: if a step is refused, the
        player rewinds to the last good point on the route and replans from
        there (instead of sliding sideways into a pocket the 30 px nav grid
        cannot see out of).
        """
        if not self.player or not self._player_dest:
            return
        if not self._player_path:
            self._player_path = find_path(self.player.x, self.player.y,
                                          self._player_dest[0], self._player_dest[1])
            if not self._player_path:
                # Nothing reachable right now: settle on the nearest walkable
                # spot instead of freezing with a destination still set.
                self._player_dest = nearest_walkable(*self._player_dest)
                return
            # find_path may stop at the last reachable cell if the exact
            # destination is pocketed; walk to where the route really ends.
            self._player_dest = self._player_path[-1]
        budget = config.PLAYER_MAX_SPEED * real_dt
        while budget > 0 and self._player_path:
            px, py = self.player.x, self.player.y
            tx, ty = self._player_path[0]
            dx, dy = tx - px, ty - py
            dist = math.hypot(dx, dy)
            if dist <= 0.001:
                self._player_path.pop(0)
                continue
            if dist <= budget:
                self.player.x, self.player.y = tx, ty
                self._last_safe = (tx, ty)
                self._player_path.pop(0)
                budget -= dist
                continue
            nx, ny = px + dx / dist * budget, py + dy / dist * budget
            if walkable(nx, ny):
                self.player.x, self.player.y = nx, ny
                self._last_safe = (nx, ny)
                budget = 0
                break
            # The leg is pinched. Step back to the last point we know is
            # clear, and re-route from there rather than squeezing through.
            safe = getattr(self, '_last_safe', None) or (px, py)
            self.player.x, self.player.y = safe
            self._player_path = find_path(safe[0], safe[1],
                                          self._player_dest[0], self._player_dest[1])
            self._replans = getattr(self, '_replans', 0) + 1
            if not self._player_path or self._replans > 8:
                # Safety net: never grind against the same corner forever.
                self._player_dest = None
                self._player_path = []
            budget = 0
        if not self._player_path:
            self._player_dest = None
        drain = 0.004 * real_dt
        self.player.energy = clamp(self.player.energy - drain, 0, 100)

    def _move_npcs(self, game_dt: float) -> None:
        step_base = config.NPC_WALK_SPEED * game_dt
        for npc in self.npcs:
            if npc.status == "sleeping" or not npc.target:
                continue
            tx, ty = npc.target["x"], npc.target["y"]
            path = self._npc_paths.get(npc.id)
            if not path:
                path = find_path(npc.x, npc.y, tx, ty) or [(tx, ty)]
                self._npc_paths[npc.id] = path
            budget = step_base
            while budget > 0 and path:
                wx, wy = path[0]
                dx, dy = wx - npc.x, wy - npc.y
                dist = math.hypot(dx, dy)
                if dist <= 0.001:
                    path.pop(0)
                    continue
                if dist <= budget:
                    npc.x, npc.y = wx, wy
                    path.pop(0)
                    budget -= dist
                    continue
                nx, ny = npc.x + dx / dist * budget, npc.y + dy / dist * budget
                if walkable(nx, ny):
                    npc.x, npc.y = nx, ny
                elif walkable(nx, npc.y):
                    npc.x = nx
                elif walkable(npc.x, ny):
                    npc.y = ny
                elif self.minute >= self._npc_replan.get(npc.id, 0):
                    self._npc_replan[npc.id] = self.minute + 6
                    self._npc_paths[npc.id] = find_path(npc.x, npc.y, tx, ty) or [(tx, ty)]
                budget = 0
            if not path:
                npc.x, npc.y = self._nudge_clear(npc, tx, ty)
                npc.location_id = npc.target.get("loc", npc.location_id)
                npc.status = "at"
                npc.activity = npc.target.get("activity", npc.activity)
                npc.target = None
                self._npc_paths.pop(npc.id, None)

    def _announce_events(self) -> None:
        """Tell the player when a fixture starts; residents already drift in."""
        live = self.live_events()
        seen = self.world_flags.setdefault("announced_events", [])
        for ev in live:
            key = f"{ev['id']}:{ev['due']}"
            if key in seen:
                continue
            seen.append(key)
            self.notices = self.notices[-59:]
            self.add_notice(
                kind="event",
                title=f"{ev['icon']} {ev['title']} is starting",
                body=f"{ev['where']} · {ev['blurb']}",
                location=ev["venue"],
            )
            self.note(f"{ev['title']} tonight", f"{ev['blurb']} — {ev['where']}.", kind="event")
            if len(seen) > 80:
                del seen[:-80]

    def _event_pull(self, npc: NPC) -> dict | None:
        """A fixture this resident would plausibly wander into right now."""
        if npc.status in ("sleeping", "working"):
            return None
        hobbies = set(npc.hobbies)
        for ev in self.live_events():
            if ev["venue"] == npc.location_id:
                continue
            if not hobbies.intersection(ev["tags"]):
                continue
            # Deterministic turnout: about a third of the matching neighbours.
            if stable_hash("event-pull", npc.id, ev["id"], ev["due"]) % 3 != 0:
                continue
            return ev
        return None

    def _npc_think(self, npc: NPC) -> None:
        block = self._block_for(npc, self.hour_of_day)
        if not block:
            # Between scheduled things: stay put, be awake, do nothing in
            # particular. (Never "sleeping" — naps are a night activity.)
            if npc.status == "sleeping":
                npc.status = "at"
            if npc.status in ("at", "working"):
                npc.activity = "between things"
            npc.flags["block_key"] = "gap"
            return
        block_key = f"{block['start']}:{block['loc']}:{block['activity']}"
        if npc.flags.get("block_key") != block_key:
            npc.flags["block_key"] = block_key
            npc.schedule_activity = block["activity"]
            if block["kind"] == "sleep":
                npc.status = "sleeping"
                npc.target = None
                self._npc_paths.pop(npc.id, None)
                # walk home quickly by teleport only if far and nobody's watching (background sim)
                if npc.location_id != "home":
                    hx, hy = home_xy(npc.home_id)
                    if math.hypot(npc.x - hx, npc.y - hy) > 700 and not npc.spotlight:
                        npc.x, npc.y = hx, hy
                        npc.location_id = "home"
                    else:
                        tx, ty = venue_spot(npc, "home")
                        npc.target = {"x": tx, "y": ty, "loc": "home", "activity": "heading home"}
                return
            if block["kind"] == "work":
                npc.status = "working"
            if npc.location_id != block["loc"]:
                # exhausted or banned residents go home instead
                loc = block["loc"]
                if npc.mood.social_energy < 12 and loc not in ("home", "work"):
                    loc = "home"
                if npc.flags.get("banned_until", 0) > self.minute and loc == npc.flags.get("banned_from"):
                    loc = "home"
                tx, ty = venue_spot(npc, loc)
                npc.target = {"x": tx, "y": ty, "loc": loc, "activity": block["activity"]}
                npc.status = "walking"
            else:
                npc.activity = block["activity"]
                if npc.status != "working":
                    npc.status = "at"
        # A live fixture out-ranks idle time at home, but never work or sleep.
        ev = self._event_pull(npc)
        if ev and block["kind"] not in ("work", "sleep"):
            key = f"event:{ev['id']}:{ev['due']}"
            if npc.flags.get("block_key") != key:
                npc.flags["block_key"] = key
                npc.target = {
                    "x": 0.0, "y": 0.0, "loc": ev["venue"], "activity": ev["title"],
                    "event": ev["id"],
                }
                tx, ty = venue_spot(npc, ev["venue"])
                npc.target["x"], npc.target["y"] = tx, ty
                npc.status = "walking"

        # micro-decisions for foreground NPCs
        if npc.spotlight and npc.status in ("at", "working") and npc.energy > 25:
            if npc.next_decision == 0:
                npc.next_decision = self.minute + self.hub.stream(f"nd:{npc.id}").uniform(18, 50)
            if self.minute >= npc.next_decision:
                npc.next_decision = self.minute + self.hub.stream(f"nd2:{npc.id}").uniform(30, 90)
                rng = self.hub.stream(f"micro:{npc.id}:{int(self.minute)}")
                if rng.random() < 0.22 and npc.location_id != "home" and npc.mood.social_energy > 30:
                    nearby = [loc["id"] for loc in LOCATIONS
                              if loc["id"] != npc.location_id
                              and math.hypot(loc["x"] + loc["w"] / 2 - npc.x, loc["y"] + loc["h"] / 2 - npc.y) < 520]
                    if nearby:
                        loc = nearby[rng.randrange(len(nearby))]
                        tx, ty = venue_spot(npc, loc)
                        npc.target = {"x": tx, "y": ty, "loc": loc, "activity": "dropping by"}
                        npc.status = "walking"

    # ------------------------------------------------------------------
    # Needs
    # ------------------------------------------------------------------
    def _update_needs(self, npc: NPC, dt: float) -> None:
        m = npc.mood
        if npc.status == "sleeping":
            npc.energy = clamp(npc.energy + 0.10 * dt, 0, 100)
            m.stress = clamp(m.stress - 0.035 * dt, 0, 100)
            m.social_energy = clamp(m.social_energy + 0.05 * dt, 0, 100)
        elif npc.status == "working":
            npc.energy = clamp(npc.energy - 0.055 * dt, 0, 100)
            m.stress = clamp(m.stress + 0.030 * dt, 0, 100)
            m.social_energy = clamp(m.social_energy - 0.030 * dt, 0, 100)
        elif npc.location_id == "home":
            npc.energy = clamp(npc.energy + 0.030 * dt, 0, 100)
            m.stress = clamp(m.stress - 0.030 * dt, 0, 100)
            m.social_energy = clamp(m.social_energy + 0.055 * dt, 0, 100)
        else:
            npc.energy = clamp(npc.energy - 0.012 * dt, 0, 100)
            m.social_energy = clamp(m.social_energy - 0.045 * dt, 0, 100)
            m.stress = clamp(m.stress - 0.008 * dt, 0, 100)
        m.valence = clamp(m.valence + (0.008 - m.stress * 0.0004) * dt, -100, 100)
        m.irritation = clamp(m.irritation - 0.012 * dt, 0, 100)
        m.excitement = clamp(m.excitement + (1.0 if npc.location_id != "home" else -0.4) * 0.01 * dt, 0, 100)
        if npc.energy <= 12 and npc.status not in ("sleeping",) and npc.location_id != "home":
            npc.status = "walking"
            tx, ty = venue_spot(npc, "home")
            npc.target = {"x": tx, "y": ty, "loc": "home", "activity": "exhausted, heading home"}

    # ------------------------------------------------------------------
    # NPC-to-NPC life
    # ------------------------------------------------------------------
    def _npc_chat(self) -> None:
        awake = [n for n in self.npcs if n.status == "at" and n.location_id != "home" and n.mood.social_energy > 18]
        by_loc: dict[str, list[NPC]] = {}
        for n in awake:
            by_loc.setdefault(n.location_id, []).append(n)
        pairs = []
        for loc, crew in by_loc.items():
            for i, a in enumerate(crew):
                for b in crew[i + 1:]:
                    r = self.rel(a.id, b.id)
                    if r.get("familiarity", 0) >= 4 and r.get("tension", 0) < 80:
                        pairs.append((a, b, loc))
        if not pairs:
            return
        rng = self.hub.stream("npc-chat")
        a, b, loc = pairs[rng.randrange(len(pairs))]
        rel_ab = self.rel(a.id, b.id)
        friendly = rel_ab.get("affinity", 0) >= 0
        topic_key = rng.choice(["music", "food", "work", "weather", "community", "sports", "gossip"])
        ev = self.add_event(
            kind="npc_chat", actor=a.id, targets=[b.id], location=loc,
            facts={"topic": topic_key, "tone": "friendly" if friendly else "tense"},
            witnesses=[], visibility="local",
            summary=f"{a.first} and {b.first} talked about {topic_key} at {self.location_names.get(loc, loc)}.",
        )
        for speaker in (a, b):
            self.remember(speaker, ev, importance=0.18, valence=0.1 if friendly else -0.1, source="participated")
        if friendly:
            self.adjust_rel(a.id, b.id, familiarity=rng.uniform(1.2, 3.2), affinity=rng.uniform(0.4, 2.0),
                            trust=rng.uniform(0.2, 1.0))
            self.adjust_rel(b.id, a.id, familiarity=rng.uniform(1.0, 3.0), affinity=rng.uniform(0.3, 2.0),
                            trust=rng.uniform(0.2, 1.0))
        else:
            self.adjust_rel(a.id, b.id, familiarity=1.0, tension=rng.uniform(0.5, 2.0))
            self.adjust_rel(b.id, a.id, familiarity=1.0, tension=rng.uniform(0.5, 2.0))
        # rumor transmission
        for speaker, listener in ((a, b), (b, a)):
            beliefs = [bl for bl in speaker.beliefs if bl.confidence >= 0.35]
            if not beliefs:
                continue
            rumor = next((r for r in self.rumors if r["id"] == beliefs[-1].rumor_id), None)
            if rumor:
                self.spread_rumor_social(speaker, listener, rumor)

    def _background_rumor_spread(self) -> None:
        holders = [(n, bl) for n in self.npcs for bl in n.beliefs if bl.confidence >= 0.4]
        if not holders:
            return
        rng = self.hub.stream("rumor-bg")
        speaker, belief = holders[rng.randrange(len(holders))]
        rumor = next((r for r in self.rumors if r["id"] == belief.rumor_id), None)
        if not rumor:
            return
        friends = [oid for oid, r in self.outgoing_rels(speaker.id)
                   if oid.startswith("npc_") and r.get("familiarity", 0) > 25]
        candidates = [self.npc(oid) for oid in friends]
        candidates = [c for c in candidates if c and not any(b.rumor_id == rumor["id"] for b in c.beliefs)]
        if not candidates:
            return
        listener = candidates[rng.randrange(len(candidates))]
        self._teach_rumor(listener, rumor, source_id=speaker.id, confidence=belief.confidence * 0.7)

    # ------------------------------------------------------------------
    # Ambient social media & messages
    # ------------------------------------------------------------------
    def _ambient_post(self) -> None:
        if self.hour_of_day < 7 or self.hour_of_day > 23:
            return
        awake = [n for n in self.npcs if n.status != "sleeping" and n.mood.social_energy > 25]
        if not awake:
            return
        rng = self.hub.stream("ambient-post")
        npc = awake[rng.randrange(len(awake))]
        mood = npc.mood.label()
        kind = "evening" if self.hour_of_day >= 18 else "morning"
        if mood in ("low",):
            text = POST_TEMPLATES["mood_low"][rng.randrange(len(POST_TEMPLATES["mood_low"]))]
        elif mood in ("buzzing", "excited", "cheerful"):
            text = POST_TEMPLATES["mood_high"][rng.randrange(len(POST_TEMPLATES["mood_high"]))]
        elif npc.status == "working":
            text = POST_TEMPLATES["work"][rng.randrange(len(POST_TEMPLATES["work"]))]
        elif npc.hobbies[0] in ("music",):
            text = POST_TEMPLATES["music"][rng.randrange(len(POST_TEMPLATES["music"]))]
        elif rng.random() < 0.35:
            text = ARCHETYPE_POSTS[npc.archetype][rng.randrange(len(ARCHETYPE_POSTS[npc.archetype]))]
        elif rng.random() < 0.4:
            text = POST_BY_LOCATION.get(npc.location_id, POST_TEMPLATES[kind][0])
        else:
            text = POST_TEMPLATES[kind][rng.randrange(len(POST_TEMPLATES[kind]))]
        text = (text.replace("{venue}", self.location_names.get(npc.location_id, "the block"))
                    .replace("{food}", npc.favorite_food)
                    .replace("{music}", npc.favorite_music)
                    .replace("{friend}", npc.first))
        recent = self.world_flags.setdefault("recent_post_texts", [])
        tries = 0
        while text in recent and tries < 4:
            tries += 1
            alt = POST_TEMPLATES["evening" if kind == "evening" else "morning"]
            text = alt[rng.randrange(len(alt))].replace(
                "{venue}", self.location_names.get(npc.location_id, "the block")
            ).replace("{food}", npc.favorite_food)
        if text in recent:
            return
        recent.append(text)
        del recent[:-14]
        self.push_feed(author_id=npc.id, text=text, mood=mood, tag="life", loc=npc.location_id)

    def send_npc_message(self, npc_id: str, text: str, *, kind: str = "text", meta: dict | None = None,
                         unread: bool = True) -> Message:
        thread = self.threads.setdefault(npc_id, Thread(npc_id=npc_id))
        msg = Message(id=new_id("msg"), sender=npc_id, text=text[:config.MAX_MESSAGE_LENGTH],
                      minute=self.minute, read=not unread, kind=kind, meta=meta or {})
        thread.messages.append(msg)
        thread.messages = thread.messages[-config.THREAD_CAP:]
        self.metrics["messages"] += 1
        self._dirty = True
        return msg

    def _ambient_message(self) -> None:
        if self.hour_of_day < 8 or self.hour_of_day > 22:
            return
        candidates = []
        for n in self.npcs:
            r = self.rel(n.id, "player")
            if r.get("familiarity", 0) >= 8 and n.status != "sleeping" and n.mood.social_energy > 35:
                candidates.append(n)
        if not candidates:
            return
        rng = self.hub.stream("ambient-message")
        npc = candidates[rng.randrange(len(candidates))]
        pool = MESSAGE_TEMPLATES[npc.archetype]
        text = pool[rng.randrange(len(pool))]
        text = (text.replace("{venue}", self.location_names.get(npc.location_id, "the block"))
                    .replace("{food}", npc.favorite_food))
        # late reply flavour if the player recently messaged
        self.send_npc_message(npc.id, text)
        self.note(f"Message from {npc.first}", text[:120], kind="message")

    def _maybe_incoming_call(self) -> None:
        if self.world_flags.get("pending_call"):
            return
        if self.hour_of_day < 8 or self.hour_of_day > 22.5:
            return
        candidates = []
        for n in self.npcs:
            r = self.rel(n.id, "player")
            if r.get("familiarity", 0) >= 30 and n.status != "sleeping" and n.mood.social_energy > 30:
                candidates.append(n)
        if not candidates:
            return
        rng = self.hub.stream("incoming-call")
        if rng.random() > 0.5:
            return
        npc = candidates[rng.randrange(len(candidates))]
        call_id = new_id("call")
        self.world_flags["pending_call"] = {
            "call_id": call_id, "npc_id": npc.id, "created": round(self.minute, 1),
            "expires": round(self.minute + 22, 1),
        }
        self.note(f"Incoming call from {npc.first}", f"{npc.first} is calling you.", kind="call")

    def _resolve_pending_calls(self) -> None:
        pending = self.world_flags.get("pending_call")
        if not pending:
            return
        if self.minute > pending["expires"]:
            npc = self.npc(pending["npc_id"])
            self.world_flags["pending_call"] = None
            if npc:
                line = MISSED_CALL_LINES.get(npc.archetype, "You missed my call — call me back when you can.")
                self.send_npc_message(npc.id, line, kind="missed_call",
                                      meta={"missed": True, "call_id": pending["call_id"]})
                self.note("Missed call", f"You missed a call from {npc.first}.", kind="missed_call")

    # ------------------------------------------------------------------
    # Date plans
    # ------------------------------------------------------------------
    def _resolve_date_plans(self) -> None:
        for npc in self.npcs:
            for plan in npc.plans:
                if plan.get("kind") != "date" or plan.get("done"):
                    continue
                if self.minute >= plan.get("due", 1e9) - 10 and npc.location_id != plan.get("venue"):
                    self.force_move(npc, plan.get("venue", "cafe"))
                if self.minute >= plan.get("due", 1e9) + 45:
                    plan["done"] = True

    # ------------------------------------------------------------------
    # Time
    # ------------------------------------------------------------------
    def tick(self, real_dt: float) -> None:
        """Real-time tick driven by the server loop."""
        self._move_player(real_dt)
        if self.speed <= 0:
            return
        game_dt = min(real_dt * float(self.speed) * 1.0, 2.0)
        self.advance(game_dt)

    def advance(self, minutes: float) -> None:
        remaining = max(0.0, float(minutes))
        while remaining > 1e-9:
            dt = min(1.0, remaining)
            remaining -= dt
            self._step(dt)

    def skip_minutes(self, minutes: float) -> list[dict]:
        """Advance the world quickly; returns notable new notices for the client."""
        before = len(self.notices)
        self.advance(minutes)
        return self.notices[before:][-4:]

    def _step(self, dt: float) -> None:
        prev_day = self.day_index
        prev_hour = self.hour_of_day
        self.minute += dt
        day = self.day_index
        hour = self.hour_of_day

        if day != prev_day:
            self.world_flags["weather"] = self._weather_for_day(day)
            self.world_flags["last_day_tick"] = day
            director.tick_days(self)
            self.note("A new day", f"{self.clock_label()} — the block is waking up.", kind="day")

        self._announce_events()

        for npc in self.npcs:
            self._npc_think(npc)
            self._update_needs(npc, dt)
        self._move_npcs(dt)

        # daily money events at 09:00
        if hour >= 9.0 > prev_hour or (prev_hour > hour and hour >= 9.0):
            self._daily_money()
        if hour >= 18.0 > prev_hour or (prev_hour > hour and hour >= 18.0):
            self._daily_income()

        # timers
        wf = self.world_flags
        if self.minute >= wf.get("next_feed_minute", 0):
            self._ambient_post()
            rng = self.hub.stream("feed-cadence")
            wf["next_feed_minute"] = self.minute + rng.uniform(45, 115)
        if self.minute >= wf.get("next_npc_chat_minute", 0):
            self._npc_chat()
            rng = self.hub.stream("chat-cadence")
            wf["next_npc_chat_minute"] = self.minute + rng.uniform(14, 36)
        if self.minute >= wf.get("next_ambient_minute", 0):
            director.run_ambient(self)
            wf["next_ambient_minute"] = self.minute + self.hub.stream("amb-cadence").uniform(150, 280)
        if self.minute >= wf.get("next_director_minute", 0):
            director.run_director(self)
            wf["next_director_minute"] = self.minute + 60
        if self.minute >= wf.get("next_rumor_minute", 0):
            if self.hub.stream("rumor-gate").random() < 0.4:
                self._background_rumor_spread()
            wf["next_rumor_minute"] = self.minute + 110
        if self.minute >= wf.get("next_message_minute", 0):
            self._ambient_message()
            wf["next_message_minute"] = self.minute + self.hub.stream("msg-cadence").uniform(90, 170)
        if self.minute >= wf.get("next_call_minute", 0):
            self._maybe_incoming_call()
            wf["next_call_minute"] = self.minute + self.hub.stream("call-cadence").uniform(150, 260)
        chaos.maybe_escalate(self)
        self._resolve_pending_calls()
        self._resolve_date_plans()
        self._deliver_pending_messages()

    def _deliver_pending_messages(self) -> None:
        pending = self.world_flags.get("pending_messages", [])
        if not pending:
            return
        remaining = []
        for item in pending:
            if self.minute < item["due"]:
                remaining.append(item)
                continue
            npc = self.npc(item["npc_id"])
            if not npc:
                continue
            if npc.status == "sleeping":
                item["due"] = self.minute + 240
                remaining.append(item)
                continue
            from blxverse.engine.composer import compose_message_reply
            reply = compose_message_reply(npc=npc, player=self.player, rel=self._rel_obj(npc.id),
                                          text=item["text"], hub=self.hub, location_names=self.location_names)
            self.send_npc_message(npc.id, reply)
            self.adjust_rel(npc.id, "player", familiarity=1.2, affinity=0.6, trust=0.4, count_interaction=True)
            self.adjust_rel("player", npc.id, familiarity=1.2, affinity=0.6, trust=0.4)
            self.note(f"Reply from {npc.first}", reply[:140], kind="message")
        self.world_flags["pending_messages"] = remaining[-20:]

    def _rel_obj(self, npc_id: str) -> Relationship:
        return Relationship.from_dict(self.rel(npc_id, "player"))

    # ------------------------------------------------------------------
    # Money
    # ------------------------------------------------------------------
    def _txn(self, actor_id: str, amount: int, category: str, memo: str,
             counterparty: str | None = None) -> dict:
        """Apply a signed transaction to the player wallet with audit logging."""
        p = self.player
        if p is None:
            raise SimError("No player", "no_player")
        try:
            if amount < 0:
                economy.authorize_spend(p.wallet, -amount)
            else:
                economy.credit(p.wallet, amount)
            entry = economy.make_entry(minute=self.minute, actor_id=actor_id, amount=amount,
                                       balance_after=p.wallet + amount, category=category,
                                       memo=memo, counterparty=counterparty)
        except EconomyError as exc:
            message = str(exc)
            code = "insufficient_funds" if "insufficient" in message else (
                "limit" if "limit" in message or "exceeds" in message else "bad_transaction")
            raise SimError(message.capitalize() + ".", code, 422) from None
        p.wallet += amount
        entry["balance_after"] = p.wallet
        p.ledger.append(entry)
        p.ledger = p.ledger[-config.MAX_LEDGER_ENTRIES:]
        economy.audit({"kind": "player_txn", "seed": self.seed, "minute": self.minute, **entry})
        self._dirty = True
        return entry

    def player_spend(self, amount: int, category: str, memo: str, counterparty: str | None = None) -> dict:
        return self._txn("player", -int(amount), category, memo, counterparty)

    def player_earn(self, amount: int, category: str, memo: str, counterparty: str | None = None) -> dict:
        return self._txn("player", int(amount), category, memo, counterparty)

    def _daily_money(self) -> None:
        wf = self.world_flags
        day = self.day_index
        if wf.get("last_rent_day") == day:
            return
        wf["last_rent_day"] = day
        p = self.player
        due = config.DAILY_RENT
        if p.wallet >= due:
            self.player_spend(due, "rent", f"Rent for {self.clock_label()} (day {self.day_number})", "landlord")
        else:
            p.mood.stress = clamp(p.mood.stress + 12, 0, 100)
            p.reputation = clamp(p.reputation - 1, 0, 100)
            self.note("Rent is due", "You didn't have enough BLX for rent. Pay when you can — the landlord noticed.", kind="money")
            self.add_notice(kind="alert", title="Rent reminder",
                            body="A resident is short on rent this week. The landlord has been seen with a clipboard.",
                            location="home")
        if self.day_index % 7 != 5 and self.day_index % 7 != 6:
            for npc in self.npcs:
                due_npc = int(npc.bills_due)
                if npc.wallet >= due_npc:
                    npc.wallet -= due_npc
                    npc.mood.stress = clamp(npc.mood.stress - 2, 0, 100)
                else:
                    npc.mood.stress = clamp(npc.mood.stress + 14, 0, 100)
                    npc.mood.valence = clamp(npc.mood.valence - 5, -100, 100)
                    landlord = self.npc_by_flag("landlord")
                    if landlord and npc.id != landlord.id:
                        self.adjust_rel(landlord.id, npc.id, tension=3)
                        self.adjust_rel(npc.id, landlord.id, tension=3)

    def _daily_income(self) -> None:
        wf = self.world_flags
        day = self.day_index
        if wf.get("last_income_day") == day:
            return
        wf["last_income_day"] = day
        p = self.player
        for npc in self.npcs:
            if npc.occupation == "unemployed":
                continue
            pay = int(npc.salary / 6 * (0.8 if self.day_index % 7 >= 5 else 1.0))
            npc.wallet += max(20, pay)
            if npc.flags.get("has_business"):
                income = 18 + (int(self.hub.stream(f"biz:{npc.id}").random() * 22))
                npc.wallet += income
        if p and p.flags.get("cart_owned"):
            base = config.STREET_CART_DAILY_BASE + int(p.reputation / 10)
            self.player_earn(base, "business", "Street cart earnings", "street_cart")
            self.note("Street cart earnings", f"Your cart brought in {base} BLX today.", kind="money")

    def host_ambient(self, event: dict) -> None:
        """A neighborhood happening: notice, gathering, feed noise, memories."""
        loc = event.get("loc", "square")
        loc_name = self.location_names.get(loc, "the block")
        self.add_notice(kind="event", title=event.get("title", "Neighborhood event"),
                        body=event.get("body", ""), location=loc)
        awake = [n for n in self.npcs if n.status != "sleeping"]
        rng = self.hub.stream("host-ambient")
        attendees = [n for n in awake if n.spotlight][:6]
        for n in attendees:
            self.force_move(n, loc)
            n.mood.social_energy = clamp(n.mood.social_energy + 4, 0, 100)
        ev = self.add_event(kind="ambient_event", actor=attendees[0].id if attendees else "system",
                            targets=[n.id for n in attendees], location=loc,
                            facts={"event": event.get("id"), "title": event.get("title")},
                            witnesses=[n.id for n in attendees], visibility="public",
                            summary=f"{event.get('title', 'A neighborhood event')} at {loc_name}.")
        for n in attendees:
            self.remember(n, ev, importance=0.3, valence=0.5, source="participated")
            for other in attendees:
                if other.id != n.id:
                    self.adjust_rel(n.id, other.id, familiarity=1.2, affinity=0.8)
        if attendees:
            self.push_feed(author_id=attendees[rng.randrange(len(attendees))].id,
                           text=event.get("feed", f"Something's happening at {loc_name}."),
                           mood="buzzed", tag="events", loc=loc)
        self.note(event.get("title", "Neighborhood event"),
                  f"{event.get('title', 'Something')} is happening at {loc_name}.", kind="event")
        self.world_flags["ambient_host"] = {"loc": loc, "title": event.get("title"), "minute": self.minute}

    # ------------------------------------------------------------------
    # Voice metrics
    # ------------------------------------------------------------------
    def log_voice_metric(self, stage: str, ms: float, meta: dict | None = None) -> None:
        metric = {"stage": str(stage)[:40], "ms": round(float(ms), 1),
                  "minute": round(self.minute, 1), "at": time.time(), "meta": meta or {}}
        metrics = self.metrics.setdefault("voice_metrics", [])
        metrics.append(metric)
        del metrics[:-config.VOICE_METRIC_CAP]

    def log_metric(self, name: str, data: dict | None = None) -> None:
        bucket = self.metrics.setdefault(name, [])
        if isinstance(bucket, list):
            bucket.append({"minute": round(self.minute, 1), **(data or {})})
            del bucket[:-120]

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------
    def _npc_save(self, npc: NPC) -> dict:
        d = npc.to_dict(include_memory=False)
        d["memory_full"] = [m.to_dict() for m in npc.memory]
        d["beliefs_full"] = [b.to_dict() for b in npc.beliefs]
        return d

    def to_save(self) -> dict:
        p = self.player
        return {
            "format": config.SAVE_FORMAT,
            "schema": self.schema,
            "version": config.VERSION,
            "seed": self.seed,
            "created_at": self.created_at,
            "saved_at": time.time(),
            "minute": self.minute,
            "speed": self.speed,
            "npcs": [self._npc_save(n) for n in self.npcs],
            "player": p.to_dict() if p else None,
            "rels": self.rels,
            "posts": [post.to_dict() for post in self.posts],
            "threads": {k: t.to_dict() for k, t in self.threads.items()},
            "notifications": self.notifications,
            "notices": self.notices,
            "events": self.events,
            "rivalries": [r.to_dict() for r in self.rivalries],
            "cases": [c.to_dict() for c in self.cases],
            "arcs": [a.to_dict() for a in self.arcs],
            "rumors": self.rumors,
            "world_flags": self.world_flags,
            "metrics": self.metrics,
        }

    def save(self, force: bool = False) -> None:
        if not self.save_path:
            return
        now = time.time()
        if not force and now - self.last_save_real < 8:
            return
        os.makedirs(os.path.dirname(self.save_path), exist_ok=True)
        tmp = self.save_path + ".tmp"
        data = self.to_save()
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, separators=(",", ":"))
        if os.path.exists(self.save_path):
            try:
                os.replace(self.save_path, self.save_path + ".bak")
            except OSError:
                pass
        os.replace(tmp, self.save_path)
        self.last_save_real = now
        self._dirty = False

    @classmethod
    def load(cls, path: str) -> Simulation:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        if data.get("format") != config.SAVE_FORMAT:
            raise SimError("Save file is not a BLXVERSE save", "bad_save", 500)
        if int(data.get("schema", -1)) != config.SCHEMA_VERSION:
            raise SimError("Save schema mismatch — start a new world or migrate", "schema_mismatch", 500)
        sim = cls(seed=int(data["seed"]), save_path=path)
        sim.created_at = float(data.get("created_at", time.time()))
        sim.minute = float(data.get("minute", config.DAY_START_MINUTE))
        sim.speed = int(data.get("speed", 1))
        sim.npcs = [NPC.from_dict(d) for d in data["npcs"]]
        sim.by_id = {n.id: n for n in sim.npcs}
        sim.player = Player.from_dict(data["player"]) if data.get("player") else None
        sim.rels = data.get("rels", {})
        sim.posts = [_post_from_dict(d) for d in data.get("posts", [])]
        sim.threads = {k: _thread_from_dict(d) for k, d in data.get("threads", {}).items()}
        sim.notifications = data.get("notifications", [])
        sim.notices = data.get("notices", [])
        sim.events = data.get("events", [])
        sim.rivalries = [_obj_from_dict(Rivalry, d) for d in data.get("rivalries", [])]
        sim.cases = [_obj_from_dict(Case, d) for d in data.get("cases", [])]
        sim.arcs = [_obj_from_dict(Arc, d) for d in data.get("arcs", [])]
        sim.rumors = data.get("rumors", [])
        sim.world_flags = data.get("world_flags", {})
        sim.metrics = data.get("metrics", sim.metrics)
        sim.metrics.setdefault("voice_metrics", [])
        sim.world_flags.setdefault("pending_messages", [])
        # NPC transient fields
        for npc in sim.npcs:
            npc.next_decision = 0.0
            npc.home_xy = home_xy(npc.home_id)
        sim.last_save_real = time.time()
        return sim

    # ------------------------------------------------------------------
    # Payloads for the client
    # ------------------------------------------------------------------
    def clock_payload(self) -> dict:
        h = int(self.hour_of_day)
        m = int((self.hour_of_day - h) * 60)
        return {
            "minute": round(self.minute, 2), "day": self.day_number, "weekday": self.weekday,
            "hour": h, "minute_of_hour": m, "time": f"{h:02d}:{m:02d}",
            "label": self.time_label(), "speed": self.speed,
            "weather": self.world_flags.get("weather", "clear skies"),
            "is_weekend": self.day_index % 7 >= 5,
        }

    def _npc_core(self, npc: NPC) -> dict:
        rel = self.rel(npc.id, "player")
        relationship = Relationship.from_dict(rel)
        return {
            "id": npc.id, "name": npc.name, "first": npc.first, "last": npc.last,
            "x": round(npc.x, 1), "y": round(npc.y, 1), "loc": npc.location_id,
            "status": npc.status,
            "activity": ("heading to " + self.location_names.get(npc.location_id, "somewhere"))
                        if npc.status == "walking" else npc.activity,
            "archetype": npc.archetype,
            "look": npc.look, "spotlight": npc.spotlight,
            "mood": npc.mood.label(), "mood_valence": round(npc.mood.valence, 1),
            "gender": npc.gender, "occupation": npc.occupation, "age": npc.age,
            "voice": npc.voice, "hobbies": npc.hobbies,
            "rel": {"label": relationship.label(), "affinity": round(rel.get("affinity", 0), 1),
                    "familiarity": round(rel.get("familiarity", 0), 1),
                    "romance": round(rel.get("romance", 0), 1),
                    "tension": round(rel.get("tension", 0), 1)},
        }

    def state_payload(self) -> dict:
        p = self.player
        if p is None:
            return {"setup": True}
        live_events = self.live_events()
        fg = nearby = bg = 0
        for npc in self.npcs:
            d = math.hypot(npc.x - p.x, npc.y - p.y)
            if d <= config.FOREGROUND_RADIUS:
                fg += 1
            elif d <= config.NEARBY_RADIUS:
                nearby += 1
            else:
                bg += 1
        unread_msgs = sum(1 for t in self.threads.values() for m in t.messages if not m.read)
        unread_notes = sum(1 for n in self.notifications if not n.get("read"))
        voice = self.metrics.get("voice_metrics", [])
        e2e = [m["ms"] for m in voice if m.get("stage") in ("e2e_first_audio", "end_to_first_audio")]
        return {
            "setup": False,
            "clock": self.clock_payload(),
            "player": {
                "name": p.name, "x": round(p.x, 1), "y": round(p.y, 1), "wallet": p.wallet,
                "energy": round(p.energy, 1), "reputation": round(p.reputation, 1),
                "mood": p.mood.label(), "mood_valence": round(p.mood.valence, 1),
                "look": p.look, "gender": p.gender, "home_id": p.home_id, "age": p.age,
                "first": p.name.split(" ")[0] if p.name else "You",
                "occupation": p.occupation, "pronouns": p.pronouns,
                "inventory": p.inventory, "flags": {k: v for k, v in p.flags.items() if k != "journal"},
                "moving": self._player_dest is not None,
                **self.player_route_payload(),
            },
            "npcs": [self._npc_core(n) for n in self.npcs],
            "nearby": [n.id for n in sorted(self.npcs, key=lambda n: math.hypot(n.x - p.x, n.y - p.y))[:10]],
            "unread": {"messages": unread_msgs, "notifications": unread_notes},
            "notifications": [n for n in self.notifications if not n.get("read")][-8:],
            "notices": self.notices[-6:],
            "pending_call": self.world_flags.get("pending_call"),
            "date_offers": [
                d for d in self.world_flags.get("date_offers", [])
                if d["expires"] > self.minute and d["status"] == "accepted"
            ],
            "arcs": [a.to_dict() for a in self.arcs if a.status == "active"],
            "cases": [c.to_dict() for c in self.cases if c.status == "open"],
            "tiers": {"foreground": fg, "nearby": nearby, "background": bg},
            "voice": {
                "samples": len(e2e),
                "p50": _percentile(e2e, 50), "p95": _percentile(e2e, 95),
                "target_ms": config.VOICE_TARGET_MS,
            },
            "metrics": {
                "events": self.metrics.get("events", 0),
                "posts": self.metrics.get("posts", 0),
                "messages": self.metrics.get("messages", 0),
                "dialogue_turns": self.metrics.get("dialogue_turns", 0),
                "chaos_scenes": self.metrics.get("chaos_scenes", 0),
                "rumor_spreads": self.metrics.get("rumor_spreads", 0),
            },
            "last_event": self.events[-1] if self.events else None,
            "live_events": live_events,
            "chain": self.world_flags.get("chain", {}),
        }

    def world_payload(self) -> dict:
        return {
            "seed": self.seed,
            "version": config.VERSION,
            "config": {
                "world_width": config.WORLD_WIDTH, "world_height": config.WORLD_HEIGHT,
                "interact_radius": config.INTERACT_RADIUS, "talk_radius": config.TALK_RADIUS,
                "player_speed": config.PLAYER_MAX_SPEED, "rent": config.DAILY_RENT,
                "start_balance": config.STARTING_BALANCE, "npcs": len(self.npcs),
                "spotlight": config.SPOTLIGHT_COUNT, "cart_cost": config.STREET_CART_COST,
            },
            "locations": LOCATIONS,
            "homes": [{"id": i, "x": h[0], "y": h[1], "color": h[2]} for i, h in enumerate(HOMES)],
            "items": ITEMS,
            "menu": CONSUMABLES_LIST,
            "npcs": [n.to_dict(include_memory=False) for n in self.npcs],
            "playable": {"genders": ["female", "male"], "pronouns": {"female": "she/her", "male": "he/him"}},
            "disclaimer": "All residents are fictional simulations. BLX is a closed-loop fictional credit with no cash value.",
        }

    def npc_payload(self, npc_id: str) -> dict:
        npc = self.npc(npc_id)
        if not npc:
            raise SimError("Resident not found", "not_found", 404)
        rel = self.rel(npc.id, "player")
        my_rel = self.rel("player", npc.id)
        relationship = Relationship.from_dict(rel)
        connections = []
        for other_id, r in self.outgoing_rels(npc.id):
            other = self.npc(other_id)
            if other:
                connections.append({
                    "id": other.id, "name": other.name, "label": Relationship.from_dict(r).label(),
                    "affinity": round(r.get("affinity", 0), 1), "familiarity": round(r.get("familiarity", 0), 1),
                })
        connections.sort(key=lambda c: -c["affinity"])
        pc_memories = [m.to_dict() for m in npc.memory if "player" in m.with_ids or m.kind in
                       ("talk", "gift", "date", "call", "apology")][-14:]
        return {
            **npc.to_dict(include_memory=False),
            "relationship": {
                "label": relationship.label(), "familiarity": round(rel.get("familiarity", 0), 1),
                "trust": round(rel.get("trust", 0), 1), "affinity": round(rel.get("affinity", 0), 1),
                "romance": round(rel.get("romance", 0), 1), "tension": round(rel.get("tension", 0), 1),
                "interactions": rel.get("interactions", 0), "flags": rel.get("flags", []),
                "dates": rel.get("dates", 0), "your_view": Relationship.from_dict(my_rel).label(),
            },
            "memory_of_you": pc_memories,
            "beliefs": [b.to_dict() for b in npc.beliefs],
            "connections": connections[:12],
            "archetype_label": ARCHETYPES.get(npc.archetype, {}).get("label", npc.archetype),
            "archetype_blurb": ARCHETYPES.get(npc.archetype, {}).get("blurb", ""),
            "known_locations": [loc["id"] for loc in LOCATIONS if loc["hours"][0] <= self.hour_of_day <= loc["hours"][1]],
        }

    def feed_payload(self, limit: int = config.FEED_PAGE) -> dict:
        def author(aid: str) -> dict:
            if aid == "player":
                return {"id": "player", "name": self.player.name if self.player else "You",
                        "first": self.player.name if self.player else "You", "look": self.player.look if self.player else {}}
            n = self.npc(aid)
            return {"id": aid, "name": n.name if n else "Unknown", "first": n.first if n else "Unknown",
                    "look": n.look if n else {}, "archetype": n.archetype if n else ""}
        posts = list(reversed(self.posts))[:limit]
        return {
            "posts": [{
                **p.to_dict(),
                "author_profile": author(p.author_id),
                "likes_named": [author(i)["first"] for i in p.likes[:6]],
                "comments_named": [{
                    **c.to_dict(), "author_profile": author(c.author_id),
                } for c in p.comments],
            } for p in posts],
            "notices": list(reversed(self.notices))[:16],
            "trending": self._trending(),
        }

    def _trending(self) -> list[dict]:
        counts: dict[str, int] = {}
        for p in self.posts[-60:]:
            if p.tag:
                counts[p.tag] = counts.get(p.tag, 0) + 1
        return [{"tag": k, "count": v} for k, v in sorted(counts.items(), key=lambda kv: -kv[1])[:6]]

    def thread_payload(self, npc_id: str, mark_read: bool = False) -> dict:
        npc = self.npc(npc_id)
        if not npc:
            raise SimError("Resident not found", "not_found", 404)
        thread = self.threads.get(npc_id)
        messages = thread.messages[-60:] if thread else []
        if mark_read:
            for m in messages:
                m.read = True
            self._dirty = True
        rel = Relationship.from_dict(self.rel(npc_id, "player"))
        return {
            "npc": {"id": npc.id, "name": npc.name, "first": npc.first, "look": npc.look,
                    "archetype": npc.archetype, "occupation": npc.occupation, "status": npc.status},
            "relationship": {"label": rel.label(), "familiarity": round(rel.familiarity, 1),
                             "trust": round(rel.trust, 1), "romance": round(rel.romance, 1),
                             "affinity": round(rel.affinity, 1), "tension": round(rel.tension, 1)},
            "messages": [m.to_dict() for m in messages],
            "can_call": rel.familiarity >= config.CALL_MIN_FAMILIARITY,
        }

    def threads_payload(self) -> dict:
        p = self.player
        if not p:
            return {"threads": [], "contacts": []}
        threads = []
        for npc_id, thread in self.threads.items():
            npc = self.npc(npc_id)
            if not npc or not thread.messages:
                continue
            last = thread.messages[-1]
            unread = sum(1 for m in thread.messages if not m.read and m.sender != "player")
            rel = Relationship.from_dict(self.rel(npc_id, "player"))
            threads.append({
                "npc_id": npc_id, "name": npc.name, "first": npc.first, "look": npc.look,
                "archetype": npc.archetype, "status": npc.status, "location": npc.location_id,
                "last": last.to_dict(), "unread": unread,
                "relationship": rel.label(), "familiarity": round(rel.familiarity, 1),
                "can_call": rel.familiarity >= config.CALL_MIN_FAMILIARITY,
                "voice": npc.voice,
            })
        threads.sort(key=lambda t: t["last"]["minute"], reverse=True)
        contacts = []
        for npc in self.npcs:
            fam = self.rel(npc.id, "player").get("familiarity", 0)
            if fam > 0 or npc.spotlight:
                contacts.append({
                    "id": npc.id, "name": npc.name, "first": npc.first, "look": npc.look,
                    "archetype": npc.archetype, "familiarity": round(fam, 1),
                    "label": Relationship.from_dict(self.rel(npc.id, "player")).label(),
                    "can_call": fam >= config.CALL_MIN_FAMILIARITY,
                })
        contacts.sort(key=lambda c: (-c["familiarity"], c["name"]))
        return {"threads": threads, "contacts": contacts[:40]}

    def live_events(self) -> list[dict]:
        """Live fixtures, cached per game-minute (called once per resident)."""
        stamp = (self.minute, self.day_index)
        if getattr(self, "_live_stamp", None) != stamp:
            self._live = event_calendar.live_events(self.minute)
            self._live_stamp = stamp
        return self._live

    def events_payload(self) -> dict:
        """The block calendar: live now, the week ahead, and birthdays."""
        now = self.minute
        live = self.live_events()
        upcoming = event_calendar.upcoming_events(now)
        for ev in upcoming:
            ev["live"] = any(item["id"] == ev["id"] and item["due"] == ev["due"] for item in live)
        for ev in live:
            ev["live"] = True
        people = []
        for npc in sorted(self.npcs, key=lambda n: event_calendar.next_birthday(n.id, now)):
            fam = self.rel(npc.id, "player").get("familiarity", 0)
            if fam <= 0 and not npc.spotlight:
                continue  # the named cast you'd recognise; plus anyone you've met
            people.append({
                "npc_id": npc.id, "name": npc.name, "first": npc.first,
                "due": event_calendar.next_birthday(npc.id, now),
                "age": npc.age + 1, "look": npc.look,
            })
        return {
            "now": now, "weekday": self.weekday, "day": self.day_index + 1,
            "live": live, "upcoming": upcoming[:14], "birthdays": people[:12],
        }

    def journal_payload(self) -> dict:
        p = self.player
        if not p:
            return {"journal": [], "memories": []}
        upcoming = []
        for offer in self.world_flags.get("date_offers", []):
            if offer.get("status") == "accepted" and offer.get("expires", 0) > self.minute:
                npc = self.npc(offer.get("npc_id", ""))
                upcoming.append({
                    "kind": "date", "title": f"Date with {npc.first if npc else 'someone'}",
                    "where": self.location_names.get(offer.get("venue", ""), "the block"),
                    "due": offer.get("due", 0),
                })
        for npc in self.npcs:
            for plan in npc.plans:
                if plan.get("done") or plan.get("with") != "player":
                    continue
                if plan.get("due", 0) > self.minute:
                    upcoming.append({
                        "kind": plan.get("kind", "plan"),
                        "title": plan.get("title", "a plan"),
                        "where": self.location_names.get(plan.get("venue", ""), ""),
                        "due": plan.get("due", 0),
                    })
        # Weekly fixtures (Open Mic Night, Market Day…) and neighbours'
        # birthdays, so "Coming up" is a real calendar rather than only
        # dates the player already agreed to.
        now = self.minute
        for ev in self.live_events():
            upcoming.append({
                "kind": "event", "id": ev["id"], "icon": ev["icon"],
                "title": f"{ev['title']} — on now", "where": ev["where"],
                "venue": ev["venue"], "due": now, "detail": f"started {clock_label_for(ev['due'])}",
                "blurb": ev["blurb"], "live": True,
            })
        for ev in event_calendar.upcoming_events(now):
            upcoming.append({
                "kind": "event", "id": ev["id"], "icon": ev["icon"],
                "title": ev["title"], "where": ev["where"], "venue": ev["venue"],
                "due": ev["due"], "detail": ev["detail"], "blurb": ev["blurb"],
                "live": False,
            })
        for npc in self.npcs:
            if self.rel(npc.id, "player").get("familiarity", 0) < 6:
                continue  # you only get invited to parties you'd recognise
            due = event_calendar.next_birthday(npc.id, now)
            upcoming.append({
                "kind": "birthday", "id": f"bday_{npc.id}", "icon": "🎂",
                "title": f"{npc.first}'s birthday", "where": "somewhere on the block",
                "due": due, "detail": f"they turn {npc.age + 1}",
            })
        seen = set()
        deduped = []
        for item in sorted(upcoming, key=lambda u: u["due"]):
            key = (item.get("kind"), item.get("title"), item.get("due"))
            if key in seen:
                continue
            seen.add(key)
            deduped.append(item)
        upcoming = deduped
        return {
            "journal": list(reversed(p.flags.get("journal", [])[-80:])),
            "upcoming": upcoming[:14],
            "memories": int(p.stats.get("memories", 0)),
            "ledger": list(reversed(p.ledger[-40:])),
            "stats": {
                "reputation": round(p.reputation, 1), "energy": round(p.energy, 1),
                "wallet": p.wallet, "occupation": p.occupation,
            },
        }

    def cases_payload(self) -> dict:
        def name(nid: str) -> str:
            return self.npc(nid).name if self.npc(nid) else "Unknown"
        return {"cases": [{
            **c.to_dict(), "accuser_name": name(c.accuser), "accused_name": name(c.accused),
        } for c in self.cases]}

    def rivals_payload(self) -> dict:
        def name(nid: str) -> str:
            n = self.npc(nid)
            return n.name if n else "Unknown"
        return {"rivalries": [{**r.to_dict(), "a_name": name(r.a), "b_name": name(r.b)} for r in self.rivalries]}

    def stats_payload(self) -> dict:
        voice = self.metrics.get("voice_metrics", [])
        e2e = [m["ms"] for m in voice if m.get("stage") in ("e2e_first_audio", "end_to_first_audio")]
        p = self.player
        money_supply = (p.wallet if p else 0) + sum(n.wallet for n in self.npcs)
        tiers = {"foreground": 0, "nearby": 0, "background": 0}
        if p:
            for n in self.npcs:
                d = math.hypot(n.x - p.x, n.y - p.y)
                if d <= config.FOREGROUND_RADIUS:
                    tiers["foreground"] += 1
                elif d <= config.NEARBY_RADIUS:
                    tiers["nearby"] += 1
                else:
                    tiers["background"] += 1
        dialogue_turns = self.metrics.get("dialogue_turns", 0)
        llm_calls = self.metrics.get("llm_calls", 0)
        active_arcs = [a for a in self.arcs if a.status == "active"]
        players_online_minutes = max(1.0, (time.time() - self.metrics.get("started_real", time.time())) / 60.0)
        return {
            "clock": self.clock_payload(),
            "seed": self.seed, "version": config.VERSION,
            "tiers": tiers,
            "counts": {
                "residents": len(self.npcs), "spotlight": sum(1 for n in self.npcs if n.spotlight),
                "events": len(self.events), "posts": len(self.posts),
                "rumors": len(self.rumors), "cases": len(self.cases),
                "arcs_active": len(active_arcs), "arcs_total": len(self.arcs),
                "rivalries": len(self.rivalries),
            },
            "metrics": {k: v for k, v in self.metrics.items() if not isinstance(v, list)},
            "voice": {"samples": len(e2e), "p50_ms": _percentile(e2e, 50), "p95_ms": _percentile(e2e, 95),
                       "target_ms": config.VOICE_TARGET_MS,
                       "recent": voice[-12:]},
            "economy": {
                "money_supply": money_supply, "player_wallet": p.wallet if p else 0,
                "avg_npc_wallet": round(sum(n.wallet for n in self.npcs) / max(1, len(self.npcs)), 1),
                "rent": config.DAILY_RENT,
                "note": "BLX is a closed-loop fictional credit. 1 BLX = 1 USD internal reference only.",
            },
            "ai": {
                "dialogue_turns": dialogue_turns,
                "remote_llm_calls": llm_calls,
                "llm_cost_per_turn_usd": round(
                    self.metrics.get("llm_spend_usd", 0.0) / max(1, llm_calls), 6),
                "active_arcs": [a.to_dict() for a in active_arcs],
                "rumors": self.rumors[-6:],
                "tier_policy": {
                    "foreground": "dialogue composer + memory retrieval + voice",
                    "nearby": "rules/schedules + selective dialogue",
                    "background": "event-driven simulation, batched updates",
                },
                "active_player_hours": round(players_online_minutes / 60.0, 2),
                "estimated_ai_spend_per_active_hour": round(
                    self.metrics.get("llm_spend_usd", 0.0)
                    / max(0.05, players_online_minutes / 60.0), 6),
            },
        }

    def player_ledger_payload(self) -> dict:
        p = self.player
        return {
            "wallet": p.wallet if p else 0,
            "ledger": list(reversed(p.ledger[-60:])) if p else [],
            "inventory": [
                {"id": iid, "qty": qty, **ITEM_BY_ID.get(iid, {"name": iid, "icon": "📦", "price": 0})}
                for iid, qty in (p.inventory.items() if p else [])
            ],
            "cart_owned": bool(p and p.flags.get("cart_owned")),
        }


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    vs = sorted(values)
    k = (len(vs) - 1) * (p / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return round(vs[int(k)], 1)
    return round(vs[f] * (c - k) + vs[c] * (k - f), 1)


def _post_from_dict(d: dict) -> Post:
    post = Post(id=d["id"], author_id=d["author"], text=d["text"], minute=float(d["minute"]),
                mood=d.get("mood", ""), likes=list(d.get("likes", [])), tag=d.get("tag", ""),
                loc=d.get("loc", ""))
    post.comments = [Comment(id=c["id"], author_id=c["author"], text=c["text"],
                             minute=float(c["minute"]), likes=int(c.get("likes", 0)))
                     for c in d.get("comments", [])]
    return post


def _thread_from_dict(d: dict) -> Thread:
    t = Thread(npc_id=d["npc_id"])
    t.messages = [Message(id=m["id"], sender=m["sender"], text=m["text"], minute=float(m["minute"]),
                          read=bool(m.get("read", False)), kind=m.get("kind", "text"),
                          meta=m.get("meta", {})) for m in d.get("messages", [])]
    return t


def _obj_from_dict(cls, d: dict):
    """Reconstruct simple dataclasses, accepting their to_dict key renames."""
    if cls is Rivalry:
        return Rivalry(id=d["id"], a=d["a"], b=d["b"], cause=d["cause"], tension=float(d["tension"]),
                       status=d.get("status", "simmering"), created=float(d.get("created", 0)),
                       last_minute=float(d.get("last", 0)), clashes=int(d.get("clashes", 0)),
                       witnesses=list(d.get("witnesses", [])))
    if cls is Case:
        return Case(id=d["id"], title=d["title"], description=d["description"], accuser=d["accuser"],
                    accused=d["accused"], item=d["item"], location=d["location"],
                    status=d.get("status", "open"), created=float(d.get("created", 0)),
                    helpful_evidence=list(d.get("helpful", [])),
                    found_evidence=list(d.get("evidence", [])))
    if cls is Arc:
        return Arc(id=d["id"], kind=d["kind"], title=d["title"], summary=d.get("summary", ""),
                   actors=list(d.get("actors", [])), stage=int(d.get("stage", 0)),
                   stages=list(d.get("stages", [])), status=d.get("status", "active"),
                   created=float(d.get("created", 0)), last_minute=float(d.get("last", 0)),
                   data=dict(d.get("data", {})))
    raise TypeError(cls)
