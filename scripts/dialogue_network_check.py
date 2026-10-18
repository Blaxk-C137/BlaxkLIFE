"""Isolated slow-provider integration: network must not freeze the town.
Uses a local OpenAI-compatible test endpoint; native Gemini payloads are tested
in tests/test_gemini.py. Never uses a real API key or the player's save.
"""
from __future__ import annotations

import json
import os
import socket
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from blxverse.engine.sim import Simulation  # noqa: E402
from scripts.render_check import PASSWORD, boot, request, stop  # noqa: E402

ACTIVE = threading.Event()
LINE = 'I have been making a playlist. What have you been listening to?'


class Provider(BaseHTTPRequestHandler):
    def do_POST(self):
        self.rfile.read(int(self.headers['Content-Length']))
        ACTIVE.set()
        time.sleep(1.4)
        body = json.dumps({'choices': [{'message': {'content': LINE}}]}).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def check():
    provider = ThreadingHTTPServer(('127.0.0.1', 0), Provider)
    threading.Thread(target=provider.serve_forever, daemon=True).start()
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    base = f'http://127.0.0.1:{port}'
    with tempfile.TemporaryDirectory(prefix='blx-dialogue-') as temp:
        data = Path(temp) / 'data'
        sim = Simulation.new(seed=20261017, player_spec={'name': 'Dialogue test'}, save_path=str(data / 'saves/world.json'))
        npc = sim.npcs[0]
        sim.player.x, sim.player.y = npc.x + 20, npc.y
        sim.adjust_rel(npc.id, 'player', familiarity=30)
        sim.save(force=True)
        env = dict(os.environ, PORT=str(port), BLXVERSE_DATA_DIR=str(data), BLXVERSE_HOST='0.0.0.0',
                   BLXVERSE_ACCESS_PASSWORD=PASSWORD, BLXVERSE_LLM_DISABLED='0',
                   BLXVERSE_LLM_API_KEY='fake-integration-test-only',
                   BLXVERSE_LLM_BASE_URL=f'http://127.0.0.1:{provider.server_port}/v1')
        for key in ('GEMINI_API_KEY', 'GOOGLE_API_KEY', 'BLXVERSE_PORT'):
            env.pop(key, None)
        with open(Path(temp) / 'server.log', 'w+') as log:
            proc = boot(env, base, log)
            polls = []
            try:
                with ThreadPoolExecutor() as workers:
                    for action in ({'type': 'talk', 'npc_id': npc.id, 'text': 'What music do you love?'},
                                   {'type': 'call_turn'}):
                        if action['type'] == 'call_turn':
                            call = request(base, '/api/action', {'type': 'call_start', 'npc_id': npc.id})
                            action.update(call_id=call['call_id'], text='How is your playlist?')
                        ACTIVE.clear()
                        future = workers.submit(request, base, '/api/action', action)
                        assert ACTIVE.wait(4), 'provider was not called'
                        first = request(base, '/api/state')['clock']['minute']
                        for _ in range(4):
                            t = time.monotonic()
                            state = request(base, '/api/state')
                            polls.append((time.monotonic() - t) * 1000)
                            time.sleep(.18)
                        assert state['clock']['minute'] > first, 'clock froze behind network'
                        result = future.result(timeout=6)
                        assert result['reply'] == LINE
                        assert '_remote_dialogue' not in result
                    request(base, '/api/action', {'type': 'call_end', 'call_id': call['call_id']})
                    request(base, '/api/speed', {'speed': 4})
                    request(base, '/api/action', {'type': 'message', 'npc_id': npc.id, 'text': 'Any new music recommendations?'})
                    deadline = time.monotonic() + 15
                    while time.monotonic() < deadline:
                        thread = request(base, f'/api/thread/{npc.id}')
                        if any(m['text'] == LINE for m in thread['messages']):
                            break
                        time.sleep(.2)
                    else:
                        raise AssertionError('remote text reply was never delivered')
                assert max(polls) < 500, polls
                return {'result': 'PASS', 'checks': ['slow chat provider does not block polling or clock',
                        'slow call provider does not block polling or clock', 'remote reply delivered to text thread',
                        'server strips private dialogue context'], 'max_state_latency_ms': round(max(polls), 2),
                        'note': 'Local mocked provider. Not a live Gemini API test.'}
            finally:
                stop(proc)
                provider.shutdown()


if __name__ == '__main__':
    result = check()
    text = json.dumps(result, indent=2)
    (Path(__file__).resolve().parents[1] / 'docs/dialogue-network-check.json').write_text(text + '\n')
    print(text)
