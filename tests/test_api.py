"""End-to-end HTTP contract tests against a real server process."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _get(base, path, timeout=10):
    with urllib.request.urlopen(base + path, timeout=timeout) as res:
        return res.status, json.loads(res.read())


def _post(base, path, body, timeout=20):
    req = urllib.request.Request(
        base + path, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            return res.status, json.loads(res.read())
    except urllib.error.HTTPError as err:
        return err.code, json.loads(err.read())


def ensure_world(base):
    """Create the world if a previous test in this module hasn't yet."""
    _, state = _get(base, "/api/state")
    if state.get("setup"):
        status, data = _post(base, "/api/new_game", {
            "name": "Ada", "gender": "female", "age": 27,
            "look": {"skin": "#c98e63", "hairStyle": "braids", "outfit": "#7c5cbf"},
        })
        assert status == 200, data
    return _get(base, "/api/state")[1]


@pytest.fixture(scope="module")
def server(tmp_path_factory):
    port = _free_port()
    env = dict(os.environ)
    env.update({
        "BLXVERSE_DATA_DIR": str(tmp_path_factory.mktemp("blxdata")),
        "BLXVERSE_PORT": str(port),
        "BLXVERSE_HOST": "127.0.0.1",
        "BLXVERSE_WORLD_SEED": "20261017",
    })
    proc = subprocess.Popen(
        [sys.executable, "run_server.py", "--port", str(port)],
        cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    base = f"http://127.0.0.1:{port}"
    deadline = time.time() + 20
    while time.time() < deadline:
        if proc.poll() is not None:
            raise RuntimeError("server died: " + (proc.stdout.read() if proc.stdout else ""))
        try:
            status, _ = _get(base, "/api/health", timeout=1)
            if status == 200:
                break
        except (urllib.error.URLError, ConnectionError, OSError):
            time.sleep(0.2)
    else:
        proc.terminate()
        raise RuntimeError("server did not start")
    yield base, proc
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()


def test_setup_state_before_a_world_exists(server):
    base, _ = server
    status, state = _get(base, "/api/state")
    assert status == 200
    assert state["setup"] is True


def test_static_assets_are_served(server):
    base, _ = server
    for path, needle in (
        ("/", b"BLXVERSE"),
        ("/css/style.css", b"--amber"),
        ("/js/app.js", b"BLXVERSE"),
        ("/js/world.js", b"WorldView"),
        ("/js/art.js", b"drawAvatar"),
    ):
        with urllib.request.urlopen(base + path, timeout=10) as res:
            body = res.read()
        assert res.status == 200
        assert needle in body, f"{path} missing expected content"
    try:
        urllib.request.urlopen(base + "/nope.js", timeout=10)
        raise AssertionError("missing static file should 404")
    except urllib.error.HTTPError as err:
        assert err.code == 404


def test_create_world_and_read_state(server):
    base, _ = server
    status, data = _post(base, "/api/new_game", {
        "name": "Ada", "gender": "female", "age": 27,
        "look": {"skin": "#c98e63", "hairStyle": "braids", "outfit": "#7c5cbf"},
    })
    assert status == 200, data
    assert data["player"]["name"] == "Ada"
    assert data["player"]["wallet"] == 320
    assert len(data["npcs"]) == 72
    assert data["clock"]["weekday"] == "Mon"
    status, state = _get(base, "/api/state")
    assert state["player"]["name"] == "Ada"
    assert state["player"]["wallet"] == 320


def test_world_endpoint(server):
    base, _ = server
    ensure_world(base)
    status, world = _get(base, "/api/world")
    assert status == 200
    assert len(world["locations"]) >= 11
    assert len(world["homes"]) == 20
    assert len(world["items"]) >= 20
    assert len(world["npcs"]) == 72


def test_action_contract_and_proximity(server):
    base, _ = server
    state = ensure_world(base)
    # Home residents are now indoors and intentionally cannot be approached.
    # Exercise proximity with an outdoor resident, not a story-driven interior.
    zara = max((n for n in state['npcs'] if not n['indoors']),
               key=lambda n: (n['x']-state['player']['x'])**2 + (n['y']-state['player']['y'])**2)
    resident_id = zara['id']
    status, blocked = _post(base, "/api/action", {
        "type": "talk", "npc_id": zara["id"], "text": "hi",
    })
    assert status == 422 and blocked["code"] == "too_far"
    _post(base, "/api/speed", {"speed": 0})  # pause so the target stays put
    _, state = _get(base, "/api/state")
    zara = next(n for n in state['npcs'] if n['id'] == resident_id)
    status, moved = _post(base, "/api/action", {
        "type": "move", "x": zara["x"] + 20, "y": zara["y"] + 8,
    })
    assert status == 200 and moved["ok"] is True
    # movement is server-authoritative: poll until the player has actually walked there
    deadline = time.time() + 12
    dist = 1e9
    while time.time() < deadline:
        _, st = _get(base, "/api/state")
        dist = ((st["player"]["x"] - zara["x"]) ** 2 + (st["player"]["y"] - zara["y"]) ** 2) ** 0.5
        if dist < 90:
            break
        time.sleep(0.25)
    assert dist < 130, f"player did not arrive (distance {dist:.0f})"
    status, talk = _post(base, "/api/action", {
        "type": "talk", "npc_id": zara["id"], "text": "Hey there, how's it going?",
    })
    assert status == 200, talk
    assert talk["reply"]
    assert talk["state"]["player"]["name"] == "Ada"
    assert talk["relationship"]["familiarity"] > 0
    _post(base, "/api/speed", {"speed": 1})


def test_rate_limit_and_unknown_action(server):
    base, _ = server
    ensure_world(base)
    status, err = _post(base, "/api/action", {"type": "warp"})
    assert status == 404
    assert err["code"] == "bad_action"


def test_voice_metric_and_stats(server):
    base, _ = server
    ensure_world(base)
    status, res = _post(base, "/api/voice/metric", {
        "stage": "e2e_first_audio", "ms": 612, "meta": {"npc": "npc_001"},
    })
    assert status == 200 and res["samples"] >= 1
    assert res["p50"] and res["target_ms"] == 800
    status, stats = _get(base, "/api/stats")
    assert status == 200
    assert stats["voice"]["samples"] >= 1
    assert "foreground" in stats["tiers"]


def test_feed_threads_ledger_cases(server):
    base, _ = server
    ensure_world(base)
    for path in ("/api/feed", "/api/threads", "/api/ledger", "/api/cases",
                 "/api/rivals", "/api/journal", "/api/events"):
        status, body = _get(base, path)
        assert status == 200, (path, body)
    status, ledger = _get(base, "/api/ledger")
    assert ledger["wallet"] >= 0
    assert isinstance(ledger["inventory"], list)


def test_speed_control_and_save_download(server):
    base, _ = server
    ensure_world(base)
    status, res = _post(base, "/api/speed", {"speed": 2})
    assert status == 200 and res["speed"] == 2
    status, bad = _post(base, "/api/speed", {"speed": 3})
    assert status == 422
    with urllib.request.urlopen(base + "/api/save", timeout=10) as res:
        raw = res.read()
    data = json.loads(raw)
    assert data["format"] == "blxverse-save"
    assert data["player"]["name"] == "Ada"
