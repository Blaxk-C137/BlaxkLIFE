"""BLXVERSE HTTP server (stdlib only).

Serves the browser client and a JSON API. One canonical world per save slot.
A background thread advances the simulation; every mutation is serialised
behind a re-entrant lock so the world can never be half-updated.

Endpoints
---------
GET  /api/health
GET  /api/state                live world snapshot for polling
GET  /api/world                static content: locations, homes, items, residents
POST /api/new_game             create a character + world
POST /api/action               validated player action
GET  /api/feed                 social feed + notices + trending
GET  /api/thread/<npc_id>      message thread (mark_read=1 supported)
GET  /api/npc/<npc_id>         full resident profile + your relationship
GET  /api/cases                case files
GET  /api/rivals               rivalry ledger
GET  /api/calendar             weekly fixtures, live events, birthdays
GET  /api/stats                simulation + AI + voice metrics
GET  /api/ledger               wallet, transactions, inventory
GET  /api/events               recent world events
GET  /api/save                 download the save file
POST /api/voice/metric         client-measured latency sample
POST /api/voice/prefetch       partial-transcript context prefetch (no action)
POST /api/speed                set 0 / 1 / 2 / 4
"""

from __future__ import annotations

import json
import mimetypes
import os
import signal
import sys
import threading
import time
import traceback
from collections import defaultdict, deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse

from blxverse import config
from blxverse.engine import actions as action_layer
from blxverse.engine import llm
from blxverse.engine.composer import classify_intent
from blxverse.engine.sim import SimError, Simulation

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB_DIR = os.path.join(ROOT, "web")
SAVE_DIR = os.path.join(os.path.abspath(config.data_dir()), "saves")
SAVE_PATH = os.path.join(SAVE_DIR, "world.json")

LOCK = threading.RLock()
SIM: Simulation | None = None
TICK_INTERVAL = 0.25
LAST_TICK = time.time()

RATE: dict[str, deque] = defaultdict(deque)
VOICE_STAGES = {
    "vad_speech_start", "asr_first_partial", "asr_final", "llm_first_token",
    "tts_first_audio", "e2e_first_audio", "end_to_first_audio", "barge_in",
    "prefetch", "playback_buffering",
}


# ---------------------------------------------------------------------------
# world lifecycle
# ---------------------------------------------------------------------------
def load_or_none() -> Simulation | None:
    global SIM
    if not os.path.exists(SAVE_PATH):
        return None
    try:
        SIM = Simulation.load(SAVE_PATH)
        return SIM
    except Exception as exc:  # corrupted save should not brick the server
        print(f"[blxverse] Could not load save: {exc}", file=sys.stderr)
        broken = SAVE_PATH + f".broken-{int(time.time())}"
        try:
            os.replace(SAVE_PATH, broken)
            print(f"[blxverse] Moved unreadable save to {broken}", file=sys.stderr)
        except OSError:
            pass
        return None


def new_world(spec: dict) -> Simulation:
    global SIM
    seed = int(spec.get("seed") or os.environ.get("BLXVERSE_WORLD_SEED") or 20261017)
    os.makedirs(SAVE_DIR, exist_ok=True)
    SIM = Simulation.new(seed=seed, player_spec=spec, save_path=SAVE_PATH)
    return SIM


def tick_loop() -> None:
    global LAST_TICK
    while True:
        time.sleep(TICK_INTERVAL)
        now = time.time()
        dt = min(now - LAST_TICK, 1.0)
        LAST_TICK = now
        sim = SIM
        if sim is None:
            continue
        try:
            with LOCK:
                sim.tick(dt)
                if sim._dirty and now - sim.last_save_real > 20:
                    sim.save()
        except Exception:
            traceback.print_exc()


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _json_default(obj):
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    return str(obj)


def _rate_limited(ip: str, limit: int = config.ACTION_RATE_LIMIT) -> bool:
    now = time.time()
    q = RATE[ip]
    while q and now - q[0] > config.RATE_WINDOW_SECONDS:
        q.popleft()
    q.append(now)
    return len(q) > limit


