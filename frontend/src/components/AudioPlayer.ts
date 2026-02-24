export class AudioPlayer {
  private ctx: AudioContext | null = null;
  private queue: AudioBuffer[] = [];
  private playing = false;
  private currentSource: AudioBufferSourceNode | null = null;
  enabled = true;

  private getContext(): AudioContext {
    if (!this.ctx) {
      this.ctx = new AudioContext();
    }
    return this.ctx;
  }

  async addChunk(base64: string) {
    if (!this.enabled) return;
    try {
      const ctx = this.getContext();
      const binary = atob(base64);
      const bytes = new Uint8Array(binary.length);
      for (let i = 0; i < binary.length; i++) {
        bytes[i] = binary.charCodeAt(i);
      }
      const buffer = await ctx.decodeAudioData(bytes.buffer.slice(0) as ArrayBuffer);
      this.queue.push(buffer);
      if (!this.playing) this.playNext();
    } catch (err) {
      console.error('AudioPlayer: failed to decode chunk', err);
    }
  }

  private playNext() {
    if (!this.queue.length) {
      this.playing = false;
      this.currentSource = null;
      return;
    }
    this.playing = true;
    const ctx = this.getContext();
    const buffer = this.queue.shift()!;
    const source = ctx.createBufferSource();
    source.buffer = buffer;
    source.connect(ctx.destination);
    source.onended = () => {
      this.currentSource = null;
      this.playNext();
    };
    this.currentSource = source;
    source.start();
  }

  /** Interrupt: stop current playback and clear queue */
  interrupt() {
    this.queue = [];
    if (this.currentSource) {
      try { this.currentSource.stop(); } catch { /* already stopped */ }
      this.currentSource = null;
    }
    this.playing = false;
  }

  stop() {
    this.interrupt();
  }

  dispose() {
    this.stop();
    if (this.ctx) {
      this.ctx.close();
      this.ctx = null;
    }
  }
}
