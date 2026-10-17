"""Browser probe: click-to-move must be stable, path-respecting and never cross a building.

    python3 run_server.py --port 8111 &
    python3 scripts/movement_probe.py --base http://localhost:8111

For three real canvas clicks it samples the player position every ~80 ms and
reports:

* ``backtracks``  — consecutive motion vectors that reverse direction
                    (dot < -25% of their lengths). Turn-a-corner is fine,
                    front/back oscillation is not.
* ``inside``      — samples strictly inside a building footprint (the
                    "walks over the houses" bug).
* ``speed``       — median / min sample speed while walking. Realistic
                    movement keeps a steady pace instead of stuttering.
* ``arrive``      — distance from the clicked point once the walk settles.

Exit code 1 if any target backtracks more than twice, enters a building,
or fails to arrive.
"""

from __future__ import annotations

import argparse
import json
import math
import pathlib
import sys
import time
import urllib.request

from playwright.sync_api import sync_playwright

from blxverse.engine.sim import walkable

SHOTS = pathlib.Path("screenshots")


def api(base: str, path: str) -> dict:
    with urllib.request.urlopen(base + path, timeout=30) as res:
        return json.loads(res.read())


def buildings(world: dict) -> list[tuple[float, float, float, float]]:
    rects = [(loc["x"], loc["y"], loc["w"], loc["h"]) for loc in world["locations"]]
    rects += [(h["x"], h["y"], 92, 74) for h in world["homes"]]
    return rects


def penetration(x: float, y: float, rects) -> float:
    """How deep (px) a point sits inside the nearest building; 0 when outside."""
    worst = 0.0
    for rx, ry, rw, rh in rects:
        if rx < x < rx + rw and ry < y < ry + rh:
            worst = max(worst, min(x - rx, rx + rw - x, y - ry, ry + rh - y))
    return worst


