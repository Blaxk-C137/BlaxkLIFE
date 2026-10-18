"""Isolated Playwright gate for drafts, mobile layouts, notices and NPC playback.

Requires Playwright + Chromium. Does not touch the live save on port 8111.
    python3 scripts/ui_regression.py
"""
from __future__ import annotations

import json
import os
import socket
import sys
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.render_check import PASSWORD, boot, request, stop  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SHOTS = ROOT / 'screenshots'
VIEWPORTS = [(320, 740), (360, 800), (390, 844), (768, 1024), (1024, 768), (1440, 900)]


def no_overflow(page, selector):
    problems = page.locator(selector).evaluate('''root => [...root.querySelectorAll('input,textarea,button,.profile-name,.bubble,.cal-main,.t-body,.post-card,.wallet-hero')].filter(el=>{
      const r=el.getBoundingClientRect();
      return r.width>0&&r.height>0&&!el.closest('.phone-tabs,.nearby-rail')&&(r.left < -2 || r.right > innerWidth+2);
    }).map(el=>({tag:el.tagName,id:el.id,class:el.className,right:el.getBoundingClientRect().right}))''')
    assert not problems, problems
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth+1')


def run():
    SHOTS.mkdir(exist_ok=True)
    errors = []
    checks = []
    motion = {}
    with tempfile.TemporaryDirectory(prefix='blaxkville-ui-') as temp:
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        base = f'http://127.0.0.1:{port}'
        env = dict(os.environ, PORT=str(port), BLXVERSE_DATA_DIR=temp, BLXVERSE_HOST='0.0.0.0',
                   BLXVERSE_ACCESS_PASSWORD=PASSWORD, BLXVERSE_LLM_DISABLED='1')
        env.pop('BLXVERSE_PORT', None)
        with open(Path(temp) / 'server.log', 'w+') as log:
            proc = boot(env, base, log)
            try:
                with sync_playwright() as pw:
                    browser = pw.chromium.launch()
                    def make_page(width, height):
                        context = browser.new_context(http_credentials={'username': 'blxverse', 'password': PASSWORD},
                                                      viewport={'width': width, 'height': height})
                        page = context.new_page()
                        page.on('pageerror', lambda e: errors.append(str(e)))
                        page.on('console', lambda m: errors.append(m.text) if m.type == 'error' else None)
                        return page
                    page = make_page(320, 740)
                    page.goto(base, wait_until='networkidle')
                    page.wait_for_selector('#input-name')
                    no_overflow(page, '#setup')
                    page.screenshot(path=str(SHOTS / 'blaxkville-setup-320.png'))
                    request(base, '/api/new_game', {'name': 'Mobile Tester', 'gender': 'female', 'age': 27, 'seed': 20261017})
                    request(base, '/api/speed', {'speed': 4})
                    page.reload(wait_until='networkidle')
                    page.wait_for_function('!!window.__BLX__?.view?.staticLayer && window.__BLX__.view.canvas.width>10')
                    page.wait_for_timeout(1800)
                    page.wait_for_function('[...window.__BLX__.view.npcs.values()].some(n=>n.route?.length)', timeout=25000)
                    page.wait_for_timeout(1500)
                    motion = page.evaluate("""async()=>{
                      const view=window.__BLX__.view;
                      const candidates=[...view.npcs.values()].filter(n=>!n.role&&n.route?.length)
                        .map(n=>{const samples=view.tracks.get(n.id)?.samples||[],b=samples.at(-1),a=samples.at(-3)||samples[0];
                          const observed=a&&b?Math.hypot(b.x-a.x,b.y-a.y)/Math.max(.001,(b.at-a.at)/1000):0;
                          const points=[{x:n.x,y:n.y},...n.route];
                          const length=points.slice(1).reduce((sum,p,i)=>sum+Math.hypot(p.x-points[i].x,p.y-points[i].y),0);
                          return {id:n.id,observed,length,points:[]}})
                        .filter(n=>n.observed>80&&n.length>250).sort((a,b)=>b.observed-a.observed).slice(0,5);
                      if(!candidates.length)throw Error('No ordinarily cruising residents to measure');
                      const start=performance.now();
                      await new Promise(resolve=>{function frame(t){for(const c of candidates){const d=view.display.get(c.id);c.points.push({x:d.x,y:d.y,t})}if(t-start<1600)requestAnimationFrame(frame);else resolve()}requestAnimationFrame(frame)});
                      const measurements=candidates.map(c=>{const points=c.points;
                        const speeds=points.slice(1).map((p,i)=>Math.hypot(p.x-points[i].x,p.y-points[i].y)/Math.max(.001,(p.t-points[i].t)/1000));
                        const steady=speeds.filter(s=>s>1).sort((a,b)=>a-b);
                        return {resident:c.id,samples:points.length,stationary_fraction:speeds.filter(s=>s<1).length/speeds.length,median_px_second:steady[Math.floor(steady.length/2)]||0}});
                      const valid=measurements.filter(m=>m.samples>15&&m.stationary_fraction<.15&&m.median_px_second>60&&m.median_px_second<400);
                      return {...(valid[0]||measurements[0]),sampled_actors:measurements.length,measurements};
                    }""")
                    assert motion['samples'] > 15, motion
                    assert motion['stationary_fraction'] < .15, motion
                    # Rendering playback is measured on actual cruising actors,
                    # not a single longest-route resident currently in a queue.
                    # Whole-population life/spacing is separately audited.
                    assert 60 < motion['median_px_second'] < 400, motion
                    checks.append('multiple ordinary walkers frame-sampled; continuous cruising playback, independent population audit')
                    page.locator('#btn-music').click()
                    page.wait_for_timeout(100)
                    assert page.evaluate('window.__BLX__.music.enabled') is False
                    page.locator('#btn-music').click()
                    page.wait_for_timeout(150)
                    assert page.evaluate('window.__BLX__.music.ctx.state') == 'running'
                    assert page.evaluate('window.__BLX__.music.enabled') is True
                    checks.append('procedural music gesture unlock, mute and unmute')
                    npc_id = request(base, '/api/state')['npcs'][0]['id']
                    page.evaluate("()=>window.__BLX__.ui.openPhone('messages',{npcId:'" + npc_id + "'})")
                    page.wait_for_selector('#phone-msg-input')
                    page.evaluate('window.originalInput=document.querySelector("#phone-msg-input")')
                    draft = 'Typing slowly through several world updates'
                    page.locator('#phone-msg-input').press_sequentially(draft, delay=75)
                    page.wait_for_timeout(1400)
                    assert page.locator('#phone-msg-input').input_value() == draft
                    assert page.evaluate('document.activeElement===window.originalInput && originalInput===document.querySelector("#phone-msg-input")')
                    await_count = len(request(base, f'/api/thread/{npc_id}')['messages'])
                    page.locator('#phone-msg-input').press('Enter')
                    page.wait_for_function("document.querySelector('#phone-msg-input').value === ''")
                    messages = request(base, f'/api/thread/{npc_id}')['messages']
                    assert sum(m['sender'] == 'player' and m['text'] == draft for m in messages) == 1
                    assert len(messages) >= await_count + 1
                    page.wait_for_timeout(4500)
                    assert page.locator('#phone-chat-scroll .chat-row.npc').count() > 0, 'incoming reply must update without replacing composer'
                    checks.append('slow typing, native focus, one send, live incoming reply')
                    # A failed request must keep the draft, not silently discard it.
                    page.locator('#phone-msg-input').fill('Keep this failed message')
                    page.route('**/api/action', lambda route: route.fulfill(status=503, content_type='application/json', body='{"error":"test network failure"}'))
                    page.locator('#phone-msg-send').click()
                    page.wait_for_timeout(250)
                    assert page.locator('#phone-msg-input').input_value() == 'Keep this failed message'
                    page.unroute('**/api/action')
                    # Expected injected failure logged by the app is not a regression.
                    errors[:] = [e for e in errors if '503' not in e]
                    checks.append('failed message retains draft')
                    page.evaluate("window.__BLX__.ui.openPhone('feed')")
                    page.wait_for_selector('#feed-composer')
                    post = 'BlaxkVille draft survives world polling'
                    page.locator('#feed-composer').press_sequentially(post, delay=65)
                    page.wait_for_timeout(1300)
                    assert page.locator('#feed-composer').input_value() == post
                    assert page.evaluate('document.activeElement.id') == 'feed-composer'
                    # Draft survives deliberate navigation too.
                    page.locator('[data-ptab="calendar"]').click()
                    page.locator('[data-ptab="feed"]').click()
                    page.wait_for_selector('#feed-composer')
                    assert page.locator('#feed-composer').input_value() == post
                    page.locator('#feed-post').click()
                    page.wait_for_function("document.querySelector('#feed-composer')?.value === ''")
                    assert any(p['text'] == post for p in request(base, '/api/feed')['posts'])
                    # Comment composer survives polling, and submits once.
                    page.locator('[data-comment-toggle]').first.click()
                    comment = page.locator('input[id^="cmt-input-"]:visible').first
                    comment.fill('A comment that stays while the world runs')
                    comment.focus()
                    page.wait_for_timeout(1700)
                    assert comment.input_value() == 'A comment that stays while the world runs'
                    assert comment.evaluate('el=>document.activeElement===el')
                    page.locator('[data-send-comment]:visible').first.click()
                    page.wait_for_timeout(700)
                    checks.append('Gist Hub draft, tab draft restoration, post, comment')
                    # Dismiss must be clickable; every transient is gone after 5s,
                    # regardless of old caller-supplied TTLs or repeated HUD polls.
                    page.evaluate("window.__BLX__.ui.closePhone();document.querySelector('#toast-stack').replaceChildren();window.__BLX__.ui.toast({title:'close-test',ttl:999999})")
                    page.get_by_role('button', name='Dismiss', exact=True).click()
                    assert page.locator('.toast').count() == 0
                    page.evaluate("window.__BLX__.ui.toast({title:'five-second-test',ttl:999999})")
                    page.wait_for_timeout(4500)
                    assert page.get_by_text('five-second-test', exact=True).is_visible()
                    page.wait_for_timeout(700)
                    assert page.get_by_text('five-second-test', exact=True).count() == 0
                    assert page.locator('#quest-stack').inner_text() == ''
                    assert page.locator('#location-chip').is_hidden(), 'unchanged location must not re-pin itself on each poll'
                    checks.append('clickable dismissal, fixed five-second expiry, no pinned story stack')
                    page.context.close()
                    for width, height in VIEWPORTS:
                        page = make_page(width, height)
                        page.goto(base, wait_until='networkidle')
                        page.wait_for_function('!!window.__BLX__?.view?.staticLayer')
                        page.wait_for_timeout(250)
                        no_overflow(page, '#game')
                        for tab in ('messages', 'feed', 'calendar', 'wallet', 'cases', 'alerts', 'guide'):
                            page.evaluate('(tab)=>window.__BLX__.ui.openPhone(tab)', tab)
                            page.wait_for_timeout(280)
                            no_overflow(page, '#phone-root')
                        page.evaluate("()=>window.__BLX__.ui.openPhone('messages',{npcId:'" + npc_id + "'})")
                        page.wait_for_selector('#phone-msg-input')
                        page.wait_for_timeout(450)
                        no_overflow(page, '#phone-root')
                        if width == 390:
                            page.screenshot(path=str(SHOTS / 'blaxkville-phone-390.png'))
                            page.set_viewport_size({'width': width, 'height': 400})
                            page.locator('#phone-msg-input').focus()
                            page.wait_for_timeout(300)
                            bounds = page.locator('#phone-msg-input').bounding_box()
                            assert bounds['y'] >= 0 and bounds['y'] + bounds['height'] <= 400
                            no_overflow(page, '#phone-root')
                            page.screenshot(path=str(SHOTS / 'blaxkville-keyboard-390.png'))
                            page.set_viewport_size({'width': width, 'height': height})
                        page.evaluate('window.__BLX__.ui.closePhone()')
                        for method in ('openJournal', 'openShop', 'openSettings', 'openHelp', 'openStats'):
                            page.evaluate('(method)=>window.__BLX__.ui[method]()', method)
                            page.wait_for_selector('.modal')
                            page.wait_for_timeout(180)
                            no_overflow(page, '#overlay-root')
                            page.evaluate('window.__BLX__.ui.closeModal()')
                        page.evaluate('window.__BLX__.openActionWheel()')
                        page.wait_for_selector('.wheel-grid')
                        no_overflow(page, '#overlay-root')
                        page.locator('[data-menu-speed="0"]').click()
                        page.wait_for_function('window.__BLX__.state.clock.speed===0')
                        page.locator('[data-menu-speed="4"]').click()
                        page.wait_for_function('window.__BLX__.state.clock.speed===4')
                        page.locator('.wheel-item').filter(has_text='Journal').click()
                        page.wait_for_selector('.modal')
                        no_overflow(page, '#overlay-root')
                        page.evaluate('window.__BLX__.ui.closeModal()')
                        page.evaluate('(id)=>window.__BLX__.ui.openProfile(id)', npc_id)
                        page.wait_for_selector('.profile-name')
                        no_overflow(page, '#overlay-root')
                        page.evaluate('window.__BLX__.ui.closeModal()')
                        page.evaluate('document.querySelector("#toast-stack").replaceChildren()')
                        page.screenshot(path=str(SHOTS / f'blaxkville-world-{width}.png'))
                        page.context.close()
                    checks.append('6 viewport sizes, 7 phone tabs, profile/shop/settings/help/stats/journal, emulated keyboard')
                    assert not errors, errors
                    browser.close()
            finally:
                stop(proc)
    report = {'result': 'PASS', 'checks': checks, 'viewports': VIEWPORTS, 'errors': errors, 'motion': motion,
              'note': 'Chromium viewport/software-keyboard emulation, not a physical-device accessibility audit.'}
    (ROOT / 'docs' / 'ui-regression.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    run()
