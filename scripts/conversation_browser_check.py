"""Isolated 0.6 UI proof: long real threads, cross-channel recall and visible composers."""
from __future__ import annotations

import json
import os
import socket
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from playwright.sync_api import sync_playwright  # noqa: E402

from blxverse.engine import actions, conversation  # noqa: E402
from blxverse.engine.sim import Simulation  # noqa: E402
from scripts.render_check import PASSWORD, boot, stop  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
VIEWPORTS = [(320, 740), (390, 844), (768, 1024), (1024, 768), (1440, 900), (390, 440)]


def visible_inside(page, control, container):
    result = page.evaluate('''([control,container])=>{const c=document.querySelector(control),p=document.querySelector(container);const a=c.getBoundingClientRect(),b=p.getBoundingClientRect();return {visible:a.width>0&&a.height>0,inside:a.top>=b.top-1&&a.bottom<=b.bottom+1&&a.left>=b.left-1&&a.right<=b.right+1,a:a.toJSON(),b:b.toJSON()}}''', [control, container])
    assert result['visible'] and result['inside'], result


def bottom(page, selector):
    page.wait_for_function('(selector)=>{const el=document.querySelector(selector);return el.scrollHeight-el.scrollTop-el.clientHeight<3}', arg=selector, timeout=2500)


