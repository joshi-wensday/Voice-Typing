import { describe, expect, it } from "vitest";
import { downsample, encodeWav } from "../src/wav";

describe("downsample", () => {
  it("48k -> 16k reduces length 3x", () => {
    const input = new Float32Array(48000).fill(0.5);
    const out = downsample(input, 48000);
    expect(out.length).toBe(16000);
    expect(out[0]).toBeCloseTo(0.5);
    expect(out[out.length - 1]).toBeCloseTo(0.5);
  });

  it("44.1k -> 16k interpolates", () => {
    const input = Float32Array.from({ length: 44100 }, (_, i) => i / 44100);
    const out = downsample(input, 44100);
    expect(out.length).toBe(16000);
    // linear ramp should stay a linear ramp
    expect(out[8000]).toBeCloseTo(0.5, 2);
  });

  it("16k passthrough", () => {
    const input = new Float32Array([0.1, 0.2]);
    expect(downsample(input, 16000)).toBe(input);
  });

  it("refuses to upsample", () => {
    expect(() => downsample(new Float32Array(10), 8000)).toThrow();
  });
});

describe("encodeWav", () => {
  it("produces a valid 16 kHz mono PCM-16 header", () => {
    const buf = encodeWav(new Float32Array(16000), 16000);
    const view = new DataView(buf);
    const tag = (o: number, n: number) =>
      String.fromCharCode(...new Uint8Array(buf, o, n));
    expect(tag(0, 4)).toBe("RIFF");
    expect(tag(8, 4)).toBe("WAVE");
    expect(view.getUint16(20, true)).toBe(1); // PCM
    expect(view.getUint16(22, true)).toBe(1); // mono
    expect(view.getUint32(24, true)).toBe(16000);
    expect(view.getUint16(34, true)).toBe(16); // bits
    expect(view.getUint32(40, true)).toBe(32000); // data bytes = samples*2
    expect(buf.byteLength).toBe(44 + 32000);
  });

  it("encodes samples as little-endian int16 with clipping", () => {
    const buf = encodeWav(new Float32Array([0, 0.5, -0.5, 2, -2]), 16000);
    const view = new DataView(buf);
    expect(view.getInt16(44, true)).toBe(0);
    expect(view.getInt16(46, true)).toBe(Math.round(0.5 * 32767));
    // JS Math.round rounds -16383.5 toward +inf → -16383
    expect(view.getInt16(48, true)).toBe(Math.round(-0.5 * 32767));
    expect(view.getInt16(50, true)).toBe(32767); // clipped
    expect(view.getInt16(52, true)).toBe(-32767);
  });
});
