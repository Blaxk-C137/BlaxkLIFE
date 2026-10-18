/* =========================================================================
   Voice engine
   - microphone consent + browser speech recognition (game server receives text only)
   - RMS metering used as lightweight VAD and for barge-in detection
   - streaming speech synthesis with per-resident voice profiles
   - honest client-side latency instrumentation, reported to the server
   ========================================================================= */

const RECOGNITION = window.SpeechRecognition || window.webkitSpeechRecognition;

function hashStr(s) {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); }
  return h >>> 0;
}

export class Voice {
  constructor(opts = {}) {
    this.onPartial = opts.onPartial || (() => {});
    this.onFinal = opts.onFinal || (() => {});
    this.onState = opts.onState || (() => {});
    this.onLevel = opts.onLevel || (() => {});
    this.onError = opts.onError || (() => {});
    this.onMetric = opts.onMetric || (() => {});
    this.onSpeakStart = opts.onSpeakStart || (() => {});
    this.onSpeakEnd = opts.onSpeakEnd || (() => {});
    this.onBargeIn = opts.onBargeIn || (() => {});
    this.soundEnabled = opts.soundEnabled !== false;
    this.rate = opts.rate ?? 1;
    this.voiceOverride = null;
    this.available = !!RECOGNITION;
    this.micReady = false;
    this.listening = false;
    this.speaking = false;
    this.stream = null;
    this.audioCtx = null;
    this.analyser = null;
    this.raf = null;
    this.bargeFrames = 0;
    this.lastLevel = 0;
    this.recognition = null;
    this.finalText = '';
    this.interimText = '';
    this.turnStart = 0;
    this.finalAt = 0;
    this.partialSent = false;
    this.micConsent = localStorage.getItem('blx.micConsent') === 'yes';
    this.currentUtterance = null;
    this.voices = [];
    this._loadVoices();
    if (window.speechSynthesis) {
      window.speechSynthesis.onvoiceschanged = () => this._loadVoices();
    }
  }

  _loadVoices() {
    try { this.voices = (window.speechSynthesis?.getVoices() || []).filter(v => (v.lang || '').toLowerCase().startsWith('en')); } catch { this.voices = []; }
  }

  get ttsSupported() { return typeof window.speechSynthesis !== 'undefined' && typeof window.SpeechSynthesisUtterance !== 'undefined'; }

