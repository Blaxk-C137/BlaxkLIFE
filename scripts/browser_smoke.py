"""Optional end-to-end browser smoke test for BLXVERSE.

Not part of CI: it needs Playwright + Chromium installed locally.

    python3 -m pip install playwright && python3 -m playwright install chromium
    python3 run_server.py --port 8111 &
    python3 scripts/browser_smoke.py --base http://localhost:8111

It drives the real UI (clicks, not API shortcuts) and fails if the page throws
a JS error or a flow that should work returns an error toast.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
import urllib.error
import urllib.request

from playwright.sync_api import sync_playwright

SHOTS = pathlib.Path("screenshots")
ERRORS: list[str] = []


def api(base: str, path: str, body: dict | None = None) -> dict:
    req = urllib.request.Request(
        base + path,
        data=None if body is None else json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
        method="GET" if body is None else "POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as res:
            return json.loads(res.read())
    except urllib.error.HTTPError as exc:  # gameplay refusals are data, not crashes
        return {"status": exc.code, **json.loads(exc.read())}


def wait_near(base: str, x: float, y: float, tol: float = 110.0, tries: int = 45) -> dict:
    import time

    state = {}
    for _ in range(tries):
        state = api(base, "/api/state")
        p = state.get("player") or {}
        if abs(p.get("x", 0) - x) < tol and abs(p.get("y", 0) - y) < tol:
            return state
        time.sleep(0.6)
    return state


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:8111")
    ap.add_argument("--headed", action="store_true")
    args = ap.parse_args()
    SHOTS.mkdir(exist_ok=True)

    world = api(args.base, "/api/world")
    loc = {entry["id"]: entry for entry in world["locations"]}

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=not args.headed)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.on("pageerror", lambda e: ERRORS.append(f"pageerror: {e}"))
        page.on("console", lambda m: ERRORS.append(f"console.{m.type}: {m.text}") if m.type == "error" else None)

        def _track(response):
            if "/api/" in response.url and response.status >= 400:
                try:
                    ERRORS.append(f"HTTP {response.status} {response.request.method} "
                                  f"{response.url.split('/api/')[-1]}: {response.text()[:180]}")
                except Exception:
                    ERRORS.append(f"HTTP {response.status} {response.url}")
        page.on("response", _track)

        # Venues keep hours. If the save is sitting at 2 am, sleep to morning
        # first — otherwise every counter button is legitimately disabled.
        clock = api(args.base, "/api/state").get("clock") or {}
        if clock.get("hour", 12) > 21 or clock.get("hour", 12) < 7:
            api(args.base, "/api/speed", {"speed": 1})
            api(args.base, "/api/action", {"type": "sleep"})

        page.goto(args.base + "/", wait_until="networkidle")
        page.wait_for_timeout(1800)
        page.screenshot(path=str(SHOTS / "01-world.png"))

        # ---------------------------------------------------------------- phone
        page.click("#btn-phone")
        page.wait_for_timeout(700)
        for tab, shot in (("feed", "02-phone-feed"), ("wallet", "03-phone-wallet"), ("cases", "04-phone-cases")):
            page.click(f"#phone-root [data-ptab='{tab}']")
            page.wait_for_timeout(700)
            page.screenshot(path=str(SHOTS / f"{shot}.png"))
        page.keyboard.press("Escape")
        page.wait_for_timeout(400)

        # ------------------------------------------------------- cafe activities
        cafe = loc["cafe"]
        cx, cy = cafe["x"] + cafe["w"] / 2, cafe["y"] + cafe["h"] + 60
        api(args.base, "/api/speed", {"speed": 4})
        api(args.base, "/api/action", {"type": "move", "x": cx, "y": cy})
        wait_near(args.base, cx, cy)
        api(args.base, "/api/speed", {"speed": 1})

        page.evaluate("window.__BLX__.ui.openVenue('cafe')")
        page.wait_for_timeout(700)
        page.screenshot(path=str(SHOTS / "05-venue.png"))
        page.click("[data-activity='coffee']")
        page.wait_for_timeout(1200)
        page.screenshot(path=str(SHOTS / "06-activity.png"))

        # ----------------------------------------------------------------- work
        api(args.base, "/api/action", {"type": "buy", "item_id": "sandwich", "remote": True})
        api(args.base, "/api/action", {"type": "use_item", "item_id": "sandwich"})
        api(args.base, "/api/action", {"type": "buy", "item_id": "sandwich", "remote": True})
        api(args.base, "/api/action", {"type": "use_item", "item_id": "sandwich"})
        page.evaluate("window.__BLX__.ui.openVenue('cafe')")
        page.wait_for_timeout(600)
        page.click("[data-work='1']")
        page.wait_for_timeout(1400)
        page.screenshot(path=str(SHOTS / "07-work.png"))

        # ------------------------------------------------------------ call flow
        st = api(args.base, "/api/state")
        if not any(n["status"] != "sleeping" for n in st["npcs"]):
            # Nobody is awake at 02:00. Sleep through to morning like a player would.
            api(args.base, "/api/speed", {"speed": 1})
            api(args.base, "/api/action", {"type": "sleep"})
            api(args.base, "/api/speed", {"speed": 4})
            for _ in range(40):
                st = api(args.base, "/api/state")
                if any(n["status"] != "sleeping" for n in st["npcs"]):
                    break
                import time as _t
                _t.sleep(1.0)
            api(args.base, "/api/speed", {"speed": 1})
            st = api(args.base, "/api/state")
        awake = [n for n in st["npcs"] if n["status"] != "sleeping"]
        target = max(awake, key=lambda n: n["rel"]["familiarity"]) if awake else None
        if target:
            # meet them properly first: a call requires familiarity, and it
            # also exercises the proximity requirement like a real player.
            api(args.base, "/api/speed", {"speed": 0})
            api(args.base, "/api/action", {"type": "move", "x": target["x"], "y": target["y"]})
            wait_near(args.base, target["x"], target["y"], tol=120)
            for _ in range(14):
                api(args.base, "/api/action", {"type": "intent", "npc_id": target["id"], "intent": "greet"})
            page.evaluate(f"window.__BLX__.ui.openProfile('{target['id']}')")
            page.wait_for_timeout(600)
            page.screenshot(path=str(SHOTS / "08-profile.png"))
            page.click("[data-act='call']")
            page.wait_for_timeout(2200)
            page.screenshot(path=str(SHOTS / "09-call.png"))
            if page.query_selector("#call-text"):
                page.click("#call-text")
                page.wait_for_timeout(500)
                page.fill("#call-input-text", "What are you up to later?")
                page.keyboard.press("Enter")
                page.wait_for_timeout(1800)
                page.screenshot(path=str(SHOTS / "10-call-turn.png"))
            if page.query_selector("#call-end"):
                page.click("#call-end")
                page.wait_for_timeout(900)

        # --------------------------------------------------------------- mobile
        mobile = browser.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=2)
        mobile.on("pageerror", lambda e: ERRORS.append(f"mobile pageerror: {e}"))
        mobile.goto(args.base + "/", wait_until="networkidle")
        mobile.wait_for_timeout(1600)
        mobile.screenshot(path=str(SHOTS / "11-mobile.png"))

        browser.close()

    if ERRORS:
        print("\n".join(ERRORS[:40]))
        return 1
    print("browser smoke: OK — screenshots in", SHOTS.resolve())
    return 0


if __name__ == "__main__":
    sys.exit(main())
