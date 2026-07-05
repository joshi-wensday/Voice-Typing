/** WebAudio microphone capture (thin edge, exercised on-device).
 *
 * ScriptProcessorNode is deprecated but is the path that works reliably on
 * iOS 16 Safari (the iPhone 8 ceiling). Revisit AudioWorklet after upgrade.
 */

export class Recorder {
  private ctx: AudioContext | null = null;
  private stream: MediaStream | null = null;
  private processor: ScriptProcessorNode | null = null;
  private chunks: Float32Array[] = [];
  level = 0;

  get isRecording(): boolean {
    return this.ctx !== null;
  }

  async start(): Promise<void> {
    if (this.ctx) return;
    this.stream = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: true, noiseSuppression: true },
    });
    this.chunks = [];
    this.ctx = new AudioContext();
    const source = this.ctx.createMediaStreamSource(this.stream);
    this.processor = this.ctx.createScriptProcessor(4096, 1, 1);
    this.processor.onaudioprocess = (e) => {
      const data = e.inputBuffer.getChannelData(0);
      this.chunks.push(new Float32Array(data));
      let sum = 0;
      for (let i = 0; i < data.length; i++) sum += data[i] * data[i];
      const rms = Math.sqrt(sum / data.length);
      this.level = 0.6 * Math.min(1, Math.sqrt(rms / 0.08)) + 0.4 * this.level;
    };
    source.connect(this.processor);
    this.processor.connect(this.ctx.destination); // required on iOS to run
  }

  /** Stop and return (samples, sampleRate). Empty array if never started. */
  async stop(): Promise<{ samples: Float32Array; sampleRate: number }> {
    const rate = this.ctx?.sampleRate ?? 48000;
    this.processor?.disconnect();
    this.stream?.getTracks().forEach((t) => t.stop());
    await this.ctx?.close();
    this.ctx = null;
    this.stream = null;
    this.processor = null;
    this.level = 0;

    const total = this.chunks.reduce((n, c) => n + c.length, 0);
    const samples = new Float32Array(total);
    let offset = 0;
    for (const chunk of this.chunks) {
      samples.set(chunk, offset);
      offset += chunk.length;
    }
    this.chunks = [];
    return { samples, sampleRate: rate };
  }
}
