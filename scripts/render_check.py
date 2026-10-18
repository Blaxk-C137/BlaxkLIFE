#!/usr/bin/env python3
"""Isolated Render-style boot/restart + Linux CPU/RSS probe. No dependencies.

Runs a NEW temporary world, never touches the real save or existing server.
CPU percentage is relative to one core, not a prediction of Render latency.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PASSWORD = "render-local-check-only"
AUTH = "Basic " + base64.b64encode(f"blxverse:{PASSWORD}".encode()).decode()


def request(base, path, body=None, *, authenticated=True):
    headers = {"Authorization": AUTH} if authenticated else {}
    if body is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(base + path, headers=headers,
                                 data=json.dumps(body).encode() if body is not None else None)
    with urllib.request.urlopen(req, timeout=20) as res:
        raw = res.read()
        return json.loads(raw) if "application/json" in res.headers.get("Content-Type", "") else raw


def boot(env, base, log):
    proc = subprocess.Popen([sys.executable, "-u", "run_server.py"], cwd=ROOT,
                            env=env, stdout=log, stderr=subprocess.STDOUT)
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(f"Server exited with {proc.returncode}; inspect log")
        try:
            request(base, "/api/health", authenticated=False)
            return proc
        except (urllib.error.URLError, ConnectionError, TimeoutError):
            time.sleep(0.1)
    stop(proc)
    raise RuntimeError("Server did not become healthy within 30 seconds")


def stop(proc):
    proc.terminate()  # Same SIGTERM Render sends before redeploy.
    try:
        proc.wait(timeout=25)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
        raise RuntimeError("Graceful shutdown exceeded 25 seconds") from None
    if proc.returncode != 0:
        raise RuntimeError(f"Nonzero exit on SIGTERM: {proc.returncode}")


def usage(pid):
    """Linux /proc: process CPU seconds and resident memory MiB."""
    root = Path(f"/proc/{pid}")
    if not root.exists():
        return None
    fields = (root / "stat").read_text().rsplit(")", 1)[1].split()
    cpu = (int(fields[11]) + int(fields[12])) / os.sysconf("SC_CLK_TCK")
    rss = int((root / "statm").read_text().split()[1]) * os.sysconf("SC_PAGE_SIZE") / 1024**2
    return cpu, rss


def check(seconds=20.0):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    base = f"http://127.0.0.1:{port}"
    env = dict(os.environ)
    env.pop("BLXVERSE_PORT", None)
    env.update(PORT=str(port), BLXVERSE_HOST="0.0.0.0", RENDER="true",
               BLXVERSE_LLM_DISABLED="1", BLXVERSE_ACCESS_PASSWORD=PASSWORD)
    with tempfile.TemporaryDirectory(prefix="blx-render-") as temp:
        env["BLXVERSE_DATA_DIR"] = str(Path(temp) / "mounted-data")
        with open(Path(temp) / "server.log", "w+") as log:
            proc = None
            try:
                proc = boot(env, base, log)
                assert request(base, "/api/health", authenticated=False)["ok"]
                try:
                    request(base, "/api/state", authenticated=False)
                    raise AssertionError("Unauthenticated state request was not blocked")
                except urllib.error.HTTPError as exc:
                    assert exc.code == 401
                assert b"BLXVERSE" in request(base, "/")
                assert request(base, "/api/state")["setup"]
                request(base, "/api/new_game", {"name": "Render Check", "age": 27, "gender": "female"})
                request(base, "/api/speed", {"speed": 4})
                before = usage(proc.pid)
                started = time.monotonic()
                latencies = []
                rss = []
                # 4 polls/sec exceeds the normal client's 1 poll / 1.4 sec.
                while time.monotonic() - started < seconds:
                    tick = time.monotonic()
                    state = request(base, "/api/state")
                    assert len(state["npcs"]) == 72
                    latencies.append((time.monotonic() - tick) * 1000)
                    sample = usage(proc.pid)
                    if sample:
                        rss.append(sample[1])
                    time.sleep(max(0.0, 0.25 - (time.monotonic() - tick)))
                elapsed = time.monotonic() - started
                after = usage(proc.pid)
                request(base, "/api/speed", {"speed": 0})
                minute = request(base, "/api/state")["clock"]["minute"]
                stop(proc)
                proc = None
                saved = json.loads((Path(env["BLXVERSE_DATA_DIR"]) / "saves/world.json").read_text())
                assert saved["speed"] == 0
                proc = boot(env, base, log)
                restored = request(base, "/api/state")
                assert restored["player"]["name"] == "Render Check"
                assert restored["clock"]["speed"] == 0
                assert restored["clock"]["minute"] == minute
                for path in ("/api/world", "/api/calendar", "/api/journal", "/api/feed", "/api/save"):
                    assert request(base, path)
                stop(proc)
                proc = None
                ordered = sorted(latencies)
                return {
                    "result": "PASS", "python": sys.version.split()[0],
                    "duration_seconds": round(elapsed, 2), "speed": 4,
                    "state_requests": len(ordered),
                    "state_latency_p50_ms": round(ordered[len(ordered) // 2], 2),
                    "state_latency_p95_ms": round(ordered[min(len(ordered)-1, int(len(ordered)*0.95))], 2),
                    "cpu_percent_one_core": round((after[0] - before[0]) / elapsed * 100, 2) if before and after else None,
                    "rss_peak_mib": round(max(rss), 2) if rss else None,
                    "checks": ["PORT-only boot", "0.0.0.0 bind", "public health", "private game",
                               "static assets", "72 NPCs at 4x", "SIGTERM exit 0",
                               "same-disk restart", "saved player/clock/speed", "calendar and export"],
                    "note": "Local sandbox measurement, not a benchmark on Render hardware.",
                }
            finally:
                if proc is not None and proc.poll() is None:
                    stop(proc)
                log.seek(0)
                print(log.read(), file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seconds", type=float, default=20)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.seconds < 1:
        parser.error("--seconds must be at least 1")
    report = check(args.seconds)
    text = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text)
    print(text)


if __name__ == "__main__":
    main()