  async requestMic() {
    if (this.micReady) return true;
    if (!navigator.mediaDevices?.getUserMedia) {
      this.onError('Microphone access is not available in this browser.');
      return false;
    }
    try {
      this.stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true, channelCount: 1 },
      });
      this.audioCtx = this.audioCtx || new (window.AudioContext || window.webkitAudioContext)();
      const src = this.audioCtx.createMediaStreamSource(this.stream);
      this.analyser = this.audioCtx.createAnalyser();
      this.analyser.fftSize = 512;
      this.analyser.smoothingTimeConstant = 0.6;
      src.connect(this.analyser);
      this.micReady = true;
      this.micConsent = true;
      localStorage.setItem('blx.micConsent', 'yes');
      this._meterLoop();
      return true;
    } catch (err) {
      this.onError('Microphone permission was blocked. You can still type instead.');
      return false;
    }
  }

  _meterLoop() {
    if (!this.analyser) return;
    const buf = new Uint8Array(this.analyser.fftSize);
    const tick = () => {
      if (!this.analyser) return;
      this.analyser.getByteTimeDomainData(buf);
      let sum = 0;
      for (let i = 0; i < buf.length; i++) {
        const v = (buf[i] - 128) / 128;
        sum += v * v;
      }
      const rms = Math.sqrt(sum / buf.length);
      this.lastLevel = rms;
      this.onLevel(rms);
      // barge-in: player speaks while NPC is talking
      if (this.speaking && rms > 0.055) {
        this.bargeFrames++;
        if (this.bargeFrames > 9) {
          this.bargeFrames = 0;
          this.stopSpeaking();
          this.onBargeIn();
        }
      } else {
        this.bargeFrames = Math.max(0, this.bargeFrames - 1);
      }
      this.raf = requestAnimationFrame(tick);
    };
    this.raf = requestAnimationFrame(tick);
  }

  startListening() {
    if (!this.available) {
      this.onError('This browser does not support speech recognition. Type your message instead.');
      return false;
    }
    this.stopRecognition();
    const rec = new RECOGNITION();
    rec.lang = 'en-US';
    rec.interimResults = true;
    rec.continuous = false;
    rec.maxAlternatives = 1;
    this.recognition = rec;
    this.finalText = '';
    this.interimText = '';
    this.partialSent = false;
    this.turnStart = performance.now();

    rec.onstart = () => {
      this.listening = true;
      this.onState({ listening: true, status: 'Listening…' });
      this.onMetric('vad_speech_start', 0);
    };
    rec.onresult = (event) => {
      let interim = '';
      let final = '';
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const res = event.results[i];
        if (res.isFinal) final += res[0].transcript;
        else interim += res[0].transcript;
      }
      if (interim) {
        this.interimText = interim.trim();
        if (!this.partialSent) {
          this.partialSent = true;
          this.onMetric('asr_first_partial', performance.now() - this.turnStart);
        }
        this.onPartial(this.interimText, false);
      }
      if (final) {
        this.finalText = final.trim();
        this.finalAt = performance.now();
        this.onMetric('asr_final', this.finalAt - this.turnStart);
        this.onPartial(this.finalText, true);
      }
    };
    rec.onerror = (e) => {
      this.listening = false;
      if (e.error === 'no-speech') this.onState({ listening: false, status: 'No speech detected — try again.' });
      else if (e.error === 'not-allowed' || e.error === 'service-not-allowed') this.onError('Microphone permission was blocked.');
      else if (e.error === 'aborted') { /* intentional */ }
      else this.onState({ listening: false, status: `Speech error: ${e.error}` });
    };
    rec.onend = () => {
      this.listening = false;
      if (this.finalText) {
        this.onState({ listening: false, status: 'Heard you.' });
        this.onFinal(this.finalText);
      } else if (this.interimText) {
        this.onState({ listening: false, status: 'I only caught part of that — say it once more.' });
      } else {
        this.onState({ listening: false, status: '' });
      }
    };
    try { rec.start(); return true; } catch { return false; }
  }

  stopRecognition() {
    if (this.recognition) {
      try { this.recognition.onend = null; this.recognition.abort(); } catch { /* noop */ }
      this.recognition = null;
    }
    this.listening = false;
  }

  stopListening() {
    if (this.recognition) {
      try { this.recognition.stop(); } catch { /* noop */ }
    }
  }

  pickVoice(name = '') {
    if (this.voiceOverride) return this.voiceOverride;
    if (!this.voices.length) return null;
    return this.voices[hashStr(name) % this.voices.length];
  }

  speak(text, npc = {}, opts = {}) {
    if (!this.ttsSupported || !text) { opts.onend?.(); return; }
    this.stopSpeaking();
    const u = new SpeechSynthesisUtterance(text);
    const v = this.pickVoice(npc.name || npc.first || '');
    if (v) u.voice = v;
    u.rate = Math.max(0.7, Math.min(1.25, (npc.voice?.rate || 1) * this.rate));
    u.pitch = Math.max(0.6, Math.min(1.5, npc.voice?.pitch || 1));
    u.volume = 1;
    u.onstart = () => {
      this.speaking = true;
      this._spokenAt = performance.now();
      if (this.finalAt) {
        const e2e = performance.now() - this.finalAt;
        this.onMetric('e2e_first_audio', e2e, { npc: npc.id || '' });
      }
      this.onMetric('tts_first_audio', performance.now() - (opts.startedAt || this.turnStart));
      this.onSpeakStart();
      opts.onstart?.();
    };
    u.onend = () => {
      this.speaking = false;
      this.onSpeakEnd();
      opts.onend?.();
    };
    u.onerror = () => {
      this.speaking = false;
      this.onSpeakEnd();
      opts.onend?.();
    };
    this.currentUtterance = u;
    this.onSpeakStart();
    window.speechSynthesis.speak(u);
  }

  stopSpeaking() {
    if (this.ttsSupported) {
      try { window.speechSynthesis.cancel(); } catch { /* noop */ }
    }
    if (this.speaking) this.onSpeakEnd();
    this.speaking = false;
  }

  /* simple synthesized SFX — no audio files needed */
  tone(kind = 'click') {
    if (!this.soundEnabled) return;
    try {
      if (!this.audioCtx) this.audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      const ctx = this.audioCtx;
      if (ctx.state === 'suspended') ctx.resume();
      const now = ctx.currentTime;
      const o = ctx.createOscillator();
      const g = ctx.createGain();
      o.connect(g); g.connect(ctx.destination);
      const presets = {
        click: { f: 620, t: 0.05, type: 'sine', vol: 0.05 },
        open: { f: 420, t: 0.12, type: 'triangle', vol: 0.06 },
        good: { f: 740, t: 0.16, type: 'sine', vol: 0.07 },
        bad: { f: 180, t: 0.18, type: 'sawtooth', vol: 0.05 },
        chaos: { f: 240, t: 0.5, type: 'square', vol: 0.055, slide: 620 },
        ring: { f: 520, t: 0.5, type: 'sine', vol: 0.08, slide: 380 },
      };
      const p = presets[kind] || presets.click;
      o.type = p.type;
      o.frequency.setValueAtTime(p.f, now);
      if (p.slide) o.frequency.exponentialRampToValueAtTime(p.slide, now + p.t);
      g.gain.setValueAtTime(p.vol, now);
      g.gain.exponentialRampToValueAtTime(0.0001, now + p.t + 0.05);
      o.start(now);
      o.stop(now + p.t + 0.06);
    } catch { /* noop */ }
  }

  get micAvailable() { return !!RECOGNITION; }
}
