/* =========================================================================
   BLXVERSE — app shell
   Boots the API client, world canvas, voice engine and UI panels, then
   keeps a light poll loop so the HUD reflects the living simulation.
   ========================================================================= */
import { BackgroundMusic } from './music.js';
import { WorldView } from './world.js';
import { Voice } from './voice.js';
import { UI } from './ui.js';
import { avatarUrl } from './art.js';

const POLL_FAST = 600;
const POLL_SLOW = 4200;

class ApiError extends Error {
  constructor(message, code, status) {
    super(message);
    this.code = code;
    this.status = status;
  }
}

const App = {
  state: null,
  world: null,
  apiHealthy: false,
  lastActionAt: 0,

  async init() {
    this.music = new BackgroundMusic();
    const unlockMusic = () => this.music.start().catch(() => {});
    document.addEventListener('pointerdown', unlockMusic, { once: true });
    document.addEventListener('keydown', unlockMusic, { once: true });
    this.cache = new Map();
    this.lastRefresh = 0;
    this.refreshPending = null;
    this.voice = new Voice({
      soundEnabled: true,
      onPartial: (t, f) => this.ui.onVoicePartial(t, f),
      onFinal: (t) => this.ui.onVoiceFinal(t),
      onState: (s) => this.ui.onVoiceState(s),
      onLevel: (l) => this.ui.onVoiceLevel(l),
      onError: (msg) => this.ui.toast({ title: 'Voice', body: msg, kind: 'danger' }),
      onMetric: (kind, ms, extra) => this.reportMetric(kind, ms, extra),
      onSpeakStart: () => { this.setTalking(true); this.music.duck(true); },
      onSpeakEnd: () => { this.setTalking(false); this.music.duck(!!this.ui.callSession); },
      onBargeIn: () => this.ui.onBargeIn(),
    });

    this.ui = new UI(this);

    const canvas = document.getElementById('world');
    this.view = new WorldView(canvas, {
      onMove: (x, y, keyboard) => this.walkTo(x, y, null, keyboard),
      onNpc: (id) => { if (id === 'player') this.ui.openPlayerProfile(); else this.ui.openProfile(id); },
      onLocation: (id) => this.ui.openVenue(id),
      onHome: () => this.ui.toast({ title: 'Home', body: 'This is someone\'s home. Yours is the mint door on Juniper Row.', kind: 'info' }),
      onHover: (hit, pt) => this.onHover(hit, pt),
    });

    this.wireChrome();
    this.wireKeys();

    document.getElementById('boot').classList.remove('hidden');
    this.setBoot('Connecting to the block…', 10);

    await this.boot();
  },

  setBoot(msg, pct) {
    const el = document.getElementById('boot-status');
    const bar = document.getElementById('boot-bar');
    if (el) el.textContent = msg;
    if (bar) bar.style.width = `${pct}%`;
  },

  async boot() {
    try {
      const health = await this.apiGet('/api/health');
      this.apiHealthy = true;
      this.configInfo = health;
      this.setBoot('Waking the neighborhood…', 35);
    } catch (e) {
      this.setBoot('Server unreachable — is run_server.py running?', 100);
      document.getElementById('boot').classList.add('error');
      setTimeout(() => this.boot(), 3000);
      return;
    }

    this.setBoot('Loading residents and venues…', 55);
    try {
      this.world = await this.apiGet('/api/world');
      document.getElementById('boot').classList.add('hidden');
      document.getElementById('setup').classList.remove('hidden');
      const st = await this.apiGet('/api/state').catch(() => null);
      this.state = st;
      if (st && !st.setup) {
        this.startGame(st);
        this.ui.toast({ title: 'Welcome back', body: `The block kept moving while you were away. It's ${st.clock.label}.`, kind: 'good', ttl: 6000 });
      } else {
        this.ui.initSetup(this.world, {
          existingName: st?.existing_player_name,
          overwrite: !!st?.has_save,
        });
        this.existingWorld = !!st?.has_save;
        this.setBoot('Ready.', 100);
      }
    } catch (e) {
      document.getElementById('boot').classList.remove('hidden');
      document.getElementById('boot').classList.add('error');
      this.setBoot(`Could not load the world: ${e.message}. Reload to retry.`, 100);
      console.error(e);
    }
  },

  /* ------------------------------------------------------------------ HTTP */
  async api(path, { method = 'GET', body = null, timeout = 25000 } = {}) {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), timeout);
    try {
      const res = await fetch(path, {
        method,
        headers: body ? { 'Content-Type': 'application/json' } : undefined,
        body: body ? JSON.stringify(body) : undefined,
        signal: ctrl.signal,
        cache: 'no-store',
      });
      const text = await res.text();
      let data = {};
      try { data = text ? JSON.parse(text) : {}; } catch { data = { error: text.slice(0, 200) }; }
      if (!res.ok) {
        throw new ApiError(data.error || data.message || `Request failed (${res.status})`, data.code || 'http_' + res.status, res.status);
      }
      return data;
    } catch (err) {
      if (err.name === 'AbortError') throw new ApiError('The block took too long to answer. Try again.', 'timeout', 504);
      throw err;
    } finally {
      clearTimeout(timer);
    }
  },

  apiGet(path) { return this.api(path); },

  async createWorld(opts) {
    const res = await this.api('/api/new_game', {
      method: 'POST',
      body: { name: opts.name, gender: opts.gender, age: opts.age, look: opts.look, overwrite: opts.overwrite || this.existingWorld === true },
    });
    if (res.world && (res.world.locations || []).length) this.world = res.world;
    this.state = res;
    this.existingWorld = false;
    this.startGame(res, true);
    this.ui.toast({ title: `Welcome to BlaxkVille, ${opts.name.split(' ')[0]}`, body: 'Your apartment is the mint door on Juniper Row. The block is already awake.', kind: 'good', ttl: 7000 });
  },

  async continueWorld() {
    const st = await this.apiGet('/api/state');
    if (st && !st.setup) { this.state = st; this.startGame(st); }
  },

  async startNewWorld() {
    this.stopLoop();
    this.ui.closePhone();
    document.getElementById('game').classList.add('hidden');
    document.getElementById('setup').classList.remove('hidden');
    this.ui.initSetup(this.world, { existingName: this.state?.player?.name, overwrite: true });
    const err = document.getElementById('creator-error');
    if (err) err.textContent = 'Starting a new world will replace the current one. Confirm to continue.';
  },

  /* ------------------------------------------------------------------ game */
  startGame(state, fresh = false) {
    document.getElementById('setup').classList.add('hidden');
    document.getElementById('game').classList.remove('hidden');
    this.state = state;
    this.view.load(this.world);
    this.view.setState(state);
    this.view.resize();
    this.view.centerOnPlayer();
    this.ui.renderHUD(state);
    this.startLoop();
    if (fresh) {
      setTimeout(() => this.ui.toast({ title: 'Press H for help', body: 'Click the ground to walk. Click a building to see what you can do there.', kind: 'info', ttl: 8000 }), 1600);
    }
    if (state.pending_call) setTimeout(() => this.ui.showIncomingCall(state.pending_call), 2600);
  },

  startLoop() {
    this.stopLoop();
    const tick = async () => {
      if (document.hidden || this.pollInFlight) return;
      this.pollInFlight = true;
      const epoch = this.mutationEpoch || 0;
      try {
        const st = await this.apiGet('/api/state');
        if (epoch === (this.mutationEpoch || 0)) this.applyState(st);
      } catch { /* transient */ }
      finally { this.pollInFlight = false; }
    };
    this.pollTimer = setInterval(tick, POLL_FAST);
    this.slowTimer = setInterval(() => this.checkAtmosphere(), 30000);
    tick();
  },

  stopLoop() {
    clearInterval(this.pollTimer);
    clearInterval(this.slowTimer);
  },

  applyState(st) {
    if (!st || st.setup) return;
    const prev = this.state;
    this.state = st;
    this.view.setState(st);
    this.ui.renderHUD(st);
    this.ui.refreshOpenPanel();
    this.diffState(prev, st);
  },

  diffState(prev, next) {
    if (!prev || !next) return;
    const prevCall = prev.pending_call;
    const nextCall = next.pending_call;
    if (nextCall && !this.ui.callSession && (!prevCall || prevCall.call_id !== nextCall.call_id)) {
      this.ui.showIncomingCall(nextCall);
    }
    if (!nextCall && prevCall) this.ui.dismissRing();
    if ((next.last_event?.id ?? null) !== (prev.last_event?.id ?? null) && next.last_event?.kind === 'slapstick') {
      const ev = next.last_event;
      this.view.playChaos(ev.x ?? this.view.player?.x ?? 900, ev.y ?? this.view.player?.y ?? 800, ev.short || 'BOING!');
      this.voice.tone('chaos');
      this.ui.toast({ title: 'Cartoon chaos', body: ev.summary, kind: 'story', ttl: 6500 });
    }
    const newNotifs = (next.notifications || []).filter(n => !(prev.notifications || []).some(p => p.id === n.id && p.minute === n.minute));
    for (const n of newNotifs.slice(-2)) {
      if (n.kind === 'call') continue;
      this.ui.toast({ title: n.title, body: n.body, kind: n.kind === 'story' ? 'story' : n.kind === 'message' ? 'message' : 'info' });
      if (n.kind === 'story') this.voice.tone('good');
    }
    if (next.clock.day !== prev.clock.day) {
      this.ui.toast({ title: `Day ${next.clock.day}`, body: `${next.clock.weekday} on BlaxkVille. Rent is ${this.world?.config?.rent ?? 32} BLX, due 09:00.`, kind: 'info', ttl: 7000 });
    }
  },

  async doAction(type, payload = {}) {
    if(this.inputLocked&&!['work','talk_end','dismiss_notifications'].includes(type))throw new ApiError('Finish your shift first.','busy',423);
    const now = performance.now();
    if (now - this.lastActionAt < 120) await new Promise(r => setTimeout(r, 120));
    this.lastActionAt = performance.now();
    const epoch = this.mutationEpoch = (this.mutationEpoch || 0) + 1;
    const res = await this.api('/api/action', { method: 'POST', body: { type, ...payload } });
    if (res.state && epoch === this.mutationEpoch) this.applyState(res.state);
    if (res.cooldown_ms) await new Promise(r => setTimeout(r, 0));
    return res;
  },

  walkTo(x, y, onArrive = null, keyboard = false) {
    if(this.inputLocked)return;
    const px = this.view.playerDisplay.x;
    const py = this.view.playerDisplay.y;
    if (!keyboard && Math.hypot(x - px, y - py) < 18) return;
    if (!keyboard) this.view.setDestinationMarker(x, y);
    // No optimistic hop: the sprite only ever walks the server's real A*
    // route, so it can neither cut through a building nor jump ahead of the
    // authoritative position and get snapped back a poll later.
    const request = this.moveRequest = (this.moveRequest || 0) + 1;
    this.doAction('move', { x: Math.round(x), y: Math.round(y) }).then(res => {
      if (request !== this.moveRequest) return;
      if (res?.route) this.view.setRoute(res.route, res.target);
      if (onArrive) setTimeout(onArrive, 350);
    }).catch(() => { if (request === this.moveRequest) this.view.clearRoute(); });
  },

  async checkAtmosphere() {
    // The fast loop already refreshes state; a second concurrent poll could
    // return out of order on a slow mobile connection.
  },

  onHover(hit, pt) {
    const tip = document.getElementById('hover-tip');
    if (!tip) return;
    if (!hit || hit.type === 'ground') { tip.classList.add('hidden'); return; }
    let text = '';
    if (hit.type === 'npc') {
      const n = this.ui.npc(hit.id) || this.view.player;
      if (!n) { tip.classList.add('hidden'); return; }
      text = hit.id === 'player' ? 'You' : `${n.name} · ${n.occupation || ''}`;
    } else if (hit.type === 'location') {
      const l = this.ui.loc(hit.id);
      text = l ? `${l.icon} ${l.name} — click to open` : '';
    } else if (hit.type === 'home') {
      text = 'Home — someone lives here';
    }
    if (!text) { tip.classList.add('hidden'); return; }
    tip.textContent = text;
    tip.classList.remove('hidden');
    const rect = this.view.canvas.getBoundingClientRect();
    tip.style.left = `${Math.min(window.innerWidth - 250, rect.left + (pt?.x ?? 0)) + 14}px`;
    tip.style.top = `${Math.min(window.innerHeight - 48, rect.top + (pt?.y ?? 0)) + 16}px`;
  },

  setTalking(on) {
    const chip = document.getElementById('voice-live');
    if (chip) chip.classList.toggle('on', !!on);
  },

  reportMetric(kind, ms, extra = {}) {
    if (!Number.isFinite(ms) || ms < 0 || ms > 120000) return;
    try {
      fetch('/api/voice/metric', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ stage: kind, ms: Math.round(ms), meta: extra || {} }),
        keepalive: true,
      });
    } catch { /* noop */ }
  },

  async ensureMicConsent(quiet = false) {
    if (this.voice.micReady) return true;
    if (!(await this.ui.confirmMic())) {
      if (!quiet) this.ui.toast({ title: 'Microphone off', body: 'You can type your side of every conversation instead.', kind: 'info' });
      return false;
    }
    const ok = await this.voice.requestMic();
    if (!ok && !quiet) this.ui.toast({ title: 'Mic blocked', body: 'Browser permission is off for this site. Voice input will stay unavailable; typing still works.', kind: 'danger' });
    return ok;
  },

  /* ------------------------------------------------------------------ chrome */
  wireChrome() {
    const $ = (s) => document.querySelector(s);
    const musicButton = $('#btn-music');
    const musicLabel = () => {
      musicButton.setAttribute('aria-pressed', String(this.music.enabled));
      musicButton.title = this.music.enabled ? 'Background music on — mute' : 'Background music off — enable';
      musicButton.textContent = this.music.enabled ? '♫' : '♪';
    };
    musicLabel();
    onClick('#btn-music', async () => { await this.music.toggle().catch(() => {}); musicLabel(); });
    onClick('#btn-phone', () => this.ui.openPhone('messages'));
    onClick('#btn-menu', () => this.openActionWheel());
    onClick('#btn-help', () => this.ui.openHelp());
    document.querySelectorAll('.side-tab').forEach(t => t.addEventListener('click', () => this.ui.switchSideTab(t.dataset.tab)));
    document.querySelectorAll('.speed').forEach(b => b.addEventListener('click', () => this.setSpeed(Number(b.dataset.speed))));
    onClick('#zoom-in', () => this.view.setZoom(0.12));
    onClick('#zoom-out', () => this.view.setZoom(-0.12));
    onClick('#zoom-home', () => { this.view.zoomTo(1.15); this.view.centerOnPlayer(); });
    onClick('#btn-newgame', () => this.ui.openSettings());
  },

  async setSpeed(speed) {
    try {
      await this.api('/api/speed', { method: 'POST', body: { speed } });
      document.querySelectorAll('.speed').forEach(b => b.classList.toggle('active', Number(b.dataset.speed) === speed));
      const label = { 0: 'Paused', 1: 'Normal speed', 2: 'Fast', 4: 'Very fast' }[speed] || 'Speed set';
      this.ui.toast({ title: label, body: speed === 0 ? 'The block waits for you.' : 'Time is moving faster — residents keep their schedules.', kind: 'info', ttl: 2600 });
    } catch (e) {
      this.ui.toast({ title: 'Could not change speed', body: e.message, kind: 'danger' });
    }
  },

  wireKeys() {
    document.addEventListener('keydown', (e) => {
      if (e.target?.closest('input,textarea,select,[contenteditable="true"]')) return;
      const k = e.key.toLowerCase();
      if (e.key === 'Escape') {
        if (this.ui.currentModal) this.ui.closeModal();
        else if (document.querySelector('#phone-root:not(.hidden)')) this.ui.closePhone();
        return;
      }
      if (this.ui.currentModal || document.querySelector('#phone-root:not(.hidden)')) return;
      if (k === 'e') {
        const near = this.ui.nearestTalkable(this.state);
        if (near) this.ui.openTalk(near.id);
      }
      if (k === 'p' || k === 'm') this.ui.openPhone('messages');
      if (k === 'f') this.ui.openPhone('feed');
      if (k === 'j') this.ui.openJournal();
      if (k === 'h' || e.key === '?') this.ui.openHelp();
      if (k === 'g') this.ui.openStats();
      if (e.key === ' ') { e.preventDefault(); const s = this.state?.clock?.speed; this.setSpeed(s === 0 ? 1 : 0); }
      if (k === '+' || k === '=') this.view.setZoom(0.12);
      if (k === '-' || k === '_') this.view.setZoom(-0.12);
      // Tab remains native focus navigation; menu has a visible button.
    });
  },

  openActionWheel() {
    const st = this.state;
    if (!st?.player) return;
    const near = this.ui.nearestTalkable(st);
    const home = this.world?.homes?.[st.player.home_id ?? 17];
    const actions = [
      ['🚶', 'Walk home', () => { if (home) this.walkTo(home.x + 46, home.y + 100); }],
      ['😴', 'Sleep', () => this.doSleep()],
      ['🛍️', 'Shop', () => this.ui.openShop()],
      ['🎁', 'Gifts', () => this.ui.openPhone('wallet')],
      ['📱', 'Phone', () => this.ui.openPhone('messages')],
      ['🌐', 'Feed', () => this.ui.openPhone('feed')],
      ['🗂️', 'Cases', () => this.ui.openPhone('cases')],
      ['📖', 'Journal', () => this.ui.openJournal()],
      ['📅', 'Calendar', () => this.ui.openPhone('calendar')],
      ['⚔️', 'Rivalries', () => this.ui.openRivals()],
      ['🕺', 'Stir the pot', () => this.doStir()],
      ['📊', 'Dashboard', () => this.ui.openStats()],
      ['❓', 'Help', () => this.ui.openHelp()],
      ['⚙️', 'Settings', () => this.ui.openSettings()],
    ];
    const body = `<div class="wheel-grid">${actions.map(([ico, label, fn], i) => `<button class="wheel-item" data-w="${i}"><span>${ico}</span><b>${label}</b></button>`).join('')}</div>
      <div class="menu-speed-controls" role="group" aria-label="World pace"><b>World pace</b>${[[0,'Pause'],[1,'1×'],[2,'2×'],[4,'4×']].map(([speed,label])=>`<button class="speed ${st.clock.speed===speed?'active':''}" data-speed="${speed}" data-menu-speed="${speed}">${label}</button>`).join('')}</div>
      <div class="hint-note" style="margin-top:10px">${near ? `${near.first} is close enough to talk — press <kbd>E</kbd> or click them.` : 'Click a building to see its activities, or type <kbd>H</kbd> for the full guide.'}</div>`;
    const m = this.ui.modal({ title: 'What now?', subtitle: 'Quick actions for the block', icon: '✦', body, wide: true });
    m.querySelectorAll('[data-menu-speed]').forEach(b => b.onclick = () => this.setSpeed(Number(b.dataset.menuSpeed)));
    m.querySelectorAll('[data-w]').forEach(b => b.onclick = () => {
      const fn = actions[Number(b.dataset.w)][2];
      this.ui.closeModal();
      fn();
    });
  },

  async doSleep() {
    try {
      const res = await this.doAction('sleep', {});
      this.ui.toast({ title: res.title || 'Slept', body: res.text, kind: 'good', ttl: 7000 });
      if (res.notices?.length) this.ui.showWhileAway(res.notices);
    } catch (e) {
      this.ui.toast({ title: 'Can\'t sleep now', body: e.message, kind: 'danger' });
    }
  },

  async doStir() {
    const near = this.state?.npcs?.filter(n => !n.indoors && Math.hypot(n.x - this.state.player.x, n.y - this.state.player.y) < 200);
    if (!near?.length) { this.ui.toast({ title: 'Nobody nearby', body: 'You need someone close enough to stir up trouble with.', kind: 'info' }); return; }
    const target = near[0];
    const yes = await this.ui.confirm({
      title: 'Stir the pot?',
      body: `Whisper something into ${target.first}'s ear about someone else. It will raise tension and your reputation will take a small hit if it comes back to you.`,
      confirmLabel: 'Do it', danger: true,
    });
    if (!yes) return;
    try {
      const res = await this.doAction('stir', { npc_id: target.id });
      this.ui.toast({ title: 'Seeds planted', body: res.text, kind: 'story', ttl: 7000 });
    } catch (e) { this.ui.toast({ title: 'Not now', body: e.message, kind: 'danger' }); }
  },
};

function onClick(sel, fn) {
  const el = document.querySelector(sel);
  if (el) el.addEventListener('click', fn);
}

window.addEventListener('DOMContentLoaded', () => { App.init().catch(err => { console.error(err); }); });
window.__BLX__ = App;
