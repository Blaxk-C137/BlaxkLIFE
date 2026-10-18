/* =========================================================================
   BLXVERSE UI
   Everything is rendered into a small number of roots and wired with
   delegated events. Panels share the same visual grammar.
   ========================================================================= */
import { avatarUrl, drawAvatar, LOOK_OPTIONS } from './art.js';

const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
const WEATHER_ICONS = {
  'clear skies': '☀️', 'light clouds': '⛅', 'warm breeze': '🌤️',
  'drizzle': '🌦️', 'golden haze': '🌅', 'cool evening': '🌙',
};
const MOOD_ICONS = {
  buzzing: '🤩', cheerful: '😄', excited: '😃', steady: '🙂',
  low: '😔', stressed: '😣', irritated: '😤',
};
const ARCH_ICONS = {
  spark: '✨', storm: '🌩️', zen: '🍃', gear: '🔧', flame: '🔥',
  sprite: '🎨', tank: '💪', trickster: '😈',
};
const STATUS_LABEL = {
  sleeping: 'asleep', walking: 'on the move', at: 'around', working: 'working', busy: 'busy',
};

export function fmtNum(n) { return Number(n ?? 0).toLocaleString('en-US'); }
export function fmtClock(minute) {
  const m = Math.floor(minute % 1440);
  const d = Math.floor(minute / 1440);
  const h = Math.floor(m / 60);
  const mm = m % 60;
  return `${WEEKDAYS[d % 7]} ${String(h).padStart(2, '0')}:${String(mm).padStart(2, '0')}`;
}
function fmtAgo(minute, nowMinute, dayNumber) {
  const diff = Math.max(0, nowMinute - minute);
  if (diff < 1) return 'just now';
  if (diff < 60) return `${Math.round(diff)} min ago`;
  const dayDiff = Math.floor((nowMinute - minute) / 1440);
  if (dayDiff >= 1) return `${dayDiff}d ago`;
  return `${Math.round(diff / 60)}h ago`;
}
function relTone(v) {
  return v >= 0 ? '' : 'neg';
}

export class UI {
  constructor(app) {
    this.app = app;
    this.sideTab = 'people';
    this.currentModal = null;
    this.modalStack = [];
    this.voiceCtx = null;
    this.voiceStatus = '';
    this.phoneTab = 'messages';
    this.phoneThread = null;
    this.callSession = null;
    this.ringTimer = null;
    this.lastSetupPreview = null;
    this.settings = this.loadSettings();
    this.phoneDrafts = new Map();
    this.seenOverlays = new Set();
    this.phoneRefreshBusy = false;
    const fitViewport = () => {
      const v = window.visualViewport;
      document.documentElement.style.setProperty('--app-height', `${v?.height || window.innerHeight}px`);
      document.documentElement.style.setProperty('--viewport-top', `${v?.offsetTop || 0}px`);
    };
    window.visualViewport?.addEventListener('resize', fitViewport);
    window.visualViewport?.addEventListener('scroll', fitViewport);
    window.addEventListener('resize', fitViewport);
    fitViewport();
    $('#btn-civic')?.addEventListener('click',()=>this.openCivicOverview());
    window.addEventListener('pagehide',()=>{if(this.talkLease)navigator.sendBeacon('/api/action',new Blob([JSON.stringify({type:'talk_end',...this.talkLease})],{type:'application/json'}))});
    document.addEventListener('keydown',e=>{if(this.app.inputLocked){e.preventDefault();e.stopImmediatePropagation()}},true);
  }

  loadSettings() {
    try {
      const raw = JSON.parse(localStorage.getItem('blx.settings') || '{}');
      return {
        sound: raw.sound !== false,
        speakReplies: raw.speakReplies === true,
        ttsRate: typeof raw.ttsRate === 'number' ? raw.ttsRate : 1,
        voiceURI: raw.voiceURI || '',
        autoListen: raw.autoListen !== false,
      };
    } catch {
      return { sound: true, speakReplies: false, ttsRate: 1, voiceURI: '', autoListen: true };
    }
  }

  saveSettings(patch) {
    this.settings = { ...this.settings, ...patch };
    localStorage.setItem('blx.settings', JSON.stringify(this.settings));
    const v = this.app.voice;
    if (v) {
      v.soundEnabled = this.settings.sound;
      v.rate = this.settings.ttsRate;
      v.voiceOverride = this.pickVoiceByURI(this.settings.voiceURI);
    }
  }

  pickVoiceByURI(uri) {
    if (!uri || !window.speechSynthesis) return null;
    return (window.speechSynthesis.getVoices() || []).find(v => v.voiceURI === uri) || null;
  }

  /* =====================================================================
     SETUP
     ===================================================================== */
  initSetup(world, opts = {}) {
    this.setupLook = {
      skin: LOOK_OPTIONS.skin[3], hair: LOOK_OPTIONS.hair[1], hairStyle: 'short',
      outfit: LOOK_OPTIONS.outfit[3], accent: '#f2c14e', accessory: 'none', height: 1,
    };
    this.setupGender = 'female';
    this.setupWorld = world;

    const skinWrap = $('#skin-swatches');
    const hairWrap = $('#hair-swatches');
    const outfitWrap = $('#outfit-swatches');
    if (skinWrap && !skinWrap.dataset.ready) {
      skinWrap.innerHTML = LOOK_OPTIONS.skin.map(c => `<button class="swatch" data-skin="${c}" style="background:${c}" aria-label="Skin tone"></button>`).join('');
      hairWrap.innerHTML = LOOK_OPTIONS.hair.map(c => `<button class="swatch" data-hair="${c}" style="background:${c}" aria-label="Hair color"></button>`).join('');
      outfitWrap.innerHTML = LOOK_OPTIONS.outfit.map(c => `<button class="swatch" data-outfit="${c}" style="background:${c}" aria-label="Outfit color"></button>`).join('');
      $('#hair-style').innerHTML = LOOK_OPTIONS.hairStyle.map(s => `<option value="${s}">${s}</option>`).join('');
      $('#accessory').innerHTML = LOOK_OPTIONS.accessory.map(a => `<option value="${a}">${a === 'none' ? 'None' : a}</option>`).join('');
      skinWrap.dataset.ready = '1';
      this.wireSetup();
    }
    this.syncSetupControls();
    this.renderSetupPreview();
    $('#setup').classList.remove('hidden');
    $('#game').classList.add('hidden');
    const cont = $('#btn-continue');
    if (opts.existingName) {
      cont.classList.remove('hidden');
      $('#continue-name').textContent = opts.existingName;
    } else {
      cont.classList.add('hidden');
    }
    if (opts.overwrite) {
      $('#creator-error').textContent = 'Starting a new world will replace the current one on this device.';
    }
  }

  wireSetup() {
    const self = this;
    $('#skin-swatches').addEventListener('click', e => {
      const b = e.target.closest('[data-skin]'); if (!b) return;
      self.setupLook.skin = b.dataset.skin; self.renderSetupPreview(); self.syncSetupControls();
    });
    $('#hair-swatches').addEventListener('click', e => {
      const b = e.target.closest('[data-hair]'); if (!b) return;
      self.setupLook.hair = b.dataset.hair; self.renderSetupPreview(); self.syncSetupControls();
    });
    $('#outfit-swatches').addEventListener('click', e => {
      const b = e.target.closest('[data-outfit]'); if (!b) return;
      self.setupLook.outfit = b.dataset.outfit; self.renderSetupPreview(); self.syncSetupControls();
    });
    $('#hair-style').addEventListener('change', e => { self.setupLook.hairStyle = e.target.value; self.renderSetupPreview(); });
    $('#accessory').addEventListener('change', e => { self.setupLook.accessory = e.target.value; self.renderSetupPreview(); });
    $('#gender-select').addEventListener('click', e => {
      const b = e.target.closest('.seg'); if (!b) return;
      self.setupGender = b.dataset.value;
      $$('.seg', $('#gender-select')).forEach(s => {
        const on = s === b;
        s.classList.toggle('active', on);
        s.setAttribute('aria-checked', on ? 'true' : 'false');
      });
    });
    $('#input-age').addEventListener('input', e => { $('#age-value').textContent = e.target.value; });
    $('#input-name').addEventListener('input', e => {
      $('#preview-name-tag').textContent = e.target.value.trim() || 'New resident';
    });
    $('#btn-create').addEventListener('click', () => self.submitSetup(false));
    $('#btn-continue').addEventListener('click', () => self.app.continueWorld());
    $('#btn-about').addEventListener('click', () => self.openAbout());
  }

  syncSetupControls() {
    const active = (sel, key, val) => $$(sel).forEach(el => el.classList.toggle('active', el.dataset[key] === val));
    active('[data-skin]', 'skin', this.setupLook.skin);
    active('[data-hair]', 'hair', this.setupLook.hair);
    active('[data-outfit]', 'outfit', this.setupLook.outfit);
    $('#hair-style').value = this.setupLook.hairStyle;
    $('#accessory').value = this.setupLook.accessory;
  }

  renderSetupPreview() {
    const canvas = $('#avatar-preview');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const W = canvas.width, H = canvas.height;
    drawAvatar(ctx, this.setupLook, W, H, { mood: 'cheerful', mode: 'bust' });
  }

  async submitSetup(overwrite) {
    const err = $('#creator-error');
    err.textContent = '';
    const name = $('#input-name').value.trim();
    const age = parseInt($('#input-age').value, 10);
    if (name.length < 2) { err.textContent = 'Give your resident a name (2+ characters).'; return; }
    const btn = $('#btn-create');
    btn.disabled = true;
    try {
      await this.app.createWorld({
        name, gender: this.setupGender, age, look: this.setupLook,
        overwrite: true,
      });
    } catch (e) {
      err.textContent = e.message || 'Could not create the world.';
    } finally {
      btn.disabled = false;
    }
  }

  /* =====================================================================
     HUD
     ===================================================================== */
  renderHUD(state) {
    if (!state || state.setup) return;
    const busy=state.civic?.busy;
    this.showBusy(busy,this.workPending&&!busy);
    const safety=$('#btn-civic');
    if(safety){safety.title=`Neighbourhood · health ${state.civic?.player_health??100} · heat ${state.civic?.heat??0}`}
    const c = state.clock;
    $('#clock-day').textContent = `Day ${c.day} · ${c.weekday}`;
    $('#clock-time').textContent = c.time;
    $('#weather').textContent = WEATHER_ICONS[c.weather] || '☀️';
    $('#weather').title = c.weather;
    $('#stat-wallet b').textContent = fmtNum(state.player.wallet);
    $('#stat-energy b').textContent = Math.round(state.player.energy);
    $('#stat-rep b').textContent = Math.round(state.player.reputation);
    const energyBar = $('#stat-energy .meter i');
    if (energyBar) energyBar.style.width = `${Math.max(0, Math.min(100, state.player.energy))}%`;
    $$('.speed').forEach(b => b.classList.toggle('active', Number(b.dataset.speed) === state.clock.speed));
    const badge = $('#phone-badge');
    const unread = (state.unread?.messages || 0) + (state.unread?.notifications || 0);
    badge.textContent = unread > 99 ? '99+' : String(unread);
    badge.classList.toggle('hidden', unread === 0);
    const alertBadge = $('#alert-badge');
    const alertCount = (state.notifications || []).length + (state.cases || []).length;
    alertBadge.textContent = String(alertCount);
    alertBadge.classList.toggle('hidden', alertCount === 0);
    $('#live-note').textContent = `● ${state.npcs.filter(n => !n.indoors && Math.hypot(n.x-state.player.x,n.y-state.player.y)<260).length} nearby · ${state.npcs.length} residents live`;

    this.renderSidebar(state);
    this.renderNearby(state);
    this.renderQuests(state);
    this.renderTicker(state);
    this.renderLocation(state);

  }

  nearestTalkable(state) {
    if (!state?.player) return null;
    let best = null, bestD = 9999;
    for (const n of state.npcs) {
      if (n.indoors || n.status === 'sleeping') continue;
      const d = Math.hypot(n.x - state.player.x, n.y - state.player.y);
      if (d < 150 && d < bestD) { best = n; bestD = d; }
    }
    return best;
  }

  renderLocation(state) {
    if (!state?.player || !this.app.world) return;
    $('#live-event')?.classList.add('hidden');
    for (const ev of state.live_events || []) this.announceOnce(`fixture:${ev.id}:${ev.due}`, {
      title: `${ev.icon} ${ev.title}`, body: `${ev.where} · on now. Find it in Calendar.`, kind: 'info',
    });
    const locs = this.app.world.locations || [];
    let best = null, bestD = 1e9;
    for (const l of locs) {
      const cx = l.x + l.w / 2, cy = l.y + l.h / 2;
      const d = Math.hypot(cx - state.player.x, cy - state.player.y);
      if (d < bestD) { best = l; bestD = d; }
    }
    const nameEl = $('#location-name');
    const subEl = $('#location-sub');
    if (best && bestD < 340) {
      nameEl.textContent = best.name;
      subEl.textContent = `${best.icon} ${best.desc.split('.')[0].slice(0, 52)}…`;
    } else {
      nameEl.textContent = 'BlaxkVille';
      subEl.textContent = `${state.clock.weather} · ${state.clock.is_weekend ? 'weekend' : 'weekday'}`;
    }
    const key = best && bestD < 340 ? best.id : 'city';
    const chip = $('#location-chip');
    if (key !== this.locationKey) {
      this.locationKey = key;
      clearTimeout(this.locationTimer);
      chip.classList.remove('hidden');
      this.locationTimer = setTimeout(() => chip.classList.add('hidden'), 5000);
    }
    $('#dismiss-location').onclick = e => {
      e.stopPropagation();
      clearTimeout(this.locationTimer);
      chip.classList.add('hidden');
    };
  }

  renderNearby(state) {
    const rail = $('#nearby-rail');
    if (!rail || !state?.player) return;
    const near = state.npcs
      .map(n => ({ ...n, d: Math.hypot(n.x - state.player.x, n.y - state.player.y) }))
      .filter(n => !n.indoors && n.status !== 'sleeping' && n.d < 520)
      .sort((a, b) => a.d - b.d)
      .slice(0, 8);
    rail.innerHTML = near.map(n => `
      <button class="nearby-person" data-npc="${n.id}" title="Talk to ${esc(n.first)}">
        <img src="${avatarUrl(n.look, 56, 'head', n.mood)}" alt="" />
        <span class="np-copy"><b>${esc(n.first)}</b><span>${esc(n.rel?.label || '')}</span></span>
      </button>`).join('');
    $$('.nearby-person', rail).forEach(el => el.onclick = () => this.openProfile(el.dataset.npc));
  }

  announceOnce(key, notification) {
    if (this.seenOverlays.has(key)) return;
    this.seenOverlays.add(key);
    // Bounded lifetime cache; ids/stages, not every game-clock update.
    if (this.seenOverlays.size > 500) this.seenOverlays.delete(this.seenOverlays.values().next().value);
    this.toast(notification);
  }

  renderQuests(state) {
    $('#quest-stack')?.replaceChildren();
    for (const arc of (state.arcs || []).filter(a => a.status === 'active')) {
      this.announceOnce(`story:${arc.id}:${arc.stage_title || arc.stage}`, {
        title: arc.stage_title || arc.title, body: arc.summary || 'Open Journal for the story so far.', kind: 'story',
      });
    }
    for (const c of state.cases || []) this.announceOnce(`case:${c.id}:${c.evidence?.length}`, {
      title: c.title, body: `${c.evidence?.length || 0} clues found. Details stay in Journal → Cases.`, kind: 'story',
    });
    for (const d of state.date_offers || []) this.announceOnce(`date:${d.id}`, {
      title: 'Date planned', body: `${this.npc(d.npc_id)?.first || 'Someone'} · ${this.locationName(d.venue)} · ${fmtClock(d.due)}`, kind: 'good',
    });
  }

  renderTicker(state) {
    $('#world-ticker')?.replaceChildren();
    for (const n of (state.notices || []).slice(-2)) this.announceOnce(`notice:${n.id}`, {
      title: n.title, body: n.body || '', kind: n.kind === 'alert' ? 'danger' : 'info',
    });
  }

