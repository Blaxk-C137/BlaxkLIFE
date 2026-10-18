"""Render environment, access control, persistence, and server resource limits."""
from __future__ import annotations

import socket
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from blxverse import server
from scripts.render_check import check


def test_render_boot_and_persistent_restart():
    report = check(seconds=1)
    assert report["result"] == "PASS"
    assert report["state_requests"] >= 1


def test_optional_auth_challenges_before_reading_post_body(monkeypatch):
    monkeypatch.setenv("BLXVERSE_ACCESS_PASSWORD", "test-secret")
    # Run the real handler, but don't require a world or touch any local save.
    httpd = server.BoundedHTTPServer(("127.0.0.1", 0), server.Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        with socket.create_connection(httpd.server_address, timeout=3) as client:
            # Claim a big body but never send it: auth must reject immediately.
            client.sendall(b"POST /api/new_game HTTP/1.1\r\nHost: test\r\nContent-Length: 200\r\n\r\n")
            response = client.recv(4096)
            assert b"401 Unauthorized" in response
            assert b'Basic realm="BLXVERSE"' in response
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=2)


def test_static_symlink_cannot_escape_web_root(tmp_path, monkeypatch):
    web = tmp_path / "web"
    web.mkdir()
    secret = tmp_path / "private.txt"
    secret.write_text("not public")
    (web / "leak.txt").symlink_to(secret)
    monkeypatch.setattr(server, "WEB_DIR", str(web))
    monkeypatch.delenv("BLXVERSE_ACCESS_PASSWORD", raising=False)
    httpd = server.BoundedHTTPServer(("127.0.0.1", 0), server.Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        with socket.create_connection(httpd.server_address, timeout=3) as client:
            client.sendall(b"GET /leak.txt HTTP/1.1\r\nHost: test\r\nConnection: close\r\n\r\n")
            assert b"403 Forbidden" in client.recv(4096)
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=2)


def test_worker_count_is_bounded():
    httpd = server.BoundedHTTPServer(("127.0.0.1", 0), server.Handler)
    # The fixed capacity is independent of CPU count and incoming traffic.
    try:
        assert all(httpd.slots.acquire(blocking=False) for _ in range(32))
        assert not httpd.slots.acquire(blocking=False)
    finally:
        for _ in range(32):
            httpd.slots.release()
        httpd.server_close()


def test_port_precedence_and_concurrent_health(tmp_path, monkeypatch):
    import os

    from scripts.render_check import boot, request, stop

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    env = dict(os.environ, PORT="1", BLXVERSE_PORT=str(port),
               BLXVERSE_HOST="127.0.0.1", BLXVERSE_DATA_DIR=str(tmp_path / "data"))
    base = f"http://127.0.0.1:{port}"
    with (tmp_path / "server.log").open("w+") as log:
        proc = boot(env, base, log)
        try:
            with ThreadPoolExecutor(max_workers=8) as pool:
                replies = list(pool.map(lambda _: request(base, "/api/health", authenticated=False), range(32)))
            assert all(reply["ok"] for reply in replies)
        finally:
            stop(proc)
    assert Path(env["BLXVERSE_DATA_DIR"], "saves").is_dir()
