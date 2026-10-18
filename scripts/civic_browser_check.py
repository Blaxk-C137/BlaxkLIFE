"""Isolated browser proof for 0.5: real API leases, bubbles and locked shifts.
The explicitly staged chatter fixture is not a claim of a naturally occurring
live encounter. Autonomous chatter and raids have separate engine tests.
Never modifies the live save.
"""

from __future__ import annotations

import json
import os
import socket
import sys
import tempfile
import time
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from playwright.sync_api import sync_playwright  # noqa: E402

from blxverse.engine import civic  # noqa: E402
from blxverse.engine.sim import Simulation, walkable  # noqa: E402
from scripts.render_check import PASSWORD, boot, request, stop  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def run():
    errors = []
    checks = []
    with tempfile.TemporaryDirectory(prefix="blaxkville-civic-ui-") as temp:
        data = Path(temp) / "data"
        sim = Simulation.new(
            20261017, {"name": "Neighbourhood Tester"}, save_path=str(data / "saves/world.json")
        )
        sim.world_flags["chain"].update(started=True, stage=1)
        sim.speed = 1
        a, b = sim.npcs[1:3]
        for n, x in ((a, 500), (b, 550)):
            n.x, n.y = x, 640
            n.status, n.location_id = "at", "square"
            n.flags["ambient_hold"] = time.time() + 60
            n.flags["ambient_game_until"] = sim.minute + 90
            n.target = None
        a.target = {"x": 700, "y": 640, "loc": "cafe", "activity": "a local walk"}
        a.status = "walking"
        patient = sim.npcs[-2]
        deceased = sim.npcs[-1]
        civic.injure(sim, patient, 45, "a staged dispute in this isolated test world")
        civic.injure(sim, deceased, 110, "a staged raid in this isolated test world")
        sim.player.x, sim.player.y = 500, 660
        assert walkable(sim.player.x, sim.player.y)
        # Delayed, short, real server bubbles; front end must wait/display/expire.
        civic.speak(sim, a, "Have you eaten yet?", delay=10, duration=3.2)
        civic.speak(sim, b, "Not yet. Cafe later?", delay=13.3, duration=3.2)
        sim.save(force=True)
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        base = f"http://127.0.0.1:{port}"
        env = dict(
            os.environ,
            PORT=str(port),
            BLXVERSE_DATA_DIR=str(data),
            BLXVERSE_HOST="0.0.0.0",
            BLXVERSE_ACCESS_PASSWORD=PASSWORD,
            BLXVERSE_LLM_DISABLED="1",
        )
        env.pop("BLXVERSE_PORT", None)
        with open(Path(temp) / "server.log", "w+") as log:
            proc = boot(env, base, log)
            try:
                with sync_playwright() as pw:
                    browser = pw.chromium.launch()
                    context = browser.new_context(
                        viewport={"width": 1440, "height": 900},
                        http_credentials={"username": "blxverse", "password": PASSWORD},
                    )
                    page = context.new_page()
                    page.on("pageerror", lambda e: errors.append(str(e)))
                    page.goto(base, wait_until="networkidle")
                    page.wait_for_function("window.__BLX__?.state?.civic")
                    page.evaluate("(id)=>window.__BLX__.ui.openTalk(id)", a.id)
                    page.wait_for_selector("#talk-input")
                    start = request(base, "/api/state")
                    n0 = next(n for n in start["npcs"] if n["id"] == a.id)
                    page.fill("#talk-input", "How has your morning been?")
                    page.click("#talk-send")
                    page.wait_for_timeout(4500)
                    end = request(base, "/api/state")
                    n1 = next(n for n in end["npcs"] if n["id"] == a.id)
                    assert abs(n1["x"] - n0["x"]) + abs(n1["y"] - n0["y"]) < 0.1
                    assert end["clock"]["minute"] > start["clock"]["minute"]
                    assert n1["engaged"] and not n1["route"]
                    page.screenshot(path=str(ROOT / "screenshots/blaxkville-05-conversation.png"))
                    page.keyboard.press("Escape")
                    page.wait_for_timeout(1800)
                    resumed = request(base, "/api/state")
                    n2 = next(n for n in resumed["npcs"] if n["id"] == a.id)
                    assert abs(n2["x"] - n1["x"]) + abs(n2["y"] - n1["y"]) > 5
                    checks.append(
                        "real talk panel acquires lease; world clock advances, NPC stays; Escape releases movement"
                    )
                    page.wait_for_function(
                        """()=>{const v=window.__BLX__.view,t=performance.now();return (v.streetBubbles||[]).some(b=>b.startAt<=t&&b.endAt>t)}""",
                        timeout=25000,
                    )
                    page.screenshot(path=str(ROOT / "screenshots/blaxkville-05-overhead-bubbles.png"))
                    checks.append(
                        "server-staged casual overhead bubbles wait, follow actors, and expire; autonomous pairing separately unit-tested"
                    )
                    page.click("#btn-civic")
                    for site in ("hospital", "graveyard", "police", "barracks", "black_market"):
                        page.evaluate("(id)=>window.__BLX__.ui.openCivicSite(id)", site)
                        assert page.locator(".modal").is_visible()
                        page.wait_for_timeout(260)  # Let the modal entrance animation paint before screenshots.
                        if site == "hospital":
                            assert patient.first in page.locator(".modal").inner_text()
                            page.screenshot(path=str(ROOT / "screenshots/blaxkville-05-hospital.png"))
                        if site == "graveyard":
                            assert deceased.name in page.locator(".modal").inner_text()
                            page.screenshot(path=str(ROOT / "screenshots/blaxkville-05-memorial.png"))
                    page.screenshot(path=str(ROOT / "screenshots/blaxkville-05-backlot.png"))
                    checks.append(
                        "all five civic facilities open; persisted injured patient, permanent memorial and abstract businesses render"
                    )
                    page.keyboard.press("Escape")
                    request(base, "/api/action", {"type": "move", "x": 370, "y": 485})
                    page.wait_for_function(
                        """()=>{const p=window.__BLX__.state.player;return Math.hypot(p.x-370,p.y-485)<35}""",
                        timeout=20000,
                    )
                    page.evaluate("window.__BLX__.ui.openVenue('cafe')")
                    page.locator("[data-work]").click()
                    page.wait_for_selector("#shift-lock", timeout=2000)
                    assert page.evaluate("window.__BLX__.inputLocked")
                    page.keyboard.press("Escape")
                    assert page.locator("#shift-lock").is_visible()
                    page.screenshot(path=str(ROOT / "screenshots/blaxkville-05-shift-lock.png"))
                    page.wait_for_function(
                        "window.__BLX__.state.civic?.busy?.remaining_seconds>0", timeout=45000
                    )
                    blocked = []
                    for action in (
                        {"type": "move", "x": 700, "y": 640},
                        {"type": "buy", "item_id": "sandwich", "remote": True},
                    ):
                        try:
                            request(base, "/api/action", action)
                        except urllib.error.HTTPError as e:
                            assert e.code == 423
                            assert json.load(e)["code"] == "busy"
                            blocked.append(e.code)
                    assert len(blocked) == 2
                    page.wait_for_selector("#shift-lock", state="detached", timeout=15000)
                    assert not page.evaluate("window.__BLX__.inputLocked")
                    checks.append(
                        "actual work action dims immediately; Escape cannot bypass; movement/purchases blocked by server; unlocks after five-second finishing lock"
                    )
                    browser.close()
            finally:
                stop(proc)
    assert not errors, errors
    report = {
        "result": "PASS",
        "checks": checks,
        "errors": errors,
        "note": "Isolated synthetic world in Chromium. Live save not changed; no live Google API key or physical-device audit.",
    }
    (ROOT / "docs/civic-browser-check-0.5.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    run()