  renderSidebar(state) {
    const body = $('#side-body');
    if (!body || !state?.player) return;
    $$('.side-tab').forEach(t => t.classList.toggle('active', t.dataset.tab === this.sideTab));
    if (this.sideTab === 'people') {
      const near = state.npcs
        .map(n => ({ ...n, d: Math.hypot(n.x - state.player.x, n.y - state.player.y) }))
        .sort((a, b) => a.d - b.d)
        .slice(0, 12);
      body.innerHTML = `
        <div class="side-section-title">Nearest residents</div>
        ${near.map(n => `
          <button class="person-row" data-npc="${n.id}">
            <span class="person-avatar"><img src="${avatarUrl(n.look, 76, 'head', n.mood)}" alt="" style="width:100%;height:100%;object-fit:cover" /></span>
            <span class="person-main"><b>${esc(n.first)} ${esc(n.last)}</b><span>${ARCH_ICONS[n.archetype] || ''} ${esc(n.vibe?.label || n.occupation)} · ${esc(n.indoors ? 'indoors at home' : STATUS_LABEL[n.status] || n.status)}</span></span>
            <span class="person-rel">${esc(n.rel?.label || '')}<small>${Math.round(n.d)}px</small></span>
          </button>`).join('')}
        <div class="empty-note">Click a resident to see their profile, memories and beliefs — or walk closer and press <kbd>E</kbd> to talk.</div>`;
      $$('.person-row', body).forEach(el => el.onclick = () => this.openProfile(el.dataset.npc));
    } else if (this.sideTab === 'story') {
      const arcs = (state.arcs || []).filter(a => a.status === 'active');
      const cases = state.cases || [];
      const dates = state.date_offers || [];
      const rows = [];
      for (const a of arcs) {
        rows.push(`<div class="story-card">
          <div class="sc-kicker">${a.kind === 'chain' ? 'Main storyline' : a.kind}</div>
          <h4>${esc(a.title)}</h4><p>${esc(a.summary)}</p>
          <div class="sc-actors">${(a.actors || []).map(id => `<span class="actor-chip">${esc(this.npc(id)?.first || '?')}</span>`).join('')}
          <span class="actor-chip">stage ${a.stage + 1}</span></div></div>`);
      }
      for (const c of cases) {
        rows.push(`<div class="story-card case">
          <div class="sc-kicker">Case file</div><h4>${esc(c.title)}</h4>
          <p>${esc(c.description)}</p>
          <div class="sc-actors"><span class="actor-chip">accused: ${esc(this.npc(c.accused)?.first || '?')}</span>
          <span class="actor-chip">${c.evidence?.length || 0} clues</span></div>
          <button class="btn tiny ghost" style="margin-top:8px" data-case="${esc(c.id)}">Open case →</button></div>`);
      }
      for (const d of dates) {
        rows.push(`<div class="story-card">
          <div class="sc-kicker">On your calendar</div><h4>Date with ${esc(this.npc(d.npc_id)?.first || 'someone')}</h4>
          <p>${esc(this.locationName(d.venue))} · ${esc(this.fmtClockShort(d.due))}. Don't be late.</p>
          <button class="btn tiny ghost" style="margin-top:8px" data-date="${esc(d.id)}">Details →</button></div>`);
      }
      body.innerHTML = rows.join('') || `<div class="empty-note">The block is quiet on the story front. Give it a few hours — someone is always planning something.</div>`;
      $$('[data-case]', body).forEach(b => b.onclick = () => this.openCaseFile(b.dataset.case));
      $$('[data-date]', body).forEach(b => b.onclick = () => this.openDateOffer(b.dataset.date));
    } else {
      const notices = (state.notices || []).slice(-10).reverse();
      const notifs = (state.notifications || []).slice().reverse();
      const noticesHtml = notices.map(n => `
        <div class="alert-row">
          <span class="alert-ico">${n.kind === 'alert' ? '🚨' : n.kind === 'news' ? '📰' : n.kind === 'event' ? '🎪' : '📌'}</span>
          <div class="alert-copy"><b>${esc(n.title)}</b><span>${esc(n.body)}</span><small>${esc(fmtClock(n.minute))}</small></div>
        </div>`).join('') || '<div class="empty-note">No notices yet.</div>';
      const notifsHtml = notifs.slice(0, 8).map(n => `
        <div class="alert-row">
          <span class="alert-ico">${n.kind === 'message' ? '💬' : n.kind === 'call' ? '📞' : n.kind === 'story' ? '📖' : '🔔'}</span>
          <div class="alert-copy"><b>${esc(n.title)}</b><span>${esc(n.body)}</span><small>${esc(fmtClock(n.minute))}</small></div>
        </div>`).join('');
      body.innerHTML = `<div class="side-section-title">Town alerts</div>${noticesHtml}
        <div class="side-section-title" style="margin-top:14px">For you</div>${notifsHtml || '<div class="empty-note">Nothing new for you.</div>'}`;
    }
  }

  switchSideTab(tab) {
    this.sideTab = tab;
    this.renderSidebar(this.app.state);
  }

  /* =====================================================================
     Generic modal plumbing
     ===================================================================== */
  modal({ title, subtitle = '', icon = '✦', body = '', foot = '', wide = false, tall = false, onMount = null, className = '' }) {
    this.closeModal();
    const root = $('#overlay-root');
    root.innerHTML = `
      <div class="scrim" data-close="1"></div>
      <div class="modal-wrap">
        <div class="modal ${wide ? 'wide' : ''} ${tall ? 'tall' : ''} ${className}" role="dialog" aria-modal="true" aria-label="${esc(title)}">
          <div class="modal-head">
            <div class="mh-icon">${icon}</div>
            <div><h3>${esc(title)}</h3>${subtitle ? `<p>${esc(subtitle)}</p>` : ''}</div>
            <button class="modal-close" data-close="1" aria-label="Close">✕</button>
          </div>
          <div class="modal-body">${body}</div>
          ${foot ? `<div class="modal-foot">${foot}</div>` : ''}
        </div>
      </div>`;
    $$('[data-close]', root).forEach(el => el.addEventListener('click', () => this.closeModal()));
    const onKey = (e) => { if (e.key === 'Escape') this.closeModal(); };
    this._escHandler && document.removeEventListener('keydown', this._escHandler);
    this._escHandler = onKey;
    document.addEventListener('keydown', onKey);
    this.currentModal = $('.modal', root);
    if (onMount) onMount(this.currentModal);
    return this.currentModal;
  }

  releaseTalk() {
    clearInterval(this.talkHeartbeat);
    const lease=this.talkLease;this.talkLease=null;
    if(lease)this.app.api('/api/action',{method:'POST',body:{type:'talk_end',...lease}}).catch(()=>{});
  }

  finishTalkUI(message) {
    this.releaseTalk();
    if(message&&$('#talk-scroll'))this.addTalkBubble('npc',message);
    $$('#talk-input,#talk-send,#talk-mic,#talk-chips button').forEach(el=>el.disabled=true);
    if(this.voiceCtx?.mode==='talk')this.voiceCtx=null;
  }

  closeModal() {
    this.releaseTalk();
    const root = $('#overlay-root');
    if (!root) return;
    root.innerHTML = '';
    this.currentModal = null;
    if (this._escHandler) { document.removeEventListener('keydown', this._escHandler); this._escHandler = null; }
  }

  confirm({ title, body, confirmLabel = 'Confirm', danger = false }) {
    return new Promise((resolve) => {
      this.modal({
        title, body: `<div style="font-size:13px;color:var(--ink-2);line-height:1.6">${body}</div>`, icon: danger ? '⚠️' : '✦',
        foot: `<button class="btn ghost" data-x="0">Cancel</button>
               <button class="btn ${danger ? 'danger' : 'primary'}" data-x="1">${esc(confirmLabel)}</button>`,
        onMount: (m) => {
          $$('[data-x]', m).forEach(b => b.addEventListener('click', () => {
            const val = b.dataset.x === '1';
            this.closeModal();
            resolve(val);
          }));
        },
      });
    });
  }

  confirmMic() {
    if (this.app.voice.micConsent) return Promise.resolve(true);
    return new Promise((resolve) => {
      this.modal({
        title: 'Turn on your microphone?',
        subtitle: 'Optional — typing works everywhere',
        icon: '🎙️',
        body: `<div style="font-size:13px;color:var(--ink-2);line-height:1.7">
          <p>Voice lets you speak to residents and interrupt them mid-sentence. Before you continue:</p>
          <ul style="margin:8px 0 8px 18px;color:var(--ink-3)">
            <li>Speech recognition runs <b>in your browser</b> (your browser vendor's on-device or cloud recognizer — we never receive audio).</li>
            <li>This game server only receives the text transcript of what you chose to say, like a typed message.</li>
            <li>You can revoke the microphone in your browser settings at any time.</li>
          </ul>
          <p>Nothing is recorded or stored by BLXVERSE.</p>
        </div>`,
        foot: `<button class="btn ghost" data-mic="0">Not now</button><button class="btn primary" data-mic="1">Allow microphone</button>`,
        onMount: (m) => {
          $$('[data-mic]', m).forEach(b => b.onclick = () => {
            const yes = b.dataset.mic === '1';
            this.closeModal();
            resolve(yes);
          });
        },
      });
    });
  }

  /* =====================================================================
     Toasts
     ===================================================================== */
  toast({ title, body = '', kind = 'info', ttl = 5000, icon = '' }) {
    const stack = $('#toast-stack');
    if (!stack) return;
    const icons = { good: '✅', story: '📖', danger: '⚠️', info: '🔔', message: '💬', call: '📞', money: '🪙' };
    const el = document.createElement('div');
    el.className = `toast ${kind}`;
    el.innerHTML = `<span class="t-ico">${icon || icons[kind] || '✦'}</span>
      <span class="t-body"><b>${esc(title)}</b><span>${esc(body)}</span></span>
      <button class="t-close" aria-label="Dismiss">✕</button>`;
    el.querySelector('.t-close').onclick = () => this.removeToast(el);
    stack.appendChild(el);
    while (stack.children.length > 3) stack.removeChild(stack.firstChild);
    // Every transient notice gets the same five-second lifetime.
    el._dismissTimer = setTimeout(() => this.removeToast(el), 5000);
  }

  removeToast(el) {
    if (!el || !el.parentNode) return;
    clearTimeout(el._dismissTimer);
    el.remove();
  }

  /* =====================================================================
     Helpers
     ===================================================================== */
  npc(id) {
    if (!id) return null;
    const state = this.app.state;
    const base=(this.app.world?.npcs || []).find(n=>n.id===id), live=state?.npcs?.find(n=>n.id===id);
    if(state?.npcs&&!live)return null;
    return base||live?{...base,...live}:null;
  }
  loc(id) { return (this.app.world?.locations || []).find(l => l.id === id) || null; }
  locationName(id) { return this.loc(id)?.name || (id === 'home' ? 'home' : 'the block'); }
  fmtClockShort(minute) { return fmtClock(minute); }

  /** "in 2h 10m" / "today 19:30" / "Thu 19:30" — for calendar rows. */
  fmtWhen(due) {
    const now = this.app.state?.clock?.minute ?? 0;
    const delta = due - now;
    if (delta <= 1) return 'now';
    if (delta < 90) return `in ${Math.round(delta)} min`;
    if (delta < 60 * 12) return `in ${Math.floor(delta / 60)}h ${Math.round(delta % 60)}m`;
    const dayOffset = Math.floor(due / 1440) - Math.floor(now / 1440);
    if (dayOffset <= 0) return `later today (${fmtClock(due)})`;
    if (dayOffset === 1) return `tomorrow (${fmtClock(due)})`;
    return fmtClock(due);  // fmtClock already prefixes the weekday
  }

  playerNearNpc(npc, pad = 150) {
    const st = this.app.state;
    if (!st?.player || !npc) return false;
    const dx = (st.player.x ?? 0) - (npc.x ?? 0);
    const dy = (st.player.y ?? 0) - (npc.y ?? 0);
    return Math.hypot(dx, dy) <= pad;
  }

  playerNearLoc(locId, pad = 130) {
    const st = this.app.state;
    const l = this.loc(locId);
    if (!st?.player || !l) return false;
    const cx = Math.min(Math.max(st.player.x, l.x), l.x + l.w);
    const cy = Math.min(Math.max(st.player.y, l.y), l.y + l.h);
    return Math.hypot(st.player.x - cx, st.player.y - cy) <= pad;
  }

  distToLoc(locId) {
    const st = this.app.state;
    const l = this.loc(locId);
    if (!st?.player || !l) return 1e9;
    const cx = Math.min(Math.max(st.player.x, l.x), l.x + l.w);
    const cy = Math.min(Math.max(st.player.y, l.y), l.y + l.h);
    return Math.hypot(st.player.x - cx, st.player.y - cy);
  }

  distToNpc(npc) {
    const st = this.app.state;
    if (!st?.player || !npc) return 1e9;
    return Math.hypot(npc.x - st.player.x, npc.y - st.player.y);
  }

  walkToLocation(locId, onArrive) {
    const l = this.loc(locId);
    if (!l) return;
    const x = l.x + l.w / 2;
    const y = l.y + l.h + 34;
    this.app.walkTo(x, y, onArrive);
    this.toast({ title: `Walking to ${l.name}`, body: 'Click the building when you arrive to go inside.', kind: 'info', ttl: 4200 });
  }

  /* =====================================================================
     PROFILE
     ===================================================================== */
  async openProfile(npcId) {
    if (npcId === 'player') { this.openPlayerProfile(); return; }
    const base = this.npc(npcId);
    if (!base) return;
    let p = null;
    try { p = await this.app.apiGet(`/api/npc/${npcId}`); } catch { p = base; }
    const rel = p.relationship || {};
    const mood = p.mood?.label || base.mood || 'steady';
    const near = this.distToNpc(base) < 150;
    const traits = (p.traits || []).map(t => `<span class="chip">${esc(t)}</span>`).join('');
    const beliefs = (p.beliefs || []).map(b => `
      <div class="belief-card">
        <div class="bc-main"><b>“${esc(b.claim)}”</b>
          <span>${b.truth === 'false' ? 'proven false' : 'unverified'} · confidence ${(b.confidence * 100).toFixed(0)}% · source: ${esc(this.npc(b.source_id)?.first || 'their own eyes')}</span>
          <div class="confidence-bar"><i style="width:${Math.round(b.confidence * 100)}%"></i></div>
        </div>
        <button class="btn tiny ghost" data-belief="${esc(b.id)}">Challenge</button>
      </div>`).join('') || '<div class="empty-note">No active beliefs about anyone. Refreshingly clean.</div>';
    const memories = (p.memory_of_you || []).map(m => `
      <div class="memory-item"><span class="mi-day">D${m.day}</span><span>${esc(m.summary)}</span></div>`).join('')
      || '<div class="empty-note">They don\'t have any strong memories of you yet. Give it time.</div>';
    const connections = (p.connections || []).map(c => `<span class="connection"><b>${esc(c.name.split(' ')[0])}</b> · ${esc(c.label)}</span>`).join('') || '<span class="connection">still building their circle</span>';
    const body = `
      <div class="profile-hero">
        <div class="profile-portrait">
          <img src="${avatarUrl(p.look || base.look, 420, 'bust', mood)}" alt="" style="width:100%;height:100%;object-fit:cover" />
          <span class="profile-mood">${MOOD_ICONS[mood] || '🙂'} ${esc(mood)}</span>
        </div>
        <div>
          <div class="profile-name">${esc(p.name || base.name)}</div>
          <div class="profile-sub">${esc(p.pronouns || '')} · ${p.age} · ${esc(p.occupation || '')} · ${esc(p.household_role || '')}</div>
          <div class="chip-row">
            <span class="chip amber">${ARCH_ICONS[p.archetype] || '✨'} ${esc(p.vibe?.label || p.archetype_label || p.archetype)}</span>
            <span class="chip mint">${esc(rel.label || 'acquaintance')}</span>
            <span class="chip">${esc(p.age_bracket || '')}</span>
            ${p.group_hint ? `<span class="chip violet">crew: ${esc(p.group_hint)}</span>` : ''}
            ${p.spotlight ? '<span class="chip mint">neighborhood regular</span>' : ''}
          </div>
          <p class="profile-bio">${esc(p.vibe?.description || p.archetype_blurb || '')}. Currently: ${esc(p.activity || 'out and about')}. ${esc(p.quirk ? `Fun fact: ${p.quirk}.` : '')}</p>
          <div class="rel-grid">
            ${meter('Familiarity', rel.familiarity || 0, 100, 'rm-fam')}
            ${meter('Trust', rel.trust || 0, 100, 'rm-trust')}
            ${meter('Affinity', (rel.affinity || 0) + 100, 200, 'rm-aff', `${Math.round(rel.affinity || 0)}`)}
            ${meter('Romance', rel.romance || 0, 100, 'rm-rom')}
            ${meter('Tension', rel.tension || 0, 100, 'rm-tension tension', `${Math.round(rel.tension || 0)}`, true)}
          </div>
        </div>
      </div>

      <div class="profile-section">
        <h4>Actions</h4>
        <div class="action-grid">
          <button class="action-tile" data-act="talk"><span class="at-ico">💬</span><b>Talk</b><span>${p.indoors ? 'indoors · text instead' : near ? 'right here' : 'walk closer first'}</span></button>
          <button class="action-tile" data-act="message"><span class="at-ico">✉️</span><b>Message</b><span>through the phone</span></button>
          <button class="action-tile" data-act="call"><span class="at-ico">📞</span><b>Call</b><span>${(rel.familiarity || 0) >= 8 ? 'voice + avatar' : 'know them better first'}</span></button>
          <button class="action-tile" data-act="gift"><span class="at-ico">🎁</span><b>Give a gift</b><span>from your bag</span></button>
          <button class="action-tile" data-act="flirt"><span class="at-ico">💛</span><b>Flirt</b><span>charming, maybe</span></button>
          <button class="action-tile" data-act="date"><span class="at-ico">🌙</span><b>Ask out</b><span>on a date</span></button>
          <button class="action-tile" data-act="apologize"><span class="at-ico">🕊️</span><b>Apologize</b><span>clear the air</span></button>
          <button class="action-tile" data-act="joke"><span class="at-ico">😄</span><b>Joke</b><span>risky, but fun</span></button>
        </div>
      </div>

      <div class="profile-section">
        <h4>Identity & quirks</h4>
        <div class="trait-list">${traits}</div>
        <div class="chip-row" style="margin-top:8px">
          <span class="chip">🎵 ${esc(p.music || '')}</span>
          <span class="chip">🍲 ${esc(p.food || '')}</span>
          <span class="chip">🎯 ${esc(p.goal_short || '')}</span>
          <span class="chip">🌟 ${esc(p.goal_long || '')}</span>
        </div>
        <div class="quote">Something they care about: ${esc((p.values || []).join(', ') || 'keeping the week moving')}. A line they don't like crossed: ${esc((p.boundaries || [])[0] || 'being talked over')}.</div>
      </div>

      <div class="profile-section">
        <h4>Inside their head · memories about you</h4>
        <div class="memory-list">${memories}</div>
      </div>

      <div class="profile-section">
        <h4>Beliefs (not facts)</h4>
        ${beliefs}
      </div>

      <div class="profile-section">
        <h4>Who they know</h4>
        <div class="connection-list">${connections}</div>
      </div>

      <div class="profile-section">
        <h4>Where they'll be today</h4>
        <div class="chip-row">${(p.schedule?.weekday || []).slice(0, 6).map(b => `<span class="chip">${String(Math.floor(b.start)).padStart(2, '0')}:00 ${esc(b.activity)}</span>`).join('') || '<span class="chip">wandering</span>'}</div>
      </div>
    `;
    const foot = `<span class="pill ghost left">${esc(p.spotlight ? 'Local regular' : 'Resident')} · ${esc(p.location || 'around')}</span>
      <button class="btn ghost" data-close="1">Close</button>
      <button class="btn danger" data-act="confront">Confront</button><button class="btn primary" data-act="talk">Talk to ${esc((p.first || 'them'))}</button>`;
    const modal = this.modal({ title: `${p.first}'s profile`, subtitle: `${p.occupation} · ${p.age} · ${MOOD_ICONS[mood] || ''} ${mood}`, icon: '👤', body, foot, wide: true, tall: true });
    $$('[data-close]', modal).forEach(el => el.addEventListener('click', () => this.closeModal()));
    $$('[data-act]', modal).forEach(el => el.addEventListener('click', () => this.runProfileAction(el.dataset.act, p, base)));
    $$('[data-belief]', modal).forEach(el => el.addEventListener('click', async () => {
      try {
        const belief = (p.beliefs || []).find(b => b.id === el.dataset.belief);
        const res = await this.app.doAction('challenge_rumor', { npc_id: p.id, claim: belief?.claim || '' });
        this.toast({ title: 'Claim challenged', body: res.text, kind: 'story' });
        this.openProfile(p.id);
      } catch (e) { this.toast({ title: 'Not yet', body: e.message, kind: 'danger' }); }
    }));
  }