def analyse(points: list[tuple[float, float, float]], rects) -> dict:
    import statistics

    backtracks, speeds, worst_inside = 0, [], 0.0
    for (x0, y0, t0), (x1, y1, t1) in zip(points, points[1:], strict=False):
        dt = max(1e-3, t1 - t0)
        dist = math.hypot(x1 - x0, y1 - y0)
        if dist > 1.0:
            speeds.append(dist / dt)
        worst_inside = max(worst_inside, penetration(x1, y1, rects))
    for (a0, a1), (b0, b1) in zip(zip(points, points[1:], strict=False), zip(points[1:], points[2:], strict=False), strict=False):
        ax, ay = a1[0] - a0[0], a1[1] - a0[1]
        bx, by = b1[0] - b0[0], b1[1] - b0[1]
        la, lb = math.hypot(ax, ay), math.hypot(bx, by)
        if la > 2 and lb > 2 and (ax * bx + ay * by) / (la * lb) < -0.25:
            backtracks += 1
    return {
        "backtracks": backtracks,
        "inside": round(worst_inside, 1),
        "speed_med": round(statistics.median(speeds), 1) if speeds else 0.0,
        "speed_min": round(min(speeds), 1) if speeds else 0.0,
        "samples": len(points),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:8111")
    ap.add_argument("--headed", action="store_true")
    args = ap.parse_args()
    SHOTS.mkdir(exist_ok=True)

    world = api(args.base, "/api/world")
    rects = buildings(world)
    state = api(args.base, "/api/state")
    px, py = state["player"]["x"], state["player"]["y"]
    candidates = [(1500, 1130), (300, 1150), (1620, 240), (900, 1050),
                  (420, 760), (1180, 620), (760, 300), (1350, 980),
                  (240, 420), (1660, 760), (620, 1120), (1000, 820)]
    targets: list[tuple[float, float]] = []
    for cand in candidates:
        if not walkable(*cand):
            continue
        if math.hypot(cand[0] - px, cand[1] - py) < 380:
            continue
        if any(math.hypot(cand[0] - t[0], cand[1] - t[1]) < 380 for t in targets):
            continue
        targets.append(cand)
        if len(targets) == 3:
            break
    ok = True

    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-sandbox"], headless=not args.headed)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(args.base, wait_until="networkidle")
        page.wait_for_function(
            "() => window.__BLX__ && window.__BLX__.view && window.__BLX__.state", timeout=25000
        )
        page.wait_for_timeout(1200)
        box = page.locator("#world").bounding_box()
        if not box:
            print("FAIL: no canvas")
            return 1

        for i, (tx, ty) in enumerate(targets):
            page.evaluate("() => window.__BLX__.view.zoomTo(0.62)")
            page.wait_for_timeout(300)
            # Wait for the camera lerp to settle: clicking while it is still
            # gliding lands on a different world point than we aimed at.
            prev_cam = None
            for _ in range(30):
                cam = page.evaluate(
                    "() => { const c = window.__BLX__.view.camera;"
                    " return [c.x, c.y, c.zoom, window.__BLX__.view.camera.targetZoom]; }"
                )
                if (
                    prev_cam
                    and abs(cam[0] - prev_cam[0]) < 0.4
                    and abs(cam[1] - prev_cam[1]) < 0.4
                    and abs(cam[2] - cam[3]) < 0.004
                ):
                    break
                prev_cam = cam
                page.wait_for_timeout(90)
            screen = page.evaluate(
                "([x, y]) => { const w = window.__BLX__.view.worldToScreen(x, y);"
                " return { x: w.x, y: w.y, vw: window.__BLX__.view.viewW, vh: window.__BLX__.view.viewH }; }",
                [tx, ty],
            )
            sx = max(4, min(screen["vw"] - 4, screen["x"]))
            sy = max(4, min(screen["vh"] - 4, screen["y"]))
            # Only open ground triggers a walk; clicking a building or a
            # resident opens that panel instead. Nudge until we hit pavement.
            hit, k = None, 0
            while k < 24:
                hit = page.evaluate(
                    "([x, y]) => window.__BLX__.view.hitTest(x, y).type", [sx, sy]
                )
                if hit in ("ground", None):
                    break
                sx += 11 if sx < screen["vw"] / 2 else -11
                sy += 7 if sy < screen["vh"] / 2 else -7
                k += 1
            if hit not in ("ground", None):
                print(f"target {i}: no open ground near aim point ({hit}), skipping")
                continue
            click_world = page.evaluate(
                "([x, y]) => window.__BLX__.view.screenToWorld(x, y)", [sx, sy]
            )
            page.mouse.click(box["x"] + sx, box["y"] + sy)

            points: list[tuple[float, float, float]] = []
            displays: list[dict] = []
            t0 = time.time()
            last = None
            still = 0
            while time.time() - t0 < 26:
                pl = page.evaluate(
                    "() => ({ x: window.__BLX__.state.player.x, y: window.__BLX__.state.player.y,"
                    " dx: window.__BLX__.view.playerDisplay.x, dy: window.__BLX__.view.playerDisplay.y,"
                    " walking: window.__BLX__.view.isWalking })"
                )
                now_t = time.time()
                points.append((pl["x"], pl["y"], now_t))
                displays.append({"dx": pl["dx"], "dy": pl["dy"], "t": now_t})
                moved = None if last is None else math.hypot(pl["x"] - last[0], pl["y"] - last[1])
                last = (pl["x"], pl["y"])
                still = still + 1 if (moved is not None and moved < 0.5 and not pl["walking"]) else 0
                if len(points) > 10 and still >= 4:
                    break
                time.sleep(0.08)

            disp = [(pl["dx"], pl["dy"], pl["t"]) for pl in displays]
            report = analyse(disp if len(disp) > 2 else points, rects)
            report["server_samples"] = len(points)
            final = api(args.base, "/api/state")["player"]
            for _ in range(40):
                if not (final.get("route") or []):
                    break
                time.sleep(0.25)
                final = api(args.base, "/api/state")["player"]
            sync_err = math.hypot(disp[-1][0] - final["x"], disp[-1][1] - final["y"])
            arrive = math.hypot(disp[-1][0] - click_world["x"], disp[-1][1] - click_world["y"])
            report["arrive"] = round(arrive, 1)
            report["sync_err"] = round(sync_err, 1)
            report["target"] = (round(click_world["x"]), round(click_world["y"]))
            verdict = (
                report["backtracks"] <= 2
                and report["inside"] < 4
                and arrive < 70
                and sync_err < 40
                and 150 < report["speed_med"] < 320
            )
            ok = ok and verdict
            print(("PASS " if verdict else "FAIL ") + json.dumps(report))
            page.screenshot(path=str(SHOTS / f"move-{i}.png"))
            page.wait_for_timeout(300)

        if errors:
            ok = False
            print("JS errors:", errors[:3])
        browser.close()
    print("MOVEMENT PROBE:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
