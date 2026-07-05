/** Hold-to-talk gesture state machine — pure logic, mirrors the desktop FSM.
 *
 * down            → start recording immediately (no capture latency)
 * swipe down fast → it was a history gesture: cancel the recording, open history
 * swipe up (held) → lock hands-free (release no longer stops)
 * up (holding)    → stop & process; taps shorter than MIN_HOLD_MS cancel
 * down (locked)   → stop & process (tap to stop)
 */

export type GestureAction =
  | "start"
  | "stop"
  | "lock"
  | "cancel"
  | "history"
  | "none";

export type GestureState = "idle" | "holding" | "locked" | "processing";

export const LOCK_SWIPE_PX = 80;
export const HISTORY_SWIPE_PX = 70;
export const HISTORY_WINDOW_MS = 300;
export const MIN_HOLD_MS = 250;

export class HoldGesture {
  state: GestureState = "idle";
  private downAt = 0;
  private downY = 0;

  down(y: number, t: number): GestureAction {
    if (this.state === "idle") {
      this.state = "holding";
      this.downAt = t;
      this.downY = y;
      return "start";
    }
    if (this.state === "locked") {
      this.state = "processing";
      return "stop";
    }
    return "none";
  }

  move(y: number, t: number): GestureAction {
    if (this.state !== "holding") return "none";
    const dy = y - this.downY;
    if (dy > HISTORY_SWIPE_PX && t - this.downAt <= HISTORY_WINDOW_MS) {
      this.state = "idle";
      return "history"; // caller cancels the just-started recording
    }
    if (dy < -LOCK_SWIPE_PX) {
      this.state = "locked";
      return "lock";
    }
    return "none";
  }

  up(t: number): GestureAction {
    if (this.state !== "holding") return "none"; // locked keeps recording
    if (t - this.downAt < MIN_HOLD_MS) {
      this.state = "idle";
      return "cancel";
    }
    this.state = "processing";
    return "stop";
  }

  processingDone(): void {
    if (this.state === "processing") this.state = "idle";
  }
}