  async runProfileAction(act, p, base) {
    if(act==='confront'){
      if(!await this.confirm({title:'Escalate this dispute?',body:'A physical fight can wound or permanently end a resident’s life. You will lose reputation and attract police attention.',confirmLabel:'Confront',danger:true}))return;
      if(await this.doCivic('confront',{npc_id:p.id}))this.closeModal();return;
    }
    if (!['message', 'call'].includes(act) && (p.indoors || base.indoors)) {
      this.toast({ title: 'At home', body: `${p.first} is indoors. Try a text or a call instead.`, kind: 'info' });
      return;
    }
    if (act === 'talk') {
      if (this.distToNpc(base) > 150) { this.toast({ title: 'Too far away', body: `Walk closer to ${p.first} first.`, kind: 'info' }); return; }
      this.openTalk(p.id);
    } else if (act === 'message') {
      this.closeModal();
      this.openPhone('messages', { npcId: p.id });
    } else if (act === 'call') {
      this.startCall(p.id);
    } else if (act === 'gift') {
      this.openGiftPicker(p.id);
    } else if (act === 'flirt') {
      this.openTalk(p.id, { intent: 'flirt' });
    } else if (act === 'date') {
      this.openTalk(p.id, { intent: 'ask_date' });
    } else if (act === 'apologize') {
      this.openTalk(p.id, { intent: 'apologize' });
    } else if (act === 'joke') {
      this.openTalk(p.id, { intent: 'joke' });
    }
  }

  openPlayerProfile() {
    const st = this.app.state;
    const p = st.player;
    const inv = Object.entries(p.inventory || {});
    const items = this.app.world?.items || [];
    const invHtml = inv.length ? inv.map(([id, qty]) => {
      const item = items.find(i => i.id === id);
      return `<span class="chip mint">${item?.icon || '🎁'} ${esc(item?.name || id)} ×${qty}</span>`;
    }).join('') : '<span class="chip">nothing yet — visit a shop</span>';
    const body = `<div class="profile-hero">
      <div class="profile-portrait"><img src="${avatarUrl(p.look, 420, 'bust', p.mood)}" style="width:100%;height:100%;object-fit:cover" alt=""/>
      <span class="profile-mood">${MOOD_ICONS[p.mood] || '🙂'} ${esc(p.mood)}</span></div>
      <div>
        <div class="profile-name">${esc(p.name)}</div>
        <div class="profile-sub">${esc(p.gender)} · ${p.age || ''} · ${esc(p.occupation || 'newcomer')} · Juniper Row</div>
        <div class="chip-row"><span class="chip amber">🪙 ${fmtNum(p.wallet)} BLX</span><span class="chip mint">⚡ ${Math.round(p.energy)} energy</span><span class="chip violet">✦ ${Math.round(p.reputation)} reputation</span></div>
        <p class="profile-bio">You're one resident among many in BlaxkVille. The block has its own rhythm; you're part of it now.</p>
        <div class="profile-section" style="margin-top:6px"><h4>Your bag</h4><div class="chip-row">${invHtml}</div></div>
      </div></div>
      <div class="profile-section"><h4>Quick actions</h4>
        <div class="action-grid">
          <button class="action-tile" data-p="journal"><span class="at-ico">📓</span><b>Journal</b><span>what happened</span></button>
          <button class="action-tile" data-p="phone"><span class="at-ico">📱</span><b>Phone</b><span>messages & feed</span></button>
          <button class="action-tile" data-p="shop"><span class="at-ico">🛍️</span><b>Shop</b><span>gifts & food</span></button>
          <button class="action-tile" data-p="home"><span class="at-ico">🏠</span><b>Go home</b><span>sleep & reset</span></button>
        </div></div>`;
    const m = this.modal({ title: 'You', subtitle: 'Your resident file', icon: '🪞', body, wide: true });
    $$('[data-p]', m).forEach(b => b.addEventListener('click', () => {
      if (b.dataset.p === 'journal') this.openJournal();
      if (b.dataset.p === 'phone') { this.closeModal(); this.openPhone('feed'); }
      if (b.dataset.p === 'shop') this.openShop();
      if (b.dataset.p === 'home') { this.closeModal(); const h = this.app.world?.homes?.[p.home_id ?? 17]; if (h) this.app.walkTo(h.x + 46, h.y + 100); }
    }));
  }

  /* =====================================================================
     TALK
     ===================================================================== */
  watchConversationLog(log) {
    if(!log || !window.ResizeObserver)return;
    this.chatObservers ||= new Map();
    for(const [el,observer] of this.chatObservers) if(!el.isConnected){observer.disconnect();this.chatObservers.delete(el);}
    if(this.chatObservers.has(log))return;
    let previousHeight=log.clientHeight;
    const observer=new ResizeObserver(()=>{
      const following=log.scrollHeight-log.scrollTop-previousHeight<70;
      previousHeight=log.clientHeight;
      if(following)log.scrollTop=log.scrollHeight;
    });
    observer.observe(log);this.chatObservers.set(log,observer);
  }

  async openTalk(npcId, opts = {}) {
    const npc = this.npc(npcId);
    if (!npc) return;
    let lease;
    try {lease=await this.app.doAction('talk_begin',{npc_id:npcId})}
    catch(e){this.toast({title:'Cannot talk now',body:e.message,kind:'info'});return}
    this.voiceCtx = { mode: 'talk', npcId };
    const firstTime = (npc.rel?.familiarity || 0) < 3;
    let opener = npc.status === 'sleeping'
      ? `${npc.first} is asleep. You decide not to wake them.`
      : this.talkOpener(npc, firstTime);
    if((lease.history||[]).some(t=>t.user))opener="Good to see you. We can pick up our gist here.";
    const previous = (lease.history || []).map(t=>`${t.user ? `<div class="chat-row player"><div class="bubble">${esc(t.user)}<span class="bubble-meta">You · earlier ${esc(t.medium)}</span></div></div>` : ''}${t.reply ? `<div class="chat-row npc"><div class="bubble">${esc(t.reply)}<span class="bubble-meta">${esc(npc.first)} · earlier ${esc(t.medium)}</span></div></div>` : ''}`).join('');
    const body = `
      <div class="chat-shell">
        <div class="chat-scroll" id="talk-scroll" role="log" aria-label="Conversation">
          ${previous}
          <div class="chat-row npc">
            <span class="chat-avatar"><img src="${avatarUrl(npc.look, 64, 'head', npc.mood)}" style="width:100%;height:100%;object-fit:cover" alt=""/></span>
            <div class="bubble">${esc(opener)}<span class="bubble-meta">${esc(npc.name)} · ${MOOD_ICONS[npc.mood] || '🙂'} ${esc(npc.mood)}</span></div>
          </div>
        </div>
        <details class="talk-options"><summary>Quick replies</summary><div class="quick-chips" id="talk-chips">
          ${[['greet', '👋 Greet'], ['joke', '😄 Joke'], ['compliment', '✨ Compliment'], ['flirt', '💛 Flirt'], ['gossip', '👀 Gossip'], ['deep', '🫶 Deep talk'], ['apology', '🕊️ Apologize'], ['ask_date', '🌙 Ask out'], ['invite', '🎟️ Invite'], ['goodbye', '👋 Bye']]
            .map(([k, l]) => `<button class="qchip" data-intent="${k}">${l}</button>`).join('')}
        </div></details>
        <div class="chat-input-row">
          <button class="mic-btn" id="talk-mic" title="Speak (browser speech)">🎙️</button>
          <textarea class="chat-input" id="talk-input" rows="1" maxlength="280" placeholder="Say something to ${esc(npc.first)}…"></textarea>
          <button class="chat-send" id="talk-send" title="Send">↑</button>
        </div>
        <div class="voice-status" id="talk-voice-status"></div>
      </div>`;
    const foot = `<button class="btn ghost" data-t="profile">Profile</button>
      <button class="btn ghost" data-t="phone">Text instead</button>`;
    const asleep = npc.status === 'sleeping';
    const modal = this.modal({
      title: `${npc.first}`, subtitle: `${npc.occupation} · ${STATUS_LABEL[npc.status] || ''} · ${MOOD_ICONS[npc.mood] || ''} ${npc.mood}`,
      icon: '💬', body, foot, wide: true, className: 'talk-modal',
    });
    this.talkLease={session_id:lease.session_id,npc_id:npcId};
    this.talkHeartbeat=setInterval(async()=>{
      const current=this.talkLease;if(!current)return;
      try{await this.app.api('/api/action',{method:'POST',body:{type:'talk_keepalive',...current}})}
      catch(e){if(this.talkLease===current)this.finishTalkUI(e.code==='session_ended'?'They have left the conversation.':e.message)}
    },5000);
    this.bindTalk(modal, npc, { asleep });
    this.watchConversationLog($('#talk-scroll'));
    if (!asleep) $('#talk-input')?.focus({preventScroll:true});
    requestAnimationFrame(()=>{const log=$('#talk-scroll');if(log)log.scrollTop=log.scrollHeight});
    $$('[data-t]', modal).forEach(b => b.addEventListener('click', () => {
      if (b.dataset.t === 'profile') this.openProfile(npc.id);
      if (b.dataset.t === 'phone') { this.closeModal(); this.openPhone('messages', { npcId: npc.id }); }
    }));
    if (opts.intent) setTimeout(() => this.sendQuickIntent(npc, opts.intent), 320);
    if (opts.prefill) { $('#talk-input').value = opts.prefill; }
  }

  talkOpener(npc, firstTime) {
    const label = npc.rel?.label || 'acquaintance';
    if (firstTime) {
      return [`${npc.first} looks up and gives you a friendly once-over. “You're the new face on Juniper Row, right? I'm ${npc.first}.”`,
        `“Oh — hi. Don't think we've met. I'm ${npc.first}. I'd shake your hand but I'm holding a very important snack.”`][hashish(npc.id) % 2];
    }
    if (label === 'rival') return `${npc.first} acknowledges you with the enthusiasm of a person finding a parking ticket. “What?”`;
    if (label === 'close friend' || label === 'partner') return `${npc.first} lights up. “There you are. I was literally about to text you.”`;
    if (label === 'dating' || label === 'crush') return `${npc.first} smiles at you a little differently than they smile at everyone else. “Hey, you.”`;
    return [`${npc.first} gives you a nod. “Hey. How's your day going?”`,
      `${npc.first} looks up from ${npc.activity || 'whatever they were doing'}. “Oh, hey — good timing.”`,
      `“Back again,” ${npc.first} says, half a smile. “I'm not complaining.”`][hashish(npc.id + label) % 3];
  }

