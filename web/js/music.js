/* Original, quiet procedural lounge score. No downloads, tracker or audio API.
   Browser audio starts only after a gesture and ducks under speech/calls. */
export class BackgroundMusic {
  constructor() {
    this.enabled = localStorage.getItem('blx.music') !== 'off';
    this.ducked = false;
    this.step = 0;
    document.addEventListener('visibilitychange', () => this.level());
  }
  async start() {
    if (!this.enabled) return;
    const Audio = window.AudioContext || window.webkitAudioContext;
    if (!Audio) return;
    if (!this.ctx) {
      this.ctx = new Audio();
      this.master = this.ctx.createGain();
      this.master.gain.value = 0;
      const filter = this.ctx.createBiquadFilter();
      filter.type = 'lowpass'; filter.frequency.value = 1800;
      this.master.connect(filter); filter.connect(this.ctx.destination);
      this.next = this.ctx.currentTime + .1;
      this.timer = setInterval(() => this.schedule(), 500);
    }
    await this.ctx.resume();
    this.level(); this.schedule();
  }
  level() {
    if (!this.ctx) return;
    const audible = this.enabled && !document.hidden;
    this.master.gain.setTargetAtTime(audible ? (this.ducked ? .006 : .025) : 0, this.ctx.currentTime, .35);
  }
  duck(value) { this.ducked = value; this.level(); }
  async toggle() {
    this.enabled = !this.enabled;
    localStorage.setItem('blx.music', this.enabled ? 'on' : 'off');
    if (this.enabled) await this.start();
    this.level();
  }
  note(midi, at, duration, strength = 1) {
    const oscillator = this.ctx.createOscillator();
    const gain = this.ctx.createGain();
    oscillator.type = 'sine';
    oscillator.frequency.value = 440 * 2 ** ((midi - 69) / 12);
    gain.gain.setValueAtTime(0, at);
    gain.gain.linearRampToValueAtTime(strength * .22, at + .15);
    gain.gain.exponentialRampToValueAtTime(.0001, at + duration);
    oscillator.connect(gain); gain.connect(this.master);
    oscillator.start(at); oscillator.stop(at + duration + .05);
    oscillator.onended = () => { oscillator.disconnect(); gain.disconnect(); };
  }
  schedule() {
    if (!this.enabled || document.hidden || this.ctx.state !== 'running') return;
    if (this.next < this.ctx.currentTime) this.next = this.ctx.currentTime + .1;
    const chords = [[48,55,59,64], [45,52,55,60], [41,48,52,57], [43,50,53,59]];
    const melody = [76, 74, 71, 67, 72, 71, 69, 64, 69, 72, 76, 72, 74, 71, 67, 62];
    while (this.next < this.ctx.currentTime + 1.5) {
      if (this.step % 4 === 0) for (const n of chords[Math.floor(this.step / 4) % 4]) this.note(n, this.next, 7, .7);
      this.note(melody[this.step % melody.length], this.next, 2.8, .5);
      this.step++; this.next += 2;
    }
  }
}
