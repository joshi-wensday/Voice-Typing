import { describe, expect, it } from "vitest";
import { HoldGesture, MIN_HOLD_MS } from "../src/gestures";

describe("HoldGesture", () => {
  it("hold and release records", () => {
    const g = new HoldGesture();
    expect(g.down(500, 0)).toBe("start");
    expect(g.state).toBe("holding");
    expect(g.up(MIN_HOLD_MS + 500)).toBe("stop");
    expect(g.state).toBe("processing");
    g.processingDone();
    expect(g.state).toBe("idle");
  });

  it("short tap cancels instead of recording", () => {
    const g = new HoldGesture();
    g.down(500, 0);
    expect(g.up(MIN_HOLD_MS - 1)).toBe("cancel");
    expect(g.state).toBe("idle");
  });

  it("swipe up locks; release keeps recording; tap stops", () => {
    const g = new HoldGesture();
    g.down(500, 0);
    expect(g.move(500 - 81, 100)).toBe("lock");
    expect(g.state).toBe("locked");
    expect(g.up(2000)).toBe("none"); // thumb off, still recording
    expect(g.state).toBe("locked");
    expect(g.down(500, 5000)).toBe("stop");
    expect(g.state).toBe("processing");
  });

  it("fast swipe down cancels recording and opens history", () => {
    const g = new HoldGesture();
    g.down(300, 0);
    expect(g.move(300 + 71, 150)).toBe("history");
    expect(g.state).toBe("idle");
  });

  it("slow drag down does not trigger history", () => {
    const g = new HoldGesture();
    g.down(300, 0);
    expect(g.move(300 + 71, 400)).toBe("none");
    expect(g.state).toBe("holding");
  });

  it("small movements are ignored while holding", () => {
    const g = new HoldGesture();
    g.down(300, 0);
    expect(g.move(310, 100)).toBe("none");
    expect(g.move(260, 100)).toBe("none");
    expect(g.state).toBe("holding");
  });

  it("down during processing is ignored", () => {
    const g = new HoldGesture();
    g.down(500, 0);
    g.up(1000);
    expect(g.down(500, 1100)).toBe("none");
    expect(g.state).toBe("processing");
  });

  it("full cycle twice", () => {
    const g = new HoldGesture();
    for (const t0 of [0, 10_000]) {
      expect(g.down(500, t0)).toBe("start");
      expect(g.up(t0 + 1000)).toBe("stop");
      g.processingDone();
    }
    expect(g.state).toBe("idle");
  });
});