class Handler(BaseHTTPRequestHandler):
    server_version = "BLXVERSE/0.1"
    protocol_version = "HTTP/1.1"

    # ---- logging -----------------------------------------------------
    def log_message(self, fmt: str, *args) -> None:  # quieter, no private content
        if os.environ.get("BLXVERSE_HTTP_LOG") == "1":
            sys.stderr.write("[http] " + (fmt % args) + "\n")

    # ---- responses ---------------------------------------------------
    def _send(self, status: int, body: bytes, content_type: str, extra: dict | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _json(self, obj, status: int = 200) -> None:
        payload = json.dumps(obj, ensure_ascii=False, default=_json_default).encode("utf-8")
        self._send(status, payload, "application/json; charset=utf-8")

    def _error(self, message: str, code: str = "error", status: int = 400) -> None:
        self._json({"ok": False, "error": message, "code": code}, status)

    def _read_json(self) -> dict:
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        if length <= 0:
            return {}
        if length > config.MAX_BODY_BYTES:
            raise SimError("Request body too large.", "too_large", 413)
        raw = self.rfile.read(length)
        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise SimError("Invalid JSON body.", "bad_json", 400) from None
        if not isinstance(data, dict):
            raise SimError("JSON body must be an object.", "bad_json", 400)
        return data

    # ---- routing -----------------------------------------------------
    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        query = parse_qs(parsed.query)
        if path.startswith("/api/"):
            return self._api_get(path, query)
        return self._static(path)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        if not path.startswith("/api/"):
            return self._error("Not found", "not_found", 404)
        ip = self.client_address[0]
        # Latency beacons are tiny and frequent; chat/action traffic is what the
        # limiter exists to protect.
        try:
            body = self._read_json()
        except SimError as exc:
            return self._error(exc.message, exc.code, exc.status)
        # Walking is chatty; conversation and economy actions are the ones that
        # need a strict budget.
        limit = 600 if body.get("type") == "move" else config.ACTION_RATE_LIMIT
        if not path.startswith("/api/voice/") and _rate_limited(ip, limit):
            return self._error("Too many actions. Take a breath.", "rate_limited", 429)
        try:
            return self._api_post(path, body)
        except SimError as exc:
            return self._error(exc.message, exc.code, exc.status)
        except Exception:
            traceback.print_exc()
            return self._error("The world engine hit an unexpected snag.", "server_error", 500)

    # ---- static files -------------------------------------------------
    def _static(self, path: str) -> None:
        if path in ("/", ""):
            path = "/index.html"
        safe = os.path.normpath(path).lstrip(os.sep)
        full = os.path.join(WEB_DIR, safe)
        if not os.path.abspath(full).startswith(os.path.abspath(WEB_DIR)):
            return self._error("Forbidden", "forbidden", 403)
        if not os.path.isfile(full):
            return self._error("Not found", "not_found", 404)
        ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript", "application/json"):
            ctype += "; charset=utf-8"
        with open(full, "rb") as fh:
            body = fh.read()
        self._send(200, body, ctype)

    # ---- GET API ------------------------------------------------------
    def _api_get(self, path: str, query: dict) -> None:
        if path == "/api/health":
            return self._json({"ok": True, "version": config.VERSION,
                               "world": SIM is not None, "time": time.time(),
                               "llm": llm.status()})
        if path == "/api/state":
            with LOCK:
                if SIM is None:
                    return self._json({"setup": True, "has_save": os.path.exists(SAVE_PATH)})
                return self._json(SIM.state_payload())
        if path == "/api/world":
            with LOCK:
                if SIM is None:
                    return self._json(_empty_world_payload())
                return self._json(SIM.world_payload())
        if path == "/api/feed":
            with LOCK:
                if SIM is None:
                    return self._error("No world yet.", "no_world", 409)
                return self._json(SIM.feed_payload())
        if path.startswith("/api/thread/"):
            npc_id = path.split("/api/thread/", 1)[1]
            with LOCK:
                if SIM is None:
                    return self._error("No world yet.", "no_world", 409)
                mark = query.get("mark_read", ["0"])[0] == "1"
                return self._json(SIM.thread_payload(npc_id, mark_read=mark))
        if path.startswith("/api/npc/"):
            npc_id = path.split("/api/npc/", 1)[1]
            with LOCK:
                if SIM is None:
                    return self._error("No world yet.", "no_world", 409)
                return self._json(SIM.npc_payload(npc_id))
        if path == "/api/threads":
            with LOCK:
                if SIM is None:
                    return self._error("No world yet.", "no_world", 409)
                return self._json(SIM.threads_payload())
        if path == "/api/journal":
            with LOCK:
                if SIM is None:
                    return self._error("No world yet.", "no_world", 409)
                return self._json(SIM.journal_payload())
        if path == "/api/cases":
            with LOCK:
                if SIM is None:
                    return self._error("No world yet.", "no_world", 409)
                return self._json(SIM.cases_payload())
        if path == "/api/rivals":
            with LOCK:
                if SIM is None:
                    return self._error("No world yet.", "no_world", 409)
                return self._json(SIM.rivals_payload())
        if path == "/api/stats":
            with LOCK:
                if SIM is None:
                    return self._error("No world yet.", "no_world", 409)
                return self._json(SIM.stats_payload())
        if path == "/api/ledger":
            with LOCK:
                if SIM is None:
                    return self._error("No world yet.", "no_world", 409)
                return self._json(SIM.player_ledger_payload())
        if path == "/api/events":
            with LOCK:
                if SIM is None:
                    return self._error("No world yet.", "no_world", 409)
                limit = int(query.get("limit", ["20"])[0])
                limit = max(1, min(120, limit))
                return self._json({"events": list(reversed(SIM.events))[:limit]})
        if path == "/api/calendar":
            with LOCK:
                if SIM is None:
                    return self._error("No world yet.", "no_world", 409)
                return self._json(SIM.events_payload())
        if path == "/api/save":
            if not os.path.exists(SAVE_PATH):
                return self._error("No save file yet.", "no_save", 404)
            with open(SAVE_PATH, "rb") as fh:
                body = fh.read()
            return self._send(200, body, "application/json",
                              {"Content-Disposition": 'attachment; filename="blxverse-save.json"'})
        return self._error("Unknown endpoint", "not_found", 404)

    # ---- POST API -----------------------------------------------------
    def _api_post(self, path: str, body: dict) -> None:
        global SIM
        if path == "/api/new_game":
            with LOCK:
                if SIM is not None and not body.get("overwrite"):
                    return self._error("A world already exists. Send overwrite=true to start over.",
                                       "world_exists", 409)
                name = str(body.get("name", "")).strip()
                if not (2 <= len(name) <= 24):
                    return self._error("Pick a name between 2 and 24 characters.", "bad_name", 422)
                gender = str(body.get("gender", "female"))
                if gender not in ("male", "female"):
                    return self._error("Choose male or female for the character creator.", "bad_gender", 422)
                try:
                    age = int(body.get("age", 26))
                except (TypeError, ValueError):
                    return self._error("Age must be a number.", "bad_age", 422)
                if not (22 <= age <= 90):
                    return self._error("This slice is 22+ only. Choose an age between 22 and 90.", "bad_age", 422)
                look = body.get("look") if isinstance(body.get("look"), dict) else {}
                if SIM is not None and os.path.exists(SAVE_PATH):
                    stamp = time.strftime("%Y%m%d-%H%M%S")
                    try:
                        os.replace(SAVE_PATH, os.path.join(SAVE_DIR, f"world.json.prev-{stamp}"))
                    except OSError:
                        pass
                sim = new_world({"name": name, "gender": gender, "age": age, "look": look,
                                 "seed": body.get("seed")})
                sim.save(force=True)
                state = sim.state_payload()
                return self._json({**state, "ok": True, "world": sim.world_payload()})

        if SIM is None:
            return self._error("Create a character first.", "no_world", 409)

        if path == "/api/action":
            with LOCK:
                result = action_layer.handle_action(SIM, body)
                if SIM._dirty and time.time() - SIM.last_save_real > 5:
                    SIM.save()
                if body.get("type") == "move":
                    return self._json({**result, "clock": SIM.clock_payload()})
                return self._json({**result, "state": SIM.state_payload()})

        if path == "/api/speed":
            with LOCK:
                speed = int(body.get("speed", 1))
                if speed not in config.ALLOWED_SPEEDS:
                    return self._error("Speed must be 0, 1, 2 or 4.", "bad_speed", 422)
                SIM.speed = speed
                return self._json({"ok": True, "speed": SIM.speed, "clock": SIM.clock_payload()})

        if path == "/api/voice/metric":
            with LOCK:
                stage = str(body.get("stage", ""))
                if stage not in VOICE_STAGES:
                    return self._error("Unknown voice stage.", "bad_stage", 422)
                try:
                    ms = float(body.get("ms", 0))
                except (TypeError, ValueError):
                    return self._error("ms must be numeric.", "bad_ms", 422)
                if not (0 <= ms <= 60000):
                    return self._error("ms out of range.", "bad_ms", 422)
                SIM.log_voice_metric(stage, ms, body.get("meta") if isinstance(body.get("meta"), dict) else {})
                e2e = [m["ms"] for m in SIM.metrics.get("voice_metrics", [])
                       if m.get("stage") in ("e2e_first_audio", "end_to_first_audio")]
                return self._json({"ok": True, "samples": len(e2e),
                                   "p50": _pct(e2e, 50), "p95": _pct(e2e, 95),
                                   "target_ms": config.VOICE_TARGET_MS})

        if path == "/api/voice/prefetch":
            partial = str(body.get("partial", ""))[:200]
            intent = classify_intent(partial) if partial else "fallback"
            return self._json({
                "ok": True, "intent": intent, "stable": False,
                "note": "Partial transcripts may be revised. Prefetch only warms context; "
                        "no game action is committed until the final transcript is confirmed.",
            })

        return self._error("Unknown endpoint", "not_found", 404)


def _pct(values: list[float], p: float):
    import math
    if not values:
        return None
    vs = sorted(values)
    k = (len(vs) - 1) * (p / 100.0)
    f, c = math.floor(k), math.ceil(k)
    if f == c:
        return round(vs[int(k)], 1)
    return round(vs[f] * (c - k) + vs[c] * (k - f), 1)


def _empty_world_payload() -> dict:
    from blxverse.content.items import ITEMS
    from blxverse.content.locations import HOMES, LOCATIONS
    return {
        "version": config.VERSION, "setup": True,
        "config": {"world_width": config.WORLD_WIDTH, "world_height": config.WORLD_HEIGHT,
                   "interact_radius": config.INTERACT_RADIUS, "talk_radius": config.TALK_RADIUS,
                   "player_speed": config.PLAYER_MAX_SPEED, "rent": config.DAILY_RENT,
                   "start_balance": config.STARTING_BALANCE, "npcs": config.NPC_COUNT,
                   "spotlight": config.SPOTLIGHT_COUNT, "cart_cost": config.STREET_CART_COST},
        "locations": LOCATIONS,
        "homes": [{"id": i, "x": h[0], "y": h[1], "color": h[2]} for i, h in enumerate(HOMES)],
        "items": ITEMS, "npcs": [],
        "playable": {"genders": ["female", "male"], "pronouns": {"female": "she/her", "male": "he/him"}},
        "disclaimer": "All residents are fictional simulations. BLX is a closed-loop fictional credit with no cash value.",
    }


def main() -> None:
    port = int(os.environ.get("BLXVERSE_PORT", "8000"))
    host = os.environ.get("BLXVERSE_HOST", "0.0.0.0")
    load_or_none()
    t = threading.Thread(target=tick_loop, daemon=True, name="blxverse-tick")
    t.start()

    def shutdown(signum, frame):
        with LOCK:
            if SIM:
                SIM.save(force=True)
        print("\n[blxverse] saved and shutting down", file=sys.stderr)
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    httpd = ThreadingHTTPServer((host, port), Handler)
    httpd.daemon_threads = True
    print(f"[blxverse] BLXVERSE {config.VERSION} serving on http://{host}:{port}", file=sys.stderr)
    print(f"[blxverse] save: {SAVE_PATH}", file=sys.stderr)
    httpd.serve_forever()


if __name__ == "__main__":
    main()