def run():
    errors, checks = [], []
    (ROOT/'screenshots').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='blax-chat-ui-') as temp:
        data = Path(temp)/'data'
        sim = Simulation.new(20261017, {'name': 'Conversation Tester'}, save_path=str(data/'saves/world.json'))
        sim.world_flags['chain'].update(started=True, stage=1)
        sim.speed = 0
        npc = sim.npcs[12]
        npc.x, npc.y, npc.status, npc.location_id = 500, 640, 'at', 'square'
        npc.target = None
        npc.schedule = {'weekday': [], 'weekend': []}
        sim.player.x, sim.player.y = 500, 660
        sim.adjust_rel(npc.id, 'player', familiarity=65, trust=50, tension=-100)
        for i in range(35):
            actions.act_message(sim, {'npc_id': npc.id, 'text': f'Earlier text {i}: this is a long conversation, not a fresh empty panel.'})
            sim.send_npc_message(npc.id, f'Earlier reply {i}: we are checking that the composer stays visible.')
        actions.act_message(sim, {'npc_id': npc.id, 'text': 'My umbrella is blue and I left it at the cafe.'})
        conversation.record(sim, npc, 'I have an interview on Friday.', 'How are preparations going?', 'call')
        sim.world_flags['pending_messages'] = []
        sim.save(force=True)
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        base = f'http://127.0.0.1:{port}'
        env = dict(os.environ, PORT=str(port), BLXVERSE_DATA_DIR=str(data), BLXVERSE_HOST='0.0.0.0', BLXVERSE_ACCESS_PASSWORD=PASSWORD, BLXVERSE_LLM_DISABLED='1')
        env.pop('BLXVERSE_PORT', None)
        with open(Path(temp)/'server.log', 'w+') as log:
            proc = boot(env, base, log)
            try:
                with sync_playwright() as pw:
                    browser = pw.chromium.launch()
                    context = browser.new_context(http_credentials={'username': 'blxverse', 'password': PASSWORD})
                    page = context.new_page()
                    page.on('pageerror', lambda e: errors.append(str(e)))
                    for width, height in VIEWPORTS:
                        page.set_viewport_size({'width': width, 'height': height})
                        page.goto(base, wait_until='networkidle')
                        page.wait_for_function('window.__BLX__?.state?.npcs?.length>0')
                        page.evaluate('(id)=>window.__BLX__.ui.openTalk(id)', npc.id)
                        page.wait_for_selector('#talk-input')
                        assert 'umbrella' in page.locator('#talk-scroll').inner_text()
                        page.fill('#talk-input', 'Do you remember my umbrella?')
                        page.click('#talk-send')
                        page.wait_for_function("document.querySelector('#talk-scroll').dataset.sending!=='1'")
                        assert 'blue' in page.locator('#talk-scroll .npc').last.inner_text()
                        visible_inside(page, '#talk-input', '.talk-modal')
                        visible_inside(page, '#talk-send', '.talk-modal')
                        bottom(page, '#talk-scroll')
                        assert page.input_value('#talk-input') == ''
                        visible_inside(page, '[data-t=profile]', '.talk-modal')
                        visible_inside(page, '[data-t=phone]', '.talk-modal')
                        assert page.locator('.talk-options').evaluate('(el)=>!el.open')
                        page.screenshot(path=str(ROOT/f'screenshots/blaxkville-06-talk-{width}x{height}.png'))
                        page.keyboard.press('Escape')
                        page.evaluate('(id)=>window.__BLX__.ui.openPhone("messages",{npcId:id})', npc.id)
                        page.wait_for_selector('#phone-msg-input')
                        scroll = page.locator('#phone-chat-scroll')
                        scroll.evaluate('(el)=>el.scrollTop=0')
                        message = f'My own newest message at {width}x{height}'
                        page.fill('#phone-msg-input', message)
                        page.click('#phone-msg-send')
                        page.wait_for_function('(text)=>[...document.querySelectorAll("#phone-chat-scroll .player")].some(el=>el.textContent.includes(text))', arg=message)
                        page.wait_for_timeout(150)
                        bottom(page, '#phone-chat-scroll')
                        visible_inside(page, '#phone-msg-input', '.phone')
                        page.screenshot(path=str(ROOT/f'screenshots/blaxkville-06-text-{width}x{height}.png'))
                        page.evaluate('window.__BLX__.ui.closePhone()')
                        page.evaluate('(id)=>window.__BLX__.ui.startCall(id)', npc.id)
                        page.wait_for_selector('#call-input-text', state='visible')
                        page.evaluate('()=>{for(let i=0;i<25;i++)window.__BLX__.ui.addCallCaption("Tester",`Earlier caption ${i}`,i%2?"player":"npc")}')
                        page.fill('#call-input-text', 'Remember my umbrella?')
                        page.click('#call-send-text')
                        page.wait_for_function('document.querySelector("#call-captions").lastElementChild.textContent.includes("blue")')
                        visible_inside(page, '#call-input-text', '#call-root')
                        visible_inside(page, '#call-end', '#call-root')
                        assert page.evaluate('document.querySelector("#call-captions").getBoundingClientRect().bottom<=document.querySelector("#call-compose").getBoundingClientRect().top+1')
                        bottom(page, '#call-captions')
                        page.evaluate('()=>{const ui=window.__BLX__.ui;ui.setCallCaption("first partial",true);ui.setCallCaption("corrected partial",true);if(document.querySelectorAll("#call-captions .provisional").length!==1)throw Error("duplicate partials");window.__beforeTurns=ui.callSession.turns;ui.sendCallTurn("How far?");ui.sendCallTurn("Remember my umbrella?");}')
                        page.wait_for_function('window.__BLX__.ui.callSession.turns>=window.__beforeTurns+2')
                        assert page.locator('#call-captions .provisional').count() == 0
                        bottom(page, '#call-captions')
                        assert page.locator('#call-captions .player').count() > 5
                        page.screenshot(path=str(ROOT/f'screenshots/blaxkville-06-call-{width}x{height}.png'))
                        page.click('#call-end')
                        checks.append(f'{width}x{height}: long talk/text/call logs, actual cross-channel recall, newest message scroll, visible composer, no call overlap')
                    browser.close()
            finally:
                stop(proc)
    assert not errors, errors
    report = {'result': 'PASS', 'checks': checks, 'errors': errors, 'note': 'Isolated offline synthetic conversation fixture in Chromium; final 390x440 viewport simulates reduced keyboard space, not physical device testing.'}
    (ROOT/'docs/conversation-browser-check-0.6.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    run()