  bindTalk(modal, npc, { asleep = false } = {}) {
    const input = $('#talk-input', modal);
    const send = () => {
      const text = input.value.trim();
      if (!text || $('#talk-scroll')?.dataset.sending === '1') return;
      input.value = '';
      this.sendTalkText(npc, text);
    };
    $('#talk-send', modal).onclick = send;
    input.addEventListener('keydown', e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); } });
    $$('[data-intent]', modal).forEach(chip => chip.addEventListener('click', () => {
      this.sendQuickIntent(npc, chip.dataset.intent);
    }));
    $('#talk-mic', modal).onclick = async () => {
      if (asleep) return;
      if (!(await this.app.ensureMicConsent())) return;
      this.voiceCtx = { mode: 'talk', npcId: npc.id };
      this.app.voice.startListening();
      $('#talk-mic').classList.add('live');
    };
    if (asleep) {
      input.disabled = true;
      input.placeholder = `${npc.first} is asleep — come back later.`;
      $('#talk-send', modal).disabled = true;
      $$('[data-intent]', modal).forEach(c => { c.disabled = true; c.classList.add('dimmed'); });
      $('#talk-mic', modal).disabled = true;
    }
  }

  async sendQuickIntent(npc, intent) {
    if (!this.currentModal || $('#talk-scroll')?.dataset.sending === '1') return;
    const label = { greet: 'Say hi', joke: 'Tell a joke', compliment: 'Give a compliment', flirt: 'Flirt', ask_date: 'Ask them out', apologize: 'Apologize', gossip: 'Ask for the gossip', invite: 'Invite them out', deep: 'Have a real conversation', goodbye: 'Say goodbye' }[intent] || intent;
    this.addTalkBubble('player', `(${label})`);
    await this.sendTalkTurn(npc, null, intent);
  }

  async sendTalkText(npc, text) {
    this.addTalkBubble('player', text);
    await this.sendTalkTurn(npc, text, null);
  }

  async sendTalkTurn(npc, text, intent) {
    const scroll = $('#talk-scroll');
    if (!scroll || scroll.dataset.sending === '1') return;
    scroll.dataset.sending = '1';
    $$('#talk-send,#talk-chips button').forEach(el=>el.disabled=true);
    const typing = document.createElement('div');
    typing.className = 'chat-row npc';
    typing.innerHTML = `<span class="chat-avatar"><img src="${avatarUrl(npc.look, 64, 'head', npc.mood)}" style="width:100%;height:100%;object-fit:cover" alt=""/></span><div class="bubble typing"><i></i><i></i><i></i></div>`;
    scroll.appendChild(typing);
    scroll.scrollTop = scroll.scrollHeight;
    try {
      const res = text != null
        ? await this.app.doAction('talk', { npc_id: npc.id, text })
        : await this.app.doAction('intent', { npc_id: npc.id, intent });
      typing.remove();
      if (!scroll.isConnected || this.voiceCtx?.npcId !== npc.id) return;
      if(res.state?.civic&&res.state.civic.conversation?.npc_id!==npc.id&&!res.conversation_ended){this.finishTalkUI('They have left the conversation.');return}
      this.addTalkBubble('npc', res.reply, res);
      if (res.effects_display?.length) this.addEffectChips(res.effects_display);
      if (res.coaching && scroll.isConnected) {
        $('#talk-voice-status').textContent = res.coaching;
      }
      if (res.conversation_ended) this.finishTalkUI();
      if (res.date_offer) this.addDateCard(res.date_offer);
      if (intent === 'ask_date' && res.accepted === false) this.toast({ title: 'Not this time', body: res.reason || 'They said no.', kind: 'info' });
      if (res.accepted === true && intent === 'ask_date') this.toast({ title: 'Date confirmed 🌙', body: `${npc.first} said yes — ${this.locationName(res.date_offer.venue)}.`, kind: 'good' });
      if (this.settings.speakReplies) this.speakLine(res.reply, npc);
      // doAction already applied the authoritative state; no extra refresh needed.
    } catch (e) {
      typing.remove();
      if (e.code === 'asleep') {
        this.addTalkBubble('npc', e.message, null);
        return;
      }
      if (text && scroll.isConnected && !$('#talk-input').value) $('#talk-input').value=text;
      this.toast({ title: 'That didn\'t land', body: e.message || 'Something went wrong.', kind: 'danger' });
    } finally {
      scroll.dataset.sending = '';
      scroll.scrollTop=scroll.scrollHeight;
      requestAnimationFrame(()=>{if(scroll.isConnected)scroll.scrollTop=scroll.scrollHeight});
      if(scroll.isConnected && this.talkLease) $$('#talk-send,#talk-chips button').forEach(el=>el.disabled=false);
    }
  }

  addTalkBubble(who, text, meta = null) {
    const scroll = $('#talk-scroll');
    if (!scroll) return;
    const npc = this.voiceCtx?.mode === 'talk' ? this.npc(this.voiceCtx.npcId) : null;
    const row = document.createElement('div');
    row.className = `chat-row ${who}`;
    const avatar = who === 'npc'
      ? `<span class="chat-avatar"><img src="${avatarUrl(npc?.look, 64, 'head', npc?.mood)}" style="width:100%;height:100%;object-fit:cover" alt=""/></span>`
      : '';
    const moodLine=who==='npc'&&meta?.mood?` · ${MOOD_ICONS[meta.mood]||''} ${meta.mood}`:'';
    const metaLine=moodLine+(who==='npc'&&meta?.dialogue_source?` · ${meta.dialogue_source==='offline'?'local reply':meta.dialogue_source}`:'');
    row.innerHTML = `${avatar}<div class="bubble">${esc(text)}<span class="bubble-meta">${who === 'npc' ? esc(npc?.first || '') : 'You'}${esc(metaLine)}</span></div>`;
    scroll.appendChild(row);
    scroll.scrollTop = scroll.scrollHeight;
  }

  addEffectChips(effects) {
    const status = $('#talk-voice-status');
    if(status) {status.textContent=effects.join(' · ');status.title=status.textContent;}
  }

  addDateCard(offer) {
    const scroll = $('#talk-scroll');
    if (!scroll) return;
    const el = document.createElement('div');
    el.className = 'story-card';
    el.style.cssText = 'align-self:center;width:100%;margin-top:4px';
    el.innerHTML = `<div class="sc-kicker">Date confirmed</div>
      <h4>${esc(this.locationName(offer.venue))} · ${esc(this.fmtClockShort(offer.due))}</h4>
      <p>They'll be there. Don't be late — the block talks.</p>
      <div class="row" style="margin-top:8px">
        <button class="btn tiny ghost" data-goto="${esc(offer.venue)}">Walk there</button>
        <button class="btn tiny primary" data-date="${esc(offer.id)}">Date details</button>
      </div>`;
    el.querySelector('[data-goto]').onclick = () => { this.closeModal(); this.walkToLocation(offer.venue); };
    el.querySelector('[data-date]').onclick = () => this.openDateOffer(offer.id);
    scroll.appendChild(el);
    scroll.scrollTop = scroll.scrollHeight;
  }

  speakLine(text, npc) {
    this.app.voice.speak(text, { ...npc, name: npc.name || npc.first }, { startedAt: performance.now() });
  }

  onVoicePartial(text, final) {
    if (this.voiceCtx?.mode === 'talk') {
      const input = $('#talk-input');
      if (input) input.value = text;
      const status = $('#talk-voice-status');
      if (status) status.innerHTML = final ? `<b>Heard:</b> ${esc(text)}` : `<i>…${esc(text)}</i>`;
    }
    if (this.voiceCtx?.mode === 'call') {
      this.setCallCaption(text, true);
    }
  }

  onVoiceFinal(text) {
    if (this.voiceCtx?.mode === 'talk') {
      const mic = $('#talk-mic');
      if (mic) mic.classList.remove('live');
      const input = $('#talk-input');
      if (input) input.value = '';
      const npc = this.npc(this.voiceCtx.npcId);
      if (npc) this.sendTalkText(npc, text);
    } else if (this.voiceCtx?.mode === 'call' && this.callSession) {
      this.sendCallTurn(text);
    }
  }

  onVoiceState(s) {
    if (this.voiceCtx?.mode === 'talk') {
      const status = $('#talk-voice-status');
      if (status && s.status) status.textContent = s.status;
    }
    if (this.voiceCtx?.mode === 'call') {
      const mic = $('#call-mic');
      if (mic) mic.classList.toggle('active', !!s.listening);
    }
  }

  onVoiceLevel(level) {
    if (this.voiceCtx?.mode === 'call') {
      const bar = $('#call-mic-level i');
      if (bar) bar.style.width = `${Math.min(100, level * 800)}%`;
    }
    if (this.voiceCtx?.mode === 'talk') {
      const mic = $('#talk-mic');
      if (mic && this.app.voice.listening) mic.style.boxShadow = `0 0 ${Math.round(level * 120)}px rgba(255,180,84,.5)`;
    }
  }

  onBargeIn() {
    if (this.voiceCtx?.mode === 'call') {
      this.setCallCaption('(you interrupted — they stopped talking)', false);
      this.toast({ title: 'Barge-in', body: 'You spoke over them. They stopped, like a real person would.', kind: 'info', ttl: 3200 });
    }
  }

  /* =====================================================================
     GIFTS / SHOP
     ===================================================================== */
  openGiftPicker(npcId) {
    const npc = this.npc(npcId);
    if (!npc) return;
    const items = this.app.world?.items || [];
    const menu = this.app.world?.menu || [];
    const all = [...items, ...menu];
    const inv = this.app.state?.player?.inventory || {};
    const entries = Object.entries(inv).filter(([, q]) => q > 0);
    const reach = (this.app.world?.config?.interact_radius ?? 115) - 6;
    const near = this.playerNearNpc(npc, reach);
    const body = entries.length ? `
      ${near ? '' : `<div class="hint-note warn">You need to be closer to hand this over. <button class="btn tiny primary" data-walkgift="1" style="margin-left:6px">Walk to ${esc(npc.first)}</button></div>`}
      <div class="hint-note">Gifts have <b>recipient-specific meaning</b>. ${esc(npc.first)} likes ${(npc.hobbies || []).map(esc).join(', ') || 'simple things'} — repeated identical gifts lose meaning fast.</div>
      <div class="item-grid">
        ${entries.map(([id, qty]) => {
          const item = all.find(i => i.id === id) || { name: id, icon: '🎁', blurb: '' };
          return `<div class="item-card">
            <span class="ic-icon">${item.icon || '🎁'}</span><b>${esc(item.name)}</b>
            <span class="ic-blurb">${esc(item.blurb || '')}</span>
            <div class="ic-foot"><span class="qty-chip">×${qty}</span>
            <button class="btn tiny primary" data-gift="${esc(id)}" ${near ? '' : 'disabled'}>Give</button></div>
          </div>`;
        }).join('')}
      </div>` : `<div class="empty-note">Your bag is empty.<br/>Visit a shop from the phone to buy something thoughtful.</div>`;
    const foot = `<button class="btn ghost left" data-shop="1">🛍️ Open shop</button><button class="btn ghost" data-close="1">Cancel</button>`;
    const m = this.modal({ title: `Give something to ${npc.first}`, subtitle: 'The thought matters — and so does the item', icon: '🎁', body, foot });
    $$('[data-close]', m).forEach(b => b.onclick = () => this.closeModal());
    $$('[data-gift]', m).forEach(b => b.onclick = async () => {
      try {
        const res = await this.app.doAction('gift', { npc_id: npc.id, item_id: b.dataset.gift });
        this.closeModal();
        const moodWord = { love: 'loved it', like: 'liked it', meh: 'was polite about it' }[res.mood] || 'reacted';
        this.toast({ title: `${res.npc.first} ${moodWord}`, body: res.reply, kind: res.mood === 'love' ? 'good' : 'info', ttl: 7000 });
        const detail = [...(res.effects_display || [])];
        if (res.reasons?.length) detail.push(`because ${res.reasons.join(' and ')}`);
        if (res.repetition >= 2) detail.push(`${res.repetition}th time — it lands softer`);
        if (detail.length) setTimeout(() => this.toast({ title: 'Relationship', body: detail.join(' · '), kind: 'info', ttl: 5000 }), 500);
      } catch (e) { this.toast({ title: 'Gift failed', body: e.message, kind: 'danger' }); }
    });
    $$('[data-shop]', m).forEach(b => b.onclick = () => this.openShop());
    $$('[data-walkgift]', m).forEach(b => b.onclick = () => {
      this.closeModal();
      this.app.walkTo(npc.x, npc.y + 60, () => this.openGiftPicker(npc.id));
    });
  }

  openShop(filterShop = null) {
    const items = this.app.world?.items || [];
    const inv = this.app.state?.player?.inventory || {};
    const wallet = this.app.state?.player?.wallet ?? 0;
    const nearShop = (filterShop && this.playerNearLoc(filterShop, 200));
    const body = `
      <div class="hint-note">Prices are fictional <b>BLX</b> (1 BLX ≈ 1 USD internal reference · closed-loop, no cash value).
      ${nearShop ? 'You\'re at the shop — no delivery fee.' : 'Ordering remotely adds a small <b>delivery fee</b>.'}</div>
      <div class="tab-row">
        <span class="pill amber">🪙 ${fmtNum(wallet)} BLX</span>
        <span class="pill ghost">${Object.values(inv).reduce((a, b) => a + b, 0)} items in bag</span>
      </div>
      <div class="item-grid">
        ${items.map(item => {
          const owned = inv[item.id] || 0;
          const price = item.price + (nearShop ? 0 : Math.ceil(item.price * .1));
          return `<div class="item-card">
            <span class="ic-icon">${item.icon}</span><b>${esc(item.name)}</b>
            <span class="ic-blurb">${esc(item.blurb)}</span>
            <div class="ic-foot">
              ${owned ? `<span class="qty-chip">have ×${owned}</span>` : ''}
              <span class="price">${fmtNum(price)} BLX</span>
            </div>
            <button class="btn tiny ${wallet >= price ? 'primary' : ''}" data-buy="${esc(item.id)}" ${wallet < price ? 'disabled' : ''}>Buy</button>
          </div>`;
        }).join('')}
      </div>
      ${(this.app.world?.menu || []).length ? `<div class="side-section-title" style="margin-top:18px">Cafe counter · eat now</div>
      <div class="item-grid">
        ${(this.app.world.menu || []).map(item => {
          const owned = inv[item.id] || 0;
          const price = item.price + (nearShop ? 0 : Math.ceil(item.price * .1));
          return `<div class="item-card">
            <span class="ic-icon">${item.icon}</span><b>${esc(item.name)}</b>
            <span class="ic-blurb">${esc(item.blurb)} · energy +${item.energy}</span>
            <div class="ic-foot">
              ${owned ? `<span class="qty-chip">have ×${owned}</span>` : ''}
              <span class="price">${fmtNum(price)} BLX</span>
            </div>
            <div class="row" style="gap:6px">
              <button class="btn tiny ${wallet >= price ? 'primary' : ''}" data-buy="${esc(item.id)}" ${wallet < price ? 'disabled' : ''}>Buy</button>
              ${owned ? `<button class="btn tiny ghost" data-eat="${esc(item.id)}">Eat</button>` : ''}
            </div>
          </div>`;
        }).join('')}
      </div>` : ''}`;
    const m = this.modal({ title: 'BlaxkVille shop', subtitle: 'Gifts, snacks and small kindnesses', icon: '🛍️', body, wide: true });
    $$('[data-buy]', m).forEach(b => b.onclick = async () => {
      try {
        const res = await this.app.doAction('buy', { item_id: b.dataset.buy, remote: !nearShop });
        this.toast({ title: 'Purchased', body: res.text, kind: 'money' });
        this.openShop(filterShop);
      } catch (e) { this.toast({ title: 'Couldn\'t buy that', body: e.message, kind: 'danger' }); }
    });
    $$('[data-eat]', m).forEach(b => b.onclick = async () => {
      try {
        const res = await this.app.doAction('use_item', { item_id: b.dataset.eat });
        this.toast({ title: 'Eaten', body: `${res.text} Energy ${Math.round(res.energy)}.`, kind: 'good' });
        this.openShop(filterShop);
      } catch (e) { this.toast({ title: 'Couldn\'t eat that', body: e.message, kind: 'danger' }); }
    });
  }

  /* =====================================================================
     VENUE
     ===================================================================== */
  openCivicOverview() {
    const c=this.app.state?.civic||{};
    const active=(c.incidents||[]).filter(i=>!['resolved','retreated'].includes(i.phase));
    const body=`<div class="civic-summary"><span>♥ Health <b>${c.player_health??100}</b></span><span>Police attention <b>${c.heat??0}/100</b></span></div>
      <p class="civic-copy">A living town, with real consequences. Fights and raids are non-graphic. Deaths are permanent, including named neighbours.</p>
      <div class="civic-sites">${['hospital','police','barracks','graveyard','black_market'].map(id=>{const l=this.loc(id);return `<button class="civic-site" data-csite="${id}"><span>${l.icon}</span><b>${esc(l.name)}</b><small>${id==='hospital'?`${(c.patients||[]).length} recovering`:id==='graveyard'?`${(c.memorials||[]).length} remembered`:id==='black_market'?'Fictional risky businesses':'Safety & response'}</small></button>`}).join('')}</div>
      <h3>Neighbourhood incidents</h3>${active.length?active.map(i=>`<div class="civic-incident"><b>${esc(i.kind==='raid'?'Armed bandit squad':i.kind)}</b><span>${esc(this.locationName(i.location))} · ${esc(i.phase)}</span><button class="btn tiny ghost" data-incident-go="${esc(i.location)}">Go nearby</button></div>`).join(''):'<p class="civic-copy">No active reports. Patrols are on their routes.</p>'}
      <button class="btn mint" data-cop-report>Report an incident</button>
      <p class="civic-copy">Dialogue: ${esc(c.dialogue?.enabled?c.dialogue.model:'offline fallback — add GEMINI_API_KEY on the server')}. Free-tier availability and quotas belong to Google; the app cannot change your billing plan.</p>`;
    const m=this.modal({title:'Neighbourhood',subtitle:'Care · safety · consequences',icon:'🛡️',body,wide:true});
    $$('[data-csite]',m).forEach(b=>b.onclick=()=>this.openCivicSite(b.dataset.csite));
    $$('[data-incident-go]',m).forEach(b=>b.onclick=()=>{this.closeModal();this.walkToLocation(b.dataset.incidentGo)});
    $('[data-cop-report]',m).onclick=()=>this.doCivic('report');
  }

  async doCivic(op,extra={}) {
    try{const res=await this.app.doAction('civic',{op,...extra});this.toast({title:'Neighbourhood',body:res.text,kind:'info'});await this.app.apiGet('/api/state').then(s=>this.app.applyState(s));return res}
    catch(e){this.toast({title:'Not now',body:e.message,kind:'danger'});return null}
  }

  openCivicSite(id) {
    const l=this.loc(id),c=this.app.state?.civic||{},near=this.playerNearLoc(id,110);
    let content='';
    if(id==='hospital')content=`<p>Emergency care and recovery. Your health: <b>${c.player_health??100}/100</b>.</p><button class="btn mint" data-civic-op="treatment" ${near?'':'disabled'}>Get treatment · up to 18 BLX</button><h3>Recovery ward</h3>${(c.patients||[]).map(n=>`<div class="civic-record"><b>${esc(n.first)}</b><span>${n.health}/100 health · ${n.remaining_minutes} game minutes of recovery</span></div>`).join('')||'<p class="civic-copy">No residents admitted.</p>'}`;
    if(id==='graveyard')content=`<p class="civic-copy">These are people from this world, not respawning game pieces. Their past messages and relationships remain in the save; their stories do not continue after death.</p>${(c.memorials||[]).map(n=>`<article class="memorial"><span>🕯️</span><div><h3>${esc(n.name)}</h3><p>Age ${n.age} · ${fmtClock(n.minute)}</p><p>${esc(n.cause)}</p></div></article>`).join('')||'<p class="civic-copy">No residents have died. May it stay quiet here.</p>'}<button class="btn ghost" data-civic-op="respects" ${near?'':'disabled'}>Pay respects</button>`;
    if(id==='police'||id==='barracks')content=`<p class="civic-copy">${id==='police'?'Officers respond to theft and public disputes. Your actions can lead to fines and higher police attention.':'Soldiers support police against armed four-person bandit squads. Keep civilians out of the confrontation.'}</p><button class="btn mint" data-civic-op="report">Report an incident</button><h3>Recent reports</h3>${(c.incidents||[]).slice(-6).reverse().map(i=>`<div class="civic-record"><b>${esc(i.kind)}</b><span>${esc(this.locationName(i.location))} · ${esc(i.phase)}</span></div>`).join('')||'<p class="civic-copy">No reports yet.</p>'}`;
    if(id==='black_market')content=`<p class="civic-copy">Fictional gun and drug trading, modelled as abstract stakes and stock. No crafting, sourcing or real-world instructions. Returns arrive every eight game hours; police may seize the business. Losses are real in this save.</p><div class="civic-summary">Police attention <b>${c.heat??0}/100</b></div>${['guns','drugs'].map(category=>{const b=c.businesses?.[category],live=b?.status==='operating';return `<section class="business-card"><h3>${category==='guns'?'Gun business':'Drug business'}</h3><p>${live?`Operating · ${b.balance} BLX uncollected`:`${esc(b?.status||'Not owned')} · stake ${category==='guns'?220:160} BLX`}</p>${live?`<button class="btn tiny mint" data-biz="business_collect" data-category="${category}" ${near?'':'disabled'}>Collect</button> <button class="btn tiny ghost" data-biz="business_close" data-category="${category}" ${near?'':'disabled'}>Close business</button>`:`<button class="btn tiny danger" data-biz="business_start" data-category="${category}" ${near?'':'disabled'}>Invest stake</button>`}</section>`}).join('')}`;
    const body=`<div class="civic-site-head"><span>${l.icon}</span><p>${esc(l.desc)}</p></div>${!near?'<p class="civic-copy">Walk to the entrance for local services.</p>':''}<button class="btn ghost" data-civic-go>Walk here</button><div class="civic-content">${content}</div>`;
    const m=this.modal({title:l.name,subtitle:'BlaxkVille neighbourhood services',icon:l.icon,body,wide:true});
    $('[data-civic-go]',m).onclick=()=>{this.closeModal();this.walkToLocation(id)};
    $$('[data-civic-op]',m).forEach(b=>b.onclick=async()=>{if(await this.doCivic(b.dataset.civicOp))this.openCivicSite(id)});
    $$('[data-biz]',m).forEach(b=>b.onclick=async()=>{const op=b.dataset.biz,category=b.dataset.category;if(op==='business_start'&&!await this.confirm({title:'Risk this stake?',body:'Police can seize this fictional business. Your stake is not refundable.',confirmLabel:'Invest',danger:true}))return;if(await this.doCivic(op,{category}))this.openCivicSite(id)});
  }

  openVenue(locId, opts = {}) {
    const l = this.loc(locId);
    if (!l) return;
    if(['hospital','graveyard','police','barracks','black_market'].includes(locId))return this.openCivicSite(locId);
    const st = this.app.state;
    const near = this.playerNearLoc(locId, 170);
    const dist = this.distToLoc(locId);
    const openNow = st?.clock ? (st.clock.hour >= l.hours[0] && st.clock.hour <= l.hours[1]) : true;
    const people = (st?.npcs || []).filter(n => n.loc === locId).slice(0, 8);
    const caseOpen = (st?.cases || [])[0];
    const isClueSpot = caseOpen && (caseOpen.helpful || []).some(h => h.startsWith(locId + ':'));
    const clueFound = caseOpen && (caseOpen.evidence || []).some(e => e.startsWith(locId + ':'));
    const body = `
      <div class="hint-note">${esc(l.desc)}<br/><b>${openNow ? 'Open now' : 'Closed right now'}</b> · ${l.hours[0]}:00–${l.hours[1]}:00 · ${near ? 'you are here' : `${Math.round(dist)} px away`}</div>
      <div class="side-section-title">Activities</div>
      <div class="item-grid">
        ${(l.activities || []).map(a => `
          <div class="item-card">
            <span class="ic-icon">${a.icon || '✨'}</span>
            <b>${esc(a.label)}</b>
            <span class="ic-blurb">${a.minutes} min · mood +${a.mood}${a.cost ? ` · ${a.cost} BLX` : ' · free'}</span>
            <button class="btn tiny ${near ? 'primary' : 'ghost'}" data-activity="${esc(a.id)}" ${(!near || !openNow) ? 'disabled' : ''}>${near ? 'Do it' : 'Walk closer'}</button>
          </div>`).join('')}
      </div>
      <div class="divider"></div>
      <div class="row wrap">
        <button class="btn ${near ? 'mint' : 'ghost'}" data-work="1" ${(!near || !openNow) ? 'disabled' : ''}>💼 Work a ${4}-hour shift</button>
        ${isClueSpot ? `<button class="btn ${near && !clueFound ? 'coral' : 'ghost'}" data-investigate="1" ${(!near || clueFound) ? 'disabled' : ''}>🔎 ${clueFound ? 'Clue already found' : 'Investigate the case'}</button>` : ''}
        ${locId === 'square' && !st?.player?.flags?.cart_owned ? `<button class="btn ${near ? 'primary' : 'ghost'}" data-cart="1" ${!near ? 'disabled' : ''}>🛒 Set up a street cart (250 BLX)</button>` : ''}
        ${locId === 'square' && st?.player?.flags?.cart_owned ? '<span class="pill mint">🛒 Your cart is open here</span>' : ''}
        ${!near ? `<button class="btn primary" data-go="1">🚶 Walk there</button>` : ''}
      </div>
      <div class="divider"></div>
      <div class="side-section-title">People here (${people.length})</div>
      ${people.length ? `<div class="chip-row">${people.map(n => `<button class="connection" data-pnpc="${n.id}"><b>${esc(n.first)}</b> · ${esc(n.mood)}</button>`).join('')}</div>` : '<div class="empty-note">Nobody here right now. The block moves fast.</div>'}
    `;
    const foot = `<span class="pill ghost left">${l.icon} ${esc(l.name)}</span>
      ${l.role === 'shop' ? '<button class="btn ghost" data-shop="1">Shop the catalog</button>' : ''}
      <button class="btn ghost" data-close="1">Close</button>`;
    const m = this.modal({ title: l.name, subtitle: `${l.icon} ${openNow ? 'Open' : 'Closed'} · ${l.hours[0]}:00–${l.hours[1]}:00`, icon: l.icon || '📍', body, foot, wide: true });
    $$('[data-close]', m).forEach(b => b.onclick = () => this.closeModal());
    $$('[data-pnpc]', m).forEach(b => b.onclick = () => this.openProfile(b.dataset.pnpc));
    $$('[data-go]', m).forEach(b => b.onclick = () => { this.closeModal(); this.walkToLocation(locId); });
    $$('[data-shop]', m).forEach(b => b.onclick = () => this.openShop(locId));
    $$('[data-activity]', m).forEach(b => b.onclick = () => this.doActivity(locId, b.dataset.activity));
    $$('[data-work]', m).forEach(b => b.onclick = () => this.doWork(locId));
    $$('[data-investigate]', m).forEach(b => b.onclick = () => this.doInvestigate(locId));
    $$('[data-cart]', m).forEach(b => b.onclick = async () => {
      try {
        const res = await this.app.doAction('start_business', {});
        this.toast({ title: 'Cart open', body: res.text, kind: 'good' });
        this.closeModal();
      } catch (e) { this.toast({ title: 'Not yet', body: e.message, kind: 'danger' }); }
    });
  }

  async doActivity(locId, activityId) {
    try {
      const res = await this.app.doAction('activity', { location_id: locId, activity_id: activityId });
      this.closeModal();
      this.toast({ title: 'Time passes', body: res.text, kind: 'good' });
      if (res.notices?.length) this.showWhileAway(res.notices);
    } catch (e) { this.toast({ title: 'Can\'t do that', body: e.message, kind: 'danger' }); }
  }

  showBusy(busy, pending=false) {
    let el=$('#shift-lock');
    if(!busy&&!pending){el?.remove();this.app.inputLocked=false;return}
    this.app.inputLocked=true;this.app.view.keys.clear();
    if(!el){el=document.createElement('div');el.id='shift-lock';el.setAttribute('role','dialog');el.setAttribute('aria-modal','true');el.setAttribute('aria-label','Shift in progress');document.body.appendChild(el)}
    const label=pending?'Starting your shift…':(busy.label||'Finishing your shift…');
    el.innerHTML=`<div class="shift-card"><div class="shift-orbit">💼</div><h2>On the clock</h2><p>${esc(label)}</p><div class="shift-progress"><i></i></div><small>${pending?'Time is passing in BlaxkVille.':`${Math.max(1,Math.ceil(busy.remaining_seconds||1))} seconds · controls locked`}</small></div>`;
  }

  async doWork(locId) {
    if(this.workPending||this.app.inputLocked)return;
    this.workPending=true;this.showBusy(null,true);
    try {
      const res = await this.app.doAction('work', { location_id: locId });
      this.closeModal();
      this.toast({ title: 'Shift complete', body: `${res.text}`, kind: 'money' });
      if (res.notices?.length) this.showWhileAway(res.notices);
    } catch (e) { this.toast({ title: 'Can\'t work now', body: e.message, kind: 'danger' }); }
    finally{this.workPending=false;await this.app.apiGet('/api/state').then(s=>this.app.applyState(s)).catch(()=>this.showBusy(null))}
  }

  async doInvestigate(locId) {
    try {
      const res = await this.app.doAction('investigate', { location_id: locId });
      this.closeModal();
      this.toast({ title: 'Clue found', body: res.evidence, kind: 'story', ttl: 8000 });
      if (res.enough) this.toast({ title: 'Enough evidence', body: 'Open the case file and present your findings.', kind: 'good' });
    } catch (e) { this.toast({ title: 'Nothing here', body: e.message, kind: 'danger' }); }
  }

  showWhileAway(notices) {
    const items = (notices || []).slice(0, 5).map(n => `<div class="wa-item"><span>${n.kind === 'alert' ? '🚨' : n.kind === 'event' ? '🎪' : '📌'}</span><span><b>${esc(n.title)}</b><br/><span class="muted">${esc(n.body)}</span></span></div>`).join('');
    if (!items) return;
    this.modal({
      title: 'While you were away', subtitle: 'The block kept living', icon: '⏱️',
      body: `<div class="while-away">${items}</div>`,
      foot: '<button class="btn primary" data-close="1">Back to it</button>',
    });
    $$('[data-close]').forEach(b => b.onclick = () => this.closeModal());
  }

  /* =====================================================================
     PHONE
     ===================================================================== */
  async openPhone(tab = 'messages', opts = {}) {
    this.phoneTab = tab;
    this.phoneThread = opts.npcId || null;
    const root = $('#phone-root');
    root.classList.remove('hidden');
    root.innerHTML = `
      <div class="phone-scrim" data-pclose="1"></div>
      <div class="phone one-ui" role="dialog" aria-label="BlaxkVille phone">
        <div class="phone-status"><span>${esc(fmtClock(this.app.state?.clock?.minute || 0))}</span><i></i><span>▮▮▮  ◉  ▰</span></div>
        <div class="phone-head">
          <div><h3>Messages</h3><p>${esc(this.app.state?.clock?.label || '')} · ${esc(this.app.state?.player?.name || '')}</p></div>
          <button class="icon-btn" data-prefresh="1" aria-label="Refresh phone" title="Refresh this tab">↻</button>
          <button class="icon-btn" data-pclose="1" aria-label="Close phone">✕</button>
        </div>
        <div class="phone-tabs">
          ${[['messages', '💬', 'Messages'], ['feed', '📰', 'Gist Hub'], ['calendar', '📅', 'Calendar'], ['wallet', '🪙', 'Wallet'], ['cases', '🗂️', 'Cases'], ['alerts', '🔔', 'Alerts'], ['guide', '♡', 'Connections']]
            .map(([id, ico, label]) => `<button class="phone-tab ${tab === id ? 'active' : ''}" data-ptab="${id}"><span class="pt-ico">${ico}</span>${label}</button>`).join('')}
        </div>
        <div class="phone-body" id="phone-body"><div class="empty-note">Loading…</div></div>
        <button class="phone-gesture" data-pclose="1" aria-label="Put phone away"><i></i></button>
      </div>`;
    this.app.view.keys.clear();
    root.oninput = e => {
      if (e.target.matches('input,textarea') && e.target.id) this.phoneDrafts.set(this.draftKey(e.target.id), e.target.value);
    };
    root.querySelector('[data-prefresh]').onclick = () => this.renderPhoneBody();
    root.querySelectorAll('[data-pclose]').forEach(el => el.addEventListener('click', () => this.closePhone()));
    root.querySelectorAll('[data-ptab]').forEach(el => el.addEventListener('click', () => {
      this.phoneTab = el.dataset.ptab;
      this.phoneThread = null;
      root.querySelectorAll('.phone-tab').forEach(t => t.classList.toggle('active', t.dataset.ptab === this.phoneTab));
      this.renderPhoneBody();
    }));
    await this.renderPhoneBody();
  }

  closePhone() {
    $('#phone-root').classList.add('hidden');
    $('#phone-root').innerHTML = '';
    this.app.voice.stopSpeaking();
  }

  draftKey(id) { return `${this.phoneTab}:${this.phoneThread || ''}:${id}`; }

  async renderPhoneBody() {
    const old = $('#phone-body');
    if (!old) return;
    // Explicit tab changes get a new node: an old async response can never
    // overwrite the current tab or wire its controls to the wrong resident.
    const body = document.createElement('div');
    body.id = 'phone-body'; body.className = 'phone-body';
    old.replaceWith(body);
    const heading = $('#phone-root .phone-head h3');
    if (heading) heading.textContent = ({messages:'Messages',feed:'Gist Hub',calendar:'Calendar',wallet:'Wallet',cases:'Case files',alerts:'Notifications',guide:'Connections'})[this.phoneTab] || 'Messages';
    const renderers = { guide: 'renderConnectionsGuide', messages: 'renderPhoneMessages', feed: 'renderPhoneFeed', calendar: 'renderPhoneCalendar',
      wallet: 'renderPhoneWallet', cases: 'renderPhoneCases', alerts: 'renderPhoneAlerts' };
    await this[renderers[this.phoneTab] || 'renderPhoneMessages'](body);
    if (!body.isConnected) return;
    for (const el of $$('input[id],textarea[id]', body)) {
      el.value = this.phoneDrafts.get(this.draftKey(el.id)) || '';
      el.dispatchEvent(new Event('input', { bubbles: true }));
    }
  }

  renderConnectionsGuide(body) {
    const people = this.app.state?.npcs || [];
    const milestones = [
      ['Break the ice', 'Introduce yourself and listen to someone’s interests.', people.some(n => (n.rel?.familiarity || 0) >= 8)],
      ['Build a connection', 'Show curiosity, follow up, and build trust over time.', people.some(n => (n.rel?.trust || 0) >= 30 && (n.rel?.familiarity || 0) >= 14)],
      ['Find mutual interest', 'Flirt only when it is welcome. A no means give them space.', people.some(n => (n.rel?.romance || 0) >= 10 && (n.rel?.familiarity || 0) >= 14)],
      ['Make a real plan', 'Ask for a date, agree on a place, and show up.', (this.app.state?.date_offers || []).length > 0 || people.some(n => (n.rel?.dates || 0) > 0)],
    ];
    body.innerHTML = `<section class="connection-guide"><span class="phone-section-title">Your social life</span>
      <h2>Good conversation.<br>Real connection.</h2>
      <p>Meet people, learn what makes them tick, and see whether the interest is mutual. Everyone here is an adult with their own life.</p>
      ${milestones.map(([title, detail, done]) => `<article class="connection-step"><span>${done ? '✓' : '○'}</span><div><b>${title}</b><p>${detail}</p></div></article>`).join('')}
      <div class="hint-note"><b>Try this next time</b><br>Ask one open question. Share something genuine. Follow up on what they actually said—not a script. Specific kindness beats repeated compliments.</div>
      <p class="ai-note">These are game milestones, not a rating of people or a promise of real-world dating results. Gifts never buy affection. Respect boundaries and rejection.</p></section>`;
  }

  async renderPhoneCalendar(body) {
    body.innerHTML = '<div class="empty-note">Reading the block calendar…</div>';
    let cal;
    try { cal = await this.app.apiGet('/api/calendar'); } catch (e) {
      if (!body.isConnected) return;
      body.innerHTML = `<div class="empty-note">Calendar unavailable: ${esc(e.message)}</div>`;
      return;
    }
    if (!body.isConnected) return;
    const live = cal.live || [];
    const upcoming = cal.upcoming || [];
    const birthdays = cal.birthdays || [];
    body.innerHTML = `
      <div class="phone-section-title">This week on the block</div>
      ${live.length ? live.map(e => `
        <div class="cal-row live">
          <span class="cal-ico">${e.icon}</span>
          <span class="cal-main"><b>${esc(e.title)} <span class="live-dot">● live</span></b>
            <span>${esc(e.where)} · ${esc(e.blurb)}</span></span>
          <button class="btn tiny primary" data-go-venue="${esc(e.venue)}">Go</button>
        </div>`).join('') : ''}
      ${upcoming.length ? upcoming.map(e => `
        <div class="cal-row">
          <span class="cal-ico">${e.icon}</span>
          <span class="cal-main"><b>${esc(e.title)}</b>
            <span>${esc(e.where)} · ${esc(this.fmtWhen(e.due))} · ${esc(e.detail || '')}</span></span>
          <button class="btn tiny ghost" data-go-venue="${esc(e.venue)}">Go</button>
        </div>`).join('') : '<div class="empty-note">Nothing scheduled. Suspicious.</div>'}
      ${birthdays.length ? `<div class="phone-section-title" style="margin-top:14px">Birthdays</div>
      ${birthdays.map(b => `
        <div class="cal-row">
          <span class="cal-ico">🎂</span>
          <span class="cal-main"><b>${esc(b.first)}</b><span>turns ${b.age} · ${esc(this.fmtWhen(b.due))}</span></span>
          <button class="btn tiny ghost" data-msg-bday="${esc(b.npc_id)}">Message</button>
        </div>`).join('')}` : ''}
      <div class="hint-note" style="margin-top:12px">Residents drift into these on their own — about a third of the ones who like the thing. If you want a specific person there, ask them.</div>`;
    $$('[data-go-venue]', body).forEach(b => b.onclick = () => {
      const loc = this.loc(b.dataset.goVenue);
      this.closePhone();
      if (!loc) return;
      this.app.walkTo(loc.x + loc.w / 2, loc.y + loc.h + 52, () => this.toast({
        title: loc.name, body: 'You made it. Open the venue card to step inside.', kind: 'info', ttl: 4200,
      }));
    });
    $$('[data-msg-bday]', body).forEach(b => b.onclick = () => {
      this.phoneTab = 'messages';
      this.phoneThread = b.dataset.msgBday;
      $$('.phone-tab').forEach(t => t.classList.toggle('active', t.dataset.ptab === 'messages'));
      this.renderPhoneBody();
    });
  }

  async renderPhoneMessages(body) {
    if (this.phoneThread) return this.renderPhoneChat(body, this.phoneThread);
    body.innerHTML = '<div class="empty-note">Loading conversations…</div>';
    let data;
    try { data = await this.app.apiGet('/api/threads'); } catch { data = { threads: [], contacts: [] }; }
    const threads = data.threads || [];
    const contacts = (data.contacts || []).slice(0, 12);
    if (!body.isConnected) return;
    body.innerHTML = `
      ${threads.length ? `<div class="phone-section-title">Conversations</div>
      ${threads.map(t => `
        <button class="thread-row" data-thread="${t.npc_id}">
          <span class="person-avatar"><img src="${avatarUrl(t.look, 84, 'head', 'steady')}" style="width:100%;height:100%;object-fit:cover" alt=""/></span>
          <span class="thread-main"><b>${esc(t.name)}</b><span>${t.last.sender === 'player' ? 'You: ' : ''}${esc(t.last.text)}</span></span>
          <span class="thread-meta"><time>${esc(fmtClock(t.last.minute))}</time>${t.unread ? `<span class="unread-dot">${t.unread}</span>` : ''}</span>
        </button>`).join('')}` : '<div class="empty-note">No conversations yet.<br/>Talk to someone in person, then text them.</div>'}
      <div class="phone-section-title" style="margin-top:14px">Start a conversation</div>
      ${contacts.map(c => `
        <button class="thread-row" data-thread="${c.id}">
          <span class="person-avatar"><img src="${avatarUrl(c.look, 84, 'head', 'steady')}" style="width:100%;height:100%;object-fit:cover" alt=""/></span>
          <span class="thread-main"><b>${esc(c.name)}</b><span>${esc(c.label)} · ${esc(c.archetype)}</span></span>
          <span class="thread-meta">${c.can_call ? '<span class="qty-chip">callable</span>' : ''}</span>
        </button>`).join('')}`;
    $$('[data-thread]', body).forEach(b => b.onclick = () => { this.phoneThread = b.dataset.thread; this.renderPhoneBody(); });
  }

  async renderPhoneChat(body, npcId) {
    body.innerHTML = '<div class="empty-note">Opening chat…</div>';
    let data;
    try { data = await this.app.apiGet(`/api/thread/${npcId}?mark_read=1`); }
    catch (e) { body.innerHTML = `<div class="empty-note">${esc(e.message)}</div>`; return; }
    const npc = data.npc || {};
    const msgs = data.messages || [];
    if (!body.isConnected) return;
    body.innerHTML = `
      <div class="phone-chat">
        <div class="row" style="margin-bottom:8px">
          <button class="phone-back" data-back="1">← Messages</button>
          <span class="spacer"></span>
          <button class="btn tiny ${data.can_call ? 'mint' : 'ghost'}" data-callchat="1" ${data.can_call ? '' : 'disabled'}>📞 Call</button>
        </div>
        <div class="post-head" style="margin-bottom:10px">
          <span class="person-avatar"><img src="${avatarUrl(npc.look || {}, 84, 'head', 'steady')}" style="width:100%;height:100%;object-fit:cover" alt=""/></span>
          <span><b>${esc(npc.name || '')}</b><span>${esc(data.relationship?.label || '')} · familiarity ${Math.round(data.relationship?.familiarity || 0)}%</span></span>
        </div>
        <div class="chat-scroll" id="phone-chat-scroll">
          ${msgs.length ? msgs.map(m => this.phoneMessageRow(m, npc)).join('') : '<div class="empty-note">No messages yet. Say something.</div>'}
        </div>
        <div class="phone-composer">
          <input id="phone-msg-input" type="text" maxlength="320" placeholder="Message ${esc(npc.first || '')}…" />
          <button class="chat-send" id="phone-msg-send" style="width:40px;height:40px">↑</button>
        </div>
        <p class="voice-status" id="phone-msg-status">Replies arrive on game time — they may be busy, asleep, or just taking their time.</p>
      </div>`;
    const scroll = $('#phone-chat-scroll');
    this.watchConversationLog(scroll);
    if (scroll) scroll.scrollTop = scroll.scrollHeight;
    $('#phone-msg-send').onclick = () => this.sendPhoneMessage(npcId, npc);
    $('#phone-msg-input').addEventListener('keydown', e => { if (e.key === 'Enter') this.sendPhoneMessage(npcId, npc); });
    $('[data-back]', body).onclick = () => { this.phoneThread = null; this.renderPhoneBody(); };
    $('[data-callchat]', body)?.addEventListener('click', () => { this.closePhone(); this.startCall(npcId); });
  }

  phoneMessageRow(m, npc) {
    return `<div class="chat-row ${m.sender === 'player' ? 'player' : 'npc'}" data-message-id="${esc(m.id)}">
      ${m.sender !== 'player' ? `<span class="chat-avatar"><img src="${avatarUrl(npc.look || {}, 64, 'head', 'steady')}" alt=""/></span>` : ''}
      <div class="bubble">${esc(m.text)}<span class="bubble-meta">${m.sender === 'player' ? 'You' : esc(npc.first || '')} · ${esc(fmtClock(m.minute))}</span></div></div>`;
  }

  async refreshPhoneThread() {
    const npcId = this.phoneThread;
    const scroll = $('#phone-chat-scroll');
    if (!scroll || !npcId || this.phoneRefreshBusy) return;
    this.phoneRefreshBusy = true;
    try {
      const data = await this.app.apiGet(`/api/thread/${npcId}?mark_read=1`);
      if (!scroll.isConnected || this.phoneThread !== npcId || this.phoneTab !== 'messages') return;
      const atBottom = scroll.scrollHeight - scroll.scrollTop - scroll.clientHeight < 60;
      const signature = JSON.stringify(data.messages.map(m => [m.id, m.text]));
      if (scroll.dataset.messages !== signature) {
        scroll.innerHTML = data.messages.map(m => this.phoneMessageRow(m, data.npc)).join('') || '<div class="empty-note">No messages yet. Say something.</div>';
        scroll.dataset.messages = signature;
        if (atBottom) scroll.scrollTop = scroll.scrollHeight;
      }
    } catch { /* Keep drafts and focus intact during a network hiccup. */ }
    finally { this.phoneRefreshBusy = false; }
  }

  async sendPhoneMessage(npcId, npc) {
    const input = $('#phone-msg-input');
    const send = $('#phone-msg-send');
    if (!input || send?.disabled) return;
    const text = input.value.trim();
    if (!text) return;
    send.disabled = true;
    try {
      const res = await this.app.doAction('message', { npc_id: npcId, text });
      if (input.value.trim() === text) {
        input.value = '';
        this.phoneDrafts.delete(`messages:${npcId}:phone-msg-input`);
      }
      await this.refreshPhoneThread();
      const log=$('#phone-chat-scroll');
      if(log) {log.scrollTop=log.scrollHeight;requestAnimationFrame(()=>{log.scrollTop=log.scrollHeight});}
      if (input.isConnected) {
        $('#phone-msg-status').textContent = res.text;
        input.focus({ preventScroll: true });
      }
    } catch (e) { this.toast({ title: 'Message failed', body: e.message, kind: 'danger' }); }
    finally { if (send) send.disabled = false; }
  }

  async renderPhoneFeed(body) {
    body.innerHTML = '<div class="empty-note">Loading the block…</div>';
    let feed;
    try { feed = await this.app.apiGet('/api/feed'); } catch (e) { body.innerHTML = `<div class="empty-note">${esc(e.message)}</div>`; return; }
    const state = this.app.state;
    const me = state?.player;
    if (!body.isConnected) return;
    body.innerHTML = `
      <div class="composer-card">
        <textarea id="feed-composer" maxlength="280" placeholder="What's happening on your block?"></textarea>
        <div class="cc-foot"><span class="cc-count" id="feed-count">0/280</span><button class="btn tiny primary" id="feed-post">Post</button></div>
      </div>
      ${(feed.posts || []).map(p => this.postCard(p, state)).join('') || '<div class="empty-note">No posts yet.</div>'}`;
    const ta = $('#feed-composer');
    ta.addEventListener('input', () => { $('#feed-count').textContent = `${ta.value.length}/280`; });
    $('#feed-post').onclick = async () => {
      const text = ta.value.trim();
      if (!text) return;
      const button = $('#feed-post');
      if (button.disabled) return;
      button.disabled = true;
      try {
        const res = await this.app.doAction('post', { text });
        ta.value = '';
        this.phoneDrafts.delete('feed::feed-composer');
        this.toast({ title: 'Posted', body: res.text, kind: 'good' });
        await this.renderPhoneBody();
      } catch (e) { this.toast({ title: 'Can\'t post that', body: e.message, kind: 'danger' }); }
      finally { button.disabled = false; }
    };
    this.bindPostActions(body);
  }

  postCard(p, state) {
    const a = p.author_profile || {};
    const liked = (p.likes || []).includes('player');
    const time = fmtClock(p.minute);
    return `<div class="post-card">
      <div class="post-head">
        <span class="person-avatar"><img src="${avatarUrl(a.look || {}, 72, 'head', 'steady')}" style="width:100%;height:100%;object-fit:cover" alt=""/></span>
        <span><b>${esc(a.name || 'Unknown')}</b><span>${esc(time)}${p.loc ? ` · ${esc(this.locationName(p.loc))}` : ''}</span></span>
        ${p.tag ? `<span class="post-tag">#${esc(p.tag)}</span>` : ''}
      </div>
      <div class="post-text">${esc(p.text)}</div>
      <div class="post-actions">
        <button class="post-action ${liked ? 'liked' : ''}" data-like="${p.id}">${liked ? '♥' : '♡'} ${(p.likes || []).length}</button>
        <button class="post-action" data-comment-toggle="${p.id}">💬 ${(p.comments || []).length}</button>
        <span class="post-action" style="cursor:default">${p.mood ? `mood: ${esc(p.mood)}` : ''}</span>
      </div>
      ${(p.comments || []).length ? `<div class="comment-list">${p.comments.map(c => `<div class="comment"><b>${esc(c.author_profile?.name || 'Someone')}:</b> ${esc(c.text)}</div>`).join('')}</div>` : ''}
      <div class="comment-list hidden" id="cmt-${p.id}">
        <div class="row"><input class="chat-input" style="min-height:34px;padding:8px 10px" id="cmt-input-${p.id}" maxlength="160" placeholder="Add a comment…" />
        <button class="btn tiny primary" data-send-comment="${p.id}">Send</button></div>
      </div>
    </div>`;
  }

  bindPostActions(body) {
    $$('[data-like]', body).forEach(b => b.onclick = async () => {
      try { await this.app.doAction('like', { post_id: b.dataset.like }); this.renderPhoneBody(); } catch { /* noop */ }
    });
    $$('[data-comment-toggle]', body).forEach(b => b.onclick = () => {
      $(`#cmt-${b.dataset.commentToggle}`)?.classList.toggle('hidden');
    });
    $$('[data-send-comment]', body).forEach(b => b.onclick = async () => {
      const input = $(`#cmt-input-${b.dataset.sendComment}`);
      const text = input?.value.trim();
      if (!text) return;
      try { await this.app.doAction('comment', { post_id: b.dataset.sendComment, text }); this.renderPhoneBody(); }
      catch (e) { this.toast({ title: 'Comment failed', body: e.message, kind: 'danger' }); }
    });
  }

  async renderPhoneWallet(body) {
    body.innerHTML = '<div class="empty-note">Counting your BLX…</div>';
    let w;
    try { w = await this.app.apiGet('/api/ledger'); } catch (e) { body.innerHTML = `<div class="empty-note">${esc(e.message)}</div>`; return; }
    if (!body.isConnected) return;
    body.innerHTML = `
      <div class="wallet-hero">
        <div class="wh-label">Balance · closed-loop game credit</div>
        <div class="wh-amount">${fmtNum(w.wallet)} <span style="font-size:16px;color:var(--muted)">BLX</span></div>
        <div class="wh-sub">1 BLX ≈ 1 USD internal reference · not redeemable · no cash value</div>
      </div>
      <div class="row wrap" style="margin-bottom:12px">
        ${w.cart_owned ? '<span class="pill mint">🛒 Street cart open</span>' : '<span class="pill ghost">No business yet · 250 BLX at the square</span>'}
        <button class="btn tiny ghost" id="wallet-shop">🛍️ Shop</button>
      </div>
      <div class="phone-section-title">Inventory</div>
      <div class="inv-grid">
        ${(w.inventory || []).length ? w.inventory.map(i => `<div class="inv-item"><div class="ii-ico">${i.icon || '🎁'}</div><b>${esc(i.name)}</b><span>×${i.qty}</span>
          ${(this.app.world?.menu || []).some(m => m.id === i.id) ? `<button class="btn tiny ghost" data-eat="${esc(i.id)}">Eat</button>` : ''}</div>`).join('') : '<div class="empty-note" style="grid-column:1/-1">Your bag is empty.</div>'}
      </div>
      <div class="phone-section-title" style="margin-top:16px">Recent transactions</div>
      ${(w.ledger || []).length ? w.ledger.map(t => `
        <div class="ledger-row">
          <div class="lr-main"><b>${esc(t.memo)}</b><span>${esc(fmtClock(t.minute))} · ${esc(t.category)}</span></div>
          <div class="lr-amt ${t.amount >= 0 ? 'pos' : 'neg'}">${t.amount >= 0 ? '+' : ''}${fmtNum(t.amount)}</div>
        </div>`).join('') : '<div class="empty-note">No transactions yet.</div>'}
    `;
    $('#wallet-shop').onclick = () => this.openShop();
    $$('[data-eat]', body).forEach(b => b.onclick = async () => {
      try {
        const res = await this.app.doAction('use_item', { item_id: b.dataset.eat });
        this.toast({ title: 'Eaten', body: `${res.text} Energy ${Math.round(res.energy)}.`, kind: 'good' });
        this.openPhone('wallet');
      } catch (e) { this.toast({ title: 'Couldn\'t eat that', body: e.message, kind: 'danger' }); }
    });
  }

  async renderPhoneCases(body) {
    body.innerHTML = '<div class="empty-note">Opening the case files…</div>';
    let data;
    try { data = await this.app.apiGet('/api/cases'); } catch (e) { body.innerHTML = `<div class="empty-note">${esc(e.message)}</div>`; return; }
    const cases = data.cases || [];
    if (!cases.length) { body.innerHTML = '<div class="empty-note">No cases on file.<br/>The block is behaving itself. For now.</div>'; return; }
    if (!body.isConnected) return;
    body.innerHTML = cases.map(c => `
      <div class="case-card">
        <div class="cc-kicker">${c.status === 'open' ? 'Open case' : 'Closed · ' + c.status}</div>
        <h4>${esc(c.title)}</h4>
        <p>${esc(c.description)}</p>
        <div class="chip-row">
          <span class="chip">accused: ${esc(this.npc(c.accused)?.first || '?')}</span>
          <span class="chip">accuser: ${esc(this.npc(c.accuser)?.first || '?')}</span>
          <span class="chip mint">${(c.evidence || []).length} clues found</span>
        </div>
        <div class="evidence-list">
          ${(c.helpful || []).map((h, i) => {
            const loc = h.split(':')[0];
            const found = (c.evidence || []).some(e => e.startsWith(loc + ':'));
            return `<div class="evidence ${found ? 'found' : ''}"><span class="ev-mark">${found ? '✅' : '🔎'}</span><span>${esc(found ? (c.evidence || []).find(e => e.startsWith(loc + ':')) : h)}</span>
              ${!found && c.status === 'open' ? `<button class="btn tiny ghost" style="margin-left:auto" data-gocase="${loc}">Go</button>` : ''}</div>`;
          }).join('')}
        </div>
        ${c.status === 'open' && (c.evidence || []).length >= 2 ? `<button class="btn primary" data-present="${c.id}" style="width:100%">📣 Present the evidence</button>` : ''}
      </div>`).join('');
    $$('[data-gocase]', body).forEach(b => b.onclick = () => { this.closePhone(); this.walkToLocation(b.dataset.gocase); });
    $$('[data-present]', body).forEach(b => b.onclick = async () => {
      try {
        const res = await this.app.doAction('present_case', { case_id: b.dataset.present });
        this.toast({ title: 'Case closed', body: res.text, kind: 'story', ttl: 8000 });
        this.renderPhoneBody();
      } catch (e) { this.toast({ title: 'Not yet', body: e.message, kind: 'danger' }); }
    });
  }

  async renderPhoneAlerts(body) {
    const state = this.app.state;
    const notices = (state?.notices || []).slice().reverse();
    const notifs = (state?.notifications || []).slice().reverse();
    body.innerHTML = `
      <div class="row" style="margin-bottom:10px"><span class="phone-section-title" style="margin:0">Your notifications</span><span class="spacer"></span>
      <button class="btn tiny ghost" id="mark-read">Mark all read</button></div>
      ${notifs.length ? notifs.map(n => `<div class="notice-card ${n.kind === 'call' ? 'alert' : n.kind === 'story' ? 'event' : ''}">
        <div class="nc-kicker">${esc(n.kind)}</div><b>${esc(n.title)}</b><span>${esc(n.body)}</span><time>${esc(fmtClock(n.minute))}</time></div>`).join('') : '<div class="empty-note">You\'re all caught up.</div>'}
      <div class="phone-section-title" style="margin-top:16px">Neighborhood notices</div>
      ${notices.map(n => `<div class="notice-card ${n.kind}">
        <div class="nc-kicker">${esc(n.kind)}</div><b>${esc(n.title)}</b><span>${esc(n.body)}</span><time>${esc(fmtClock(n.minute))}</time></div>`).join('')}
    `;
    $('#mark-read').onclick = async () => {
      try { await this.app.doAction('dismiss_notifications', {}); this.renderPhoneBody(); } catch { /* noop */ }
    };
  }

  /* =====================================================================
     CASES / DATES
     ===================================================================== */
  openCaseFile(caseId) {
    const c = (this.app.state?.cases || []).find(x => x.id === caseId);
    if (!c) { this.toast({ title: 'Case not found', body: 'It may already be closed.', kind: 'info' }); return; }
    const body = `
      <div class="hint-note">${esc(c.description)}</div>
      <div class="chip-row">
        <span class="chip">Accused: <b>${esc(this.npc(c.accused)?.name || '?')}</b></span>
        <span class="chip">Accuser: <b>${esc(this.npc(c.accuser)?.name || '?')}</b></span>
        <span class="chip mint">${(c.evidence || []).length} clues found</span>
      </div>
      <div class="side-section-title" style="margin-top:12px">Evidence trail</div>
      <div class="evidence-list">
        ${(c.helpful || []).map(h => {
          const loc = h.split(':')[0];
          const found = (c.evidence || []).some(e => e.startsWith(loc + ':'));
          const near = this.playerNearLoc(loc, 170);
          return `<div class="evidence ${found ? 'found' : ''}">
            <span class="ev-mark">${found ? '✅' : '🔎'}</span>
            <span>${esc(found ? (c.evidence || []).find(e => e.startsWith(loc + ':')) : h)}<br/>
            <span class="muted" style="font-size:10px">${esc(this.locationName(loc))} · ${near ? 'you are here' : Math.round(this.distToLoc(loc)) + 'px away'}</span></span>
            ${!found ? `<button class="btn tiny ${near ? 'coral' : 'ghost'}" style="margin-left:auto" data-clue="${loc}">${near ? 'Investigate' : 'Go'}</button>` : ''}
          </div>`;
        }).join('')}
      </div>
      ${(c.evidence || []).length >= 2 ? '<div class="hint-note" style="border-color:rgba(127,209,185,.4)">You have enough to clear them. Present the evidence to close the case.</div>' : ''}`;
    const foot = `${(c.evidence || []).length >= 2 ? '<button class="btn primary" data-presentcase="1">📣 Present evidence</button>' : ''}
      <button class="btn ghost" data-close="1">Close</button>`;
    const m = this.modal({ title: c.title, subtitle: 'Case file · BlaxkVille', icon: '🗂️', body, foot, wide: true });
    $$('[data-close]', m).forEach(b => b.onclick = () => this.closeModal());
    $$('[data-clue]', m).forEach(b => b.onclick = () => {
      const loc = b.dataset.clue;
      if (this.playerNearLoc(loc, 170)) { this.closeModal(); this.doInvestigate(loc); }
      else { this.closeModal(); this.walkToLocation(loc); }
    });
    $$('[data-presentcase]', m).forEach(b => b.onclick = async () => {
      try {
        const res = await this.app.doAction('present_case', { case_id: c.id });
        this.toast({ title: 'Case closed', body: res.text, kind: 'story', ttl: 8000 });
        this.closeModal();
      } catch (e) { this.toast({ title: 'Not yet', body: e.message, kind: 'danger' }); }
    });
  }

  openDateOffer(offerId) {
    const d = (this.app.state?.date_offers || []).find(x => x.id === offerId);
    if (!d) { this.toast({ title: 'Date not found', body: 'The window may have closed.', kind: 'info' }); return; }
    const npc = this.npc(d.npc_id);
    const near = this.playerNearLoc(d.venue, 200);
    const body = `<div class="hint-note">${esc(npc?.first || 'They')} said yes. The date is at <b>${esc(this.locationName(d.venue))}</b> around <b>${esc(this.fmtClockShort(d.due))}</b>. Dates cost a little BLX and take about an hour of game time.</div>
      <div class="profile-hero" style="grid-template-columns:110px 1fr">
        <div class="profile-portrait"><img src="${avatarUrl(npc?.look || {}, 300, 'bust', npc?.mood)}" style="width:100%;height:100%;object-fit:cover" alt=""/></div>
        <div><div class="profile-name" style="font-size:22px">${esc(npc?.name || '')}</div>
        <div class="profile-sub">${esc(npc?.occupation || '')} · ${esc(npc?.rel?.label || '')}</div>
        <p class="profile-bio">A date can deepen romance and trust — if the vibes are right. Push too hard and they can say no.</p></div>
      </div>`;
    const foot = `<button class="btn ghost left" data-walk="1">${near ? 'I\'m here' : 'Walk there'}</button>
      <button class="btn ghost" data-close="1">Not now</button>
      <button class="btn primary" data-datego="1" ${near ? '' : 'disabled'}>Go on the date</button>`;
    const m = this.modal({ title: 'Date with ' + (npc?.first || 'someone'), subtitle: this.fmtClockShort(d.due) + ' · ' + this.locationName(d.venue), icon: '🌙', body, foot });
    $$('[data-close]', m).forEach(b => b.onclick = () => this.closeModal());
    $$('[data-walk]', m).forEach(b => b.onclick = () => { this.closeModal(); this.walkToLocation(d.venue); });
    $$('[data-datego]', m).forEach(b => b.onclick = async () => {
      try {
        const res = await this.app.doAction('date_go', { offer_id: d.id });
        this.closeModal();
        this.toast({ title: 'A good date', body: res.text, kind: 'good', ttl: 7000 });
        if (res.relationship) this.toast({ title: 'Relationship', body: `Romance ${Math.round(res.relationship.romance)} · Trust ${Math.round(res.relationship.trust)} · ${res.relationship.label}`, kind: 'info', ttl: 5000 });
        if (res.notices?.length) setTimeout(() => this.showWhileAway(res.notices), 400);
      } catch (e) { this.toast({ title: 'Date failed', body: e.message, kind: 'danger' }); }
    });
  }

  /* =====================================================================
     CALLS
     ===================================================================== */
  async startCall(npcId) {
    const npc = this.npc(npcId);
    if (!npc) return;
    try {
      const res = await this.app.doAction('call_start', { npc_id: npcId });
      this.openCallScreen({ ...npc, voice: res.voice, look: res.look }, res.greeting, res.call_id);
    } catch (e) {
      this.toast({ title: 'Call not connected', body: e.message, kind: 'danger' });
    }
  }

  openCallScreen(npc, greeting, callId) {
    this.closeModal();
    this.closePhone();
    const root = $('#call-root');
    root.classList.remove('hidden');
    this.app.music.duck(true);
    this.callSession = { npc, callId, start: Date.now(), turns: 0, muted: false };
    this.voiceCtx = { mode: 'call', npcId: npc.id, callId };
    root.innerHTML = `
      <div class="call-bg"><span class="call-orb co-a"></span><span class="call-orb co-b"></span></div>
      <div class="call-shell">
        <div class="call-top"><div class="call-status"><span class="cs-dot"></span><b>${esc(npc.name)}</b> · connected <span id="call-time" style="font-family:var(--mono)">00:00</span></div></div>
        <div class="call-portrait" id="call-portrait">
          <canvas width="480" height="480"></canvas>
          <div class="call-ripple"></div><div class="call-ripple r2"></div>
        </div>
        <div>
          <div class="call-name">${esc(npc.first)}</div>
          <div class="call-sub">${esc(npc.occupation || '')} · ${esc(npc.archetype || '')} · ${esc(npc.mood || '')}</div>
        </div>
        <div class="call-wave" id="call-wave">${'<i></i>'.repeat(7)}</div>
        <div class="call-captions" id="call-captions"></div>
        <div class="call-mic-level"><i></i></div>
      </div>
      <div class="call-controls">
        <button class="call-ctl" id="call-mic" title="Microphone">🎙️<span class="ctl-label">LISTEN</span></button>
        <button class="call-ctl" id="call-mute" title="Mute NPC voice">🔊<span class="ctl-label">SOUND</span></button>
        <button class="call-ctl hangup" id="call-end" title="End call">✕<span class="ctl-label">END</span></button>
        <button class="call-ctl" id="call-text" title="Type instead">⌨️<span class="ctl-label">TYPE</span></button>
      </div>
      <div class="call-compose hidden" id="call-compose">
        <input id="call-input-text" maxlength="280" placeholder="Type what you say — they answer out loud…" autocomplete="off"/>
        <button class="call-send-text" id="call-send-text" title="Send">↑</button>
      </div>
      <div class="call-hint">Speak naturally — you can interrupt them mid-sentence. The game receives text, not audio. Your browser may use its own speech service.</div>
    `;
    const canvas = root.querySelector('canvas');
    const ctx = canvas.getContext('2d');
    const drawLoop = () => {
      if (!this.callSession) return;
      const mood = this.npc(npc.id)?.mood || npc.mood || 'steady';
      drawAvatar(ctx, npc.look, 480, 480, { mood, bob: this.app.voice.speaking ? Math.sin(Date.now() / 140) * 3 : 0, talking: this.app.voice.speaking });
      requestAnimationFrame(drawLoop);
    };
    drawLoop();
    $('#call-mute').onclick = () => {
      this.callSession.muted = !this.callSession.muted;
      this.app.voice.stopSpeaking();
      $('#call-mute').classList.toggle('active', this.callSession.muted);
      $('#call-mute').firstChild.textContent = this.callSession.muted ? '🔇' : '🔊';
    };
    $('#call-mic').onclick = async () => {
      if (!(await this.app.ensureMicConsent())) return;
      if (this.app.voice.listening) this.app.voice.stopListening();
      else { this.app.voice.startListening(); }
    };
    $('#call-text').onclick = () => this.toggleCallComposer();
    $('#call-end').onclick = () => this.endCall();
    this.wireCallComposer();
    this.watchConversationLog($('#call-captions'));
    this.toggleCallComposer(true);
    this.callInterval = setInterval(() => {
      if (!this.callSession) return;
      const s = Math.floor((Date.now() - this.callSession.start) / 1000);
      const el = $('#call-time');
      if (el) el.textContent = `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`;
    }, 500);
    this.addCallCaption(npc.first, greeting, 'npc');
    const listenAfter = async () => {
      if (!this.callSession || this.callSession.muted) return;
      if (!this.settings.autoListen) return;
      if (!this.app.voice.micReady) return;
      if (this.app.voice.listening) return;
      this.app.voice.startListening();
    };
    this.app.voice.speak(greeting, npc, {
      startedAt: performance.now(),
      onend: () => setTimeout(listenAfter, 420),
    });
    $('#call-mic').classList.toggle('active', this.app.voice.listening);
  }

  setCallCaption(text, provisional) {
    const box = $('#call-captions');
    if (!box) return;
    let el=box.querySelector('.cap.provisional');
    if(!el){el=document.createElement('div');el.className='cap provisional';box.appendChild(el);}
    el.textContent=text;
    box.scrollTop=box.scrollHeight;
  }

  addCallCaption(who, text, className) {
    const box = $('#call-captions');
    if (!box) return;
    const el = document.createElement('div');
    el.className = `cap ${className === 'player' ? 'player' : ''}`;
    el.textContent = `${className === 'player' ? 'You' : who}: ${text}`;
    box.appendChild(el);
    while (box.children.length > 60) box.removeChild(box.firstChild);
    box.scrollTop = box.scrollHeight;
    requestAnimationFrame(()=>{if(box.isConnected)box.scrollTop=box.scrollHeight});
  }

  async sendCallTurn(text, alreadyShown=false) {
    if (!this.callSession) return;
    const session = this.callSession;
    session.queue ||= [];
    if(session.pending && session.queue.length>=5){this.toast({title:'One moment',body:'Let them finish this reply, then repeat that last line.'});return;}
    $('#call-captions .provisional')?.remove();
    if(!alreadyShown)this.addCallCaption('You', text, 'player');
    if(session.pending){session.queue.push(text);return;}
    session.pending=true;
    const send=$('#call-send-text');if(send)send.disabled=true;
    const npc = session.npc;
    try {
      const res = await this.app.doAction('call_turn', { call_id: session.callId, text });
      if (this.callSession !== session) return;
      this.callSession.turns++;
      if (!this.callSession.muted) {
        this.app.voice.speak(res.reply, npc, {
          startedAt: performance.now(),
          onend: () => {
            if (this.callSession && this.settings.autoListen) {
              setTimeout(() => { if (this.callSession) this.app.voice.startListening(); }, 300);
            }
          },
        });
      }
      this.addCallCaption(npc.first, res.reply, 'npc');
    } catch (e) {
      if(this.callSession===session)this.addCallCaption('System', e.message, 'npc');
    } finally {
      if(this.callSession===session){
        session.pending=false;
        const next=session.queue.shift();
        if(next)this.sendCallTurn(next,true);
        else if(send?.isConnected)send.disabled=false;
      }
    }
  }

  toggleCallComposer(force = null) {
    if (!this.callSession) return;
    const box = $('#call-compose');
    const input = $('#call-input-text');
    if (!box || !input) return;
    const show = force === null ? box.classList.contains('hidden') : force;
    box.classList.toggle('hidden', !show);
    $('#call-text')?.classList.toggle('active', show);
    if (show) {
      input.focus();
      if (this.app.voice.listening) this.app.voice.stopListening();
    }
  }

  wireCallComposer() {
    const input = $('#call-input-text');
    const send = $('#call-send-text');
    if (!input || !send) return;
    const fire = () => {
      const text = input.value.trim();
      if (!text || !this.callSession || this.callSession.pending) return;
      input.value = '';
      this.sendCallTurn(text);
    };
    send.onclick = fire;
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') { e.preventDefault(); fire(); }
      if (e.key === 'Escape') { e.stopPropagation(); this.toggleCallComposer(false); }
    });
  }

  async endCall() {
    if (!this.callSession) return;
    const { callId, start, turns } = this.callSession;
    const duration = Math.round((Date.now() - start) / 1000);
    this.callSession = null;
    this.app.music.duck(false);
    this.app.voice.stopSpeaking();
    this.app.voice.stopRecognition();
    clearInterval(this.callInterval);
    this.voiceCtx = null;
    $('#call-root').classList.add('hidden');
    $('#call-root').innerHTML = '';
    if (!turns) {
      await this.app.doAction('call_end', { call_id: callId, duration_s: duration }).catch(() => {});
      return;
    }
    try {
      const res = await this.app.doAction('call_end', { call_id: callId, duration_s: duration });
      this.toast({ title: 'Call ended', body: res.reply || `${duration}s call with ${res.turns || turns} turns.`, kind: 'call', ttl: 6000 });
    } catch { /* noop */ }
  }

  showIncomingCall(pending) {
    if (!pending || this.ringTimer) return;
    const npc = this.npc(pending.npc_id);
    if (!npc) return;
    const root = $('#ring-root');
    root.classList.remove('hidden');
    this.app.voice.tone('ring');
    let ticks = 0;
    this.ringTimer = setInterval(() => {
      ticks++;
      if (ticks % 5 === 0) this.app.voice.tone('ring');
      if (ticks > 26) { this.dismissRing(); }
    }, 1000);
    root.innerHTML = `
      <div class="ring-scrim"></div>
      <div class="ring-card">
        <div class="ring-avatar"><img src="${avatarUrl(npc.look, 240, 'bust', npc.mood)}" style="width:100%;height:100%;object-fit:cover" alt=""/></div>
        <h3>${esc(npc.name)}</h3>
        <p>is calling you · ${esc(npc.occupation || '')}</p>
        <div class="ring-actions">
          <button class="btn ghost" id="ring-decline">Decline</button>
          <button class="btn primary" id="ring-accept">Accept</button>
        </div>
        <div class="ring-note">Microphone is optional — you can type on the call too.</div>
      </div>`;
    $('#ring-accept').onclick = async () => {
      try {
        const res = await this.app.doAction('answer_call', { call_id: pending.call_id });
        this.dismissRing(false);
        this.openCallScreen({ ...npc, voice: res.voice, look: res.look }, res.greeting, res.call_id);
      } catch (e) {
        this.dismissRing();
        this.toast({ title: 'Call missed', body: e.message, kind: 'info' });
      }
    };
    $('#ring-decline').onclick = async () => {
      this.dismissRing();
      try { await this.app.doAction('decline_call', {}); } catch { /* noop */ }
    };
  }

  dismissRing(stopTimer = true) {
    if (stopTimer && this.ringTimer) { clearInterval(this.ringTimer); this.ringTimer = null; }
    if (!stopTimer) { clearInterval(this.ringTimer); this.ringTimer = null; }
    $('#ring-root').classList.add('hidden');
    $('#ring-root').innerHTML = '';
  }

  /* =====================================================================
     OTHER PANELS
     ===================================================================== */
  openHelp() {
    const body = `
      <div class="hint-note">You're one resident in a <b>living, single-player simulation</b>. Everyone else has their own schedule, moods, money and secrets. The block keeps moving at 1× even when you're reading this.</div>
      <div class="help-list">
        <div class="help-item"><span class="hi-ico">🚶</span><span><b>Move</b>Click the ground or use WASD / arrow keys. Click a building to see activities. Press <kbd>E</kbd> near someone to talk.</span></div>
        <div class="help-item"><span class="hi-ico">💬</span><span><b>Talk & relationships</b>Free text and quick intents are understood as greetings, jokes, compliments, flirting, apologies, gossip and more. Actions change familiarity, trust, affinity, romance and tension.</span></div>
        <div class="help-item"><span class="hi-ico">🎁</span><span><b>Gifts</b>Meaning is recipient-specific. Gifts that match hobbies and tastes land better; repeated identical gifts stop working as a shortcut.</span></div>
        <div class="help-item"><span class="hi-ico">📞</span><span><b>Calls</b>Call residents you know. Speak with the mic (browser speech recognition) or type. You can interrupt the NPC mid-sentence — that's barge-in.</span></div>
        <div class="help-item"><span class="hi-ico">🧠</span><span><b>Memory & beliefs</b>Residents remember events they witnessed or were told about. Rumors have a source and a confidence level. NPCs can be wrong; challenge a claim you know is false.</span></div>
        <div class="help-item"><span class="hi-ico">🌀</span><span><b>Cartoon chaos</b>Rivalries can escalate into non-graphic dust clouds. Nobody is hurt. People gossip, security intervenes, and there are social consequences. You can even nudge tensions — at a cost to your reputation.</span></div>
        <div class="help-item"><span class="hi-ico">🪙</span><span><b>BLX economy</b>Earn from shifts, quests and your street cart; spend on rent, food, gifts and dates. BLX is fictional and closed-loop.</span></div>
        <div class="help-item"><span class="hi-ico">🗂️</span><span><b>Stories</b>The director builds causal arcs from actual state. A false accusation can become a case file — investigate locations, present evidence, and watch opinions change.</span></div>
      </div>
      <div class="ai-note">Transparency: all residents are fictional simulations, not real people. AI characters are designed to have their own lives and to decline, disagree and leave. No manipulative dependency mechanics. Romance is adult-only (22+).</div>`;
    this.modal({ title: 'How to live here', subtitle: 'A short guide to BlaxkVille', icon: '❓', body, wide: true, foot: '<button class="btn primary" data-close="1">Got it</button>' });
    $$('[data-close]').forEach(b => b.onclick = () => this.closeModal());
  }

  openSettings() {
    const voices = (window.speechSynthesis?.getVoices() || []).filter(v => (v.lang || '').toLowerCase().startsWith('en'));
    const body = `
      <div class="settings-row"><div><b>Sound effects</b><span>UI blips, chaos whooshes, ringtone</span></div>
        <button class="switch ${this.settings.sound ? 'on' : ''}" data-toggle="sound"><i></i></button></div>
      <div class="settings-row"><div><b>Speak NPC replies in chats</b><span>Uses your browser's speech synthesis</span></div>
        <button class="switch ${this.settings.speakReplies ? 'on' : ''}" data-toggle="speakReplies"><i></i></button></div>
      <div class="settings-row"><div><b>Auto-listen on calls</b><span>Restart the mic after they finish speaking</span></div>
        <button class="switch ${this.settings.autoListen ? 'on' : ''}" data-toggle="autoListen"><i></i></button></div>
      <div class="settings-row"><div><b>Voice</b><span>System speech voice for NPCs</span></div>
        <select id="voice-select" style="max-width:190px;padding:8px;border-radius:9px;background:rgba(0,0,0,.25);border:1px solid var(--line-strong)">
          <option value="">Auto (per resident)</option>
          ${voices.map(v => `<option value="${esc(v.voiceURI)}" ${this.settings.voiceURI === v.voiceURI ? 'selected' : ''}>${esc(v.name)}</option>`).join('')}
        </select></div>
      <div class="settings-row"><div><b>Speech rate</b><span>Applies to all spoken lines</span></div>
        <div class="range-line"><input id="rate-range" type="range" min="0.7" max="1.3" step="0.05" value="${this.settings.ttsRate}" /><span id="rate-value" class="mono">${this.settings.ttsRate.toFixed(2)}×</span></div></div>
      <div class="settings-row"><div><b>Microphone</b><span>${this.settings.voiceURI ? '' : ''}The game receives text, not audio. Browser speech services may be cloud-based.</span></div>
        <button class="btn tiny ${this.app.voice.micConsent ? 'mint' : 'ghost'}" id="mic-status">${this.app.voice.micConsent ? 'Enabled' : 'Not enabled'}</button></div>
      <div class="divider"></div>
      <div class="row wrap">
        <a class="btn ghost" href="/api/save" download>⬇ Export save</a>
        <button class="btn danger" id="reset-world">⚠ Start a new world</button>
      </div>
      <div class="ai-note">BlaxkVille v0.4 · social life simulation. All residents are fictional simulations. BLX is a closed-loop fictional credit with no cash value. No audio recordings are stored, no real-money purchases exist, and local dialogue works without a key. When Gemini or another AI provider is enabled, dialogue text and character context are sent to that provider.</div>`;
    const m = this.modal({ title: 'Settings', subtitle: 'Comfort, voice and data', icon: '⚙️', body });
    $$('[data-toggle]', m).forEach(b => b.onclick = () => {
      const key = b.dataset.toggle;
      this.saveSettings({ [key]: !this.settings[key] });
      b.classList.toggle('on', this.settings[key]);
    });
    $('#voice-select', m).onchange = (e) => this.saveSettings({ voiceURI: e.target.value });
    $('#rate-range', m).oninput = (e) => {
      const val = parseFloat(e.target.value);
      $('#rate-value', m).textContent = `${val.toFixed(2)}×`;
      this.saveSettings({ ttsRate: val });
    };
    $('#mic-status', m).onclick = async () => {
      const ok = await this.app.ensureMicConsent();
      $('#mic-status', m).textContent = ok ? 'Enabled' : 'Not enabled';
      $('#mic-status', m).className = `btn tiny ${ok ? 'mint' : 'ghost'}`;
    };
    $('#reset-world', m).onclick = async () => {
      const yes = await this.confirm({
        title: 'Start a new world?', danger: true, confirmLabel: 'Erase & restart',
        body: 'This replaces the current neighborhood save on this device. Residents, memories, relationships and your wallet will reset. This cannot be undone.',
      });
      if (yes) this.app.startNewWorld();
    };
  }

  openAbout() {
    const body = `
      <div class="hint-note">BLXVERSE is a <b>living AI world</b> prototype: a single-player neighborhood simulation built around fictional AI residents, persistent memory, procedural stories, a closed-loop economy, and playful cartoon chaos.</div>
      <div class="help-list">
        <div class="help-item"><span class="hi-ico">🧠</span><span><b>Hybrid intelligence</b>The simulation owns the truth. Deterministic rules handle schedules, money and state; a dialogue composer handles conversation and intentions. No LLM ever edits wallets or world state.</span></div>
        <div class="help-item"><span class="hi-ico">🛡️</span><span><b>Comedy over cruelty</b>Slapstick is non-graphic. Conflicts produce apologies, reputations and cooling-off notices — never identity-based mobs or persecution.</span></div>
        <div class="help-item"><span class="hi-ico">🔒</span><span><b>Privacy</b>Microphone use is explicit, recorded locally only as a consent flag, and speech recognition runs in your browser. No raw audio or transcripts leave this device for storage.</span></div>
        <div class="help-item"><span class="hi-ico">🪙</span><span><b>Economy</b>1 BLX = 1 USD is an internal fictional pricing reference only. BLX is closed-loop, non-redeemable, and not a dollar-backed asset. No real-money purchases or cash-out exist.</span></div>
      </div>
      <div class="ai-note">All residents are simulated. They are not real people, and the game is not designed to replace real relationships or encourage emotional dependency. If you feel a game is affecting you negatively, step away — the block will keep living.</div>`;
    this.modal({ title: 'About BLXVERSE', subtitle: 'Version 0.1 · vertical slice', icon: '🌐', body, wide: true, foot: '<button class="btn primary" data-close="1">Close</button>' });
    $$('[data-close]').forEach(b => b.onclick = () => this.closeModal());
  }

  async openStats() {
    let s;
    try { s = await this.app.apiGet('/api/stats'); } catch (e) { this.toast({ title: 'Stats unavailable', body: e.message, kind: 'danger' }); return; }
    const tiers = s.tiers || {};
    const counts = s.counts || {};
    const voice = s.voice || {};
    const eco = s.economy || {};
    const ai = s.ai || {};
    const body = `
      <div class="metric-grid">
        <div class="metric"><span>Foreground NPCs</span><b>${tiers.foreground ?? 0}</b></div>
        <div class="metric"><span>Nearby NPCs</span><b>${tiers.nearby ?? 0}</b></div>
        <div class="metric"><span>Background NPCs</span><b>${tiers.background ?? 0}</b></div>
        <div class="metric"><span>Residents</span><b>${counts.residents ?? 0}</b></div>
        <div class="metric"><span>World events</span><b>${counts.events ?? 0}</b></div>
        <div class="metric"><span>Feed posts</span><b>${counts.posts ?? 0}</b></div>
        <div class="metric"><span>Rumor spreads</span><b>${s.metrics?.rumor_spreads ?? 0}</b></div>
        <div class="metric"><span>Cartoon scenes</span><b>${s.metrics?.chaos_scenes ?? 0}</b></div>
      </div>
      <div class="side-section-title" style="margin-top:14px">Voice latency (client-measured)</div>
      <div class="metric-grid">
        <div class="metric"><span>End → first audio p50</span><b>${voice.p50_ms ?? '—'} <small>ms</small></b></div>
        <div class="metric"><span>End → first audio p95</span><b>${voice.p95_ms ?? '—'} <small>ms</small></b></div>
        <div class="metric"><span>Target</span><b>${voice.target_ms ?? 800} <small>ms</small></b></div>
        <div class="metric"><span>Samples</span><b>${voice.samples ?? 0}</b></div>
      </div>
      <div class="ai-note">Latency is measured in your browser from final transcript to first audible NPC speech. It includes network and browser speech synthesis. If speech recognition is unavailable, you can type instead. Browser vendors may use cloud-based speech services.</div>
      <div class="side-section-title" style="margin-top:14px">Economy</div>
      <div class="metric-grid">
        <div class="metric"><span>Money supply</span><b>${fmtNum(eco.money_supply ?? 0)} <small>BLX</small></b></div>
        <div class="metric"><span>Your wallet</span><b>${fmtNum(eco.player_wallet ?? 0)} <small>BLX</small></b></div>
        <div class="metric"><span>Avg resident wallet</span><b>${fmtNum(eco.avg_npc_wallet ?? 0)}</b></div>
        <div class="metric"><span>Daily rent</span><b>${eco.rent ?? 0} <small>BLX</small></b></div>
      </div>
      <div class="ai-note">${esc(eco.note || '')}</div>
      <div class="side-section-title" style="margin-top:14px">Active storylines</div>
      ${(ai.active_arcs || []).map(a => `<div class="story-card" style="margin-bottom:8px"><div class="sc-kicker">${esc(a.kind)} · ${esc(a.stage_title || '')}</div><h4>${esc(a.title)}</h4><p>${esc(a.summary)}</p></div>`).join('') || '<div class="empty-note">No active arcs.</div>'}
      <div class="ai-note">AI policy: off-screen residents keep their schedules. Dialogue uses the offline composer unless a server-side AI key is configured. Remote LLM calls: <b>${ai.remote_llm_calls ?? 0}</b>. AI provider spend is not measured here; check your provider’s billing dashboard.</div>`;
    this.modal({ title: 'World dashboard', subtitle: 'The simulation under the hood', icon: '📊', body, wide: true, foot: '<button class="btn primary" data-close="1">Close</button>' });
    $$('[data-close]').forEach(b => b.onclick = () => this.closeModal());
  }

  async openJournal() {
    let j;
    try { j = await this.app.apiGet('/api/journal'); } catch (e) { this.toast({ title: 'Journal unavailable', body: e.message, kind: 'danger' }); return; }
    const body = `
      <div class="row wrap" style="margin-bottom:12px">
        <span class="pill amber">🪙 ${fmtNum(j.stats?.wallet ?? 0)} BLX</span>
        <span class="pill mint">⚡ ${Math.round(j.stats?.energy ?? 0)}</span>
        <span class="pill violet">✦ ${Math.round(j.stats?.reputation ?? 0)} reputation</span>
        <span class="pill ghost">${esc(j.stats?.occupation || '')}</span>
      </div>
      ${(j.upcoming || []).length ? `<div class="side-section-title">Coming up</div>
      ${j.upcoming.map(u => `<div class="upcoming-row ${u.live ? 'live' : ''}">
        <span class="up-ico">${u.icon || (u.kind === 'date' ? '🌙' : u.kind === 'birthday' ? '🎂' : '📌')}</span>
        <span class="up-main"><b>${esc(u.title)}${u.live ? ' <span class="live-dot">● live</span>' : ''}</b>
          <span>${esc(u.where || '')} · ${esc(this.fmtWhen(u.due))}${u.detail ? ` · ${esc(u.detail)}` : ''}</span></span>
        ${u.venue ? `<button class="btn tiny ghost" data-go-venue="${esc(u.venue)}">Go</button>` : ''}
      </div>`).join('')}` : ''}
      <div class="side-section-title" style="margin-top:14px">Journal</div>
      <div class="timeline">
        ${(j.journal || []).length ? j.journal.map(e => `<div class="timeline-item ${e.kind === 'date' || e.kind === 'business' || e.kind === 'case' ? 'story' : ''}">
          ${esc(e.summary)}<span class="ti-meta">Day ${e.day} · ${esc(e.kind)}</span></div>`).join('') : '<div class="empty-note">Your journal is empty. Go make something happen.</div>'}
      </div>`;
    this.modal({ title: 'Your journal', subtitle: 'What you remember from the block', icon: '📓', body });
    $$('[data-go-venue]', document).forEach(b => b.onclick = () => {
      const loc = this.loc(b.dataset.goVenue);
      this.closeModal();
      if (!loc) return;
      this.app.walkTo(loc.x + loc.w / 2, loc.y + loc.h + 52, () => this.toast({
        title: loc.name, body: `${loc.name} is right here. Step inside from the card.`, kind: 'info', ttl: 4200,
      }));
    });
  }

  openRivals() {
    const body = `<div class="empty-note">Loading rivalries…</div>`;
    const m = this.modal({ title: 'Rivalry ledger', subtitle: 'Feuds are stories too', icon: '⚔️', body });
    this.app.apiGet('/api/rivals').then(({ rivalries }) => {
      if (!rivalries?.length) {
        $('.modal-body', m).innerHTML = '<div class="empty-note">No active rivalries. The block is suspiciously peaceful.</div>';
        return;
      }
      $('.modal-body', m).innerHTML = rivalries.map(r => `
        <div class="story-card case" style="margin-bottom:9px">
          <div class="sc-kicker">${esc(r.status)} · ${r.clashes} clash${r.clashes === 1 ? '' : 'es'}</div>
          <h4>${esc(r.a_name)} vs ${esc(r.b_name)}</h4>
          <p>Cause: ${esc(r.cause)}. Tension ${Math.round(r.tension)}/100.</p>
        </div>`).join('');
    }).catch(() => { $('.modal-body', m).innerHTML = '<div class="empty-note">Could not load rivalries.</div>'; });
  }

  /* feed for sidebar / re-render after actions */
  refreshOpenPanel() {
    // Never replace a live composer. Only the message list updates in place.
    if ($('#phone-root:not(.hidden)') && this.phoneTab === 'messages' && this.phoneThread) this.refreshPhoneThread();
  }
}

function meter(label, value, max, cls, display = null, raw = false) {
  const pct = Math.max(0, Math.min(100, (value / max) * 100));
  return `<div class="rel-meter ${cls.startsWith('rm-tension') ? 'full' : ''}">
    <div class="rm-head"><span>${label}</span><b>${esc(display ?? Math.round(value))}${raw ? '' : ''}</b></div>
    <div class="rm-track"><i style="width:${pct}%"></i></div>
  </div>`;
}
function avatarImg(look, size = 96, mood = 'steady') {
  return `<img src="${avatarUrl(look || {}, size, 'bust', mood)}" alt="" style="width:100%;height:100%;object-fit:cover" />`;
}
function hashish(s) {
  let h = 0;
  for (let i = 0; i < String(s).length; i++) h = (h * 31 + String(s).charCodeAt(i)) >>> 0;
  return h;
}
