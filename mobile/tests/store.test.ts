import { describe, expect, it } from "vitest";
import { RECENTS_TTL_MS, Store, type KV } from "../src/store";

function memKV(): KV {
  const m = new Map<string, string>();
  return { get: (k) => m.get(k) ?? null, set: (k, v) => m.set(k, v) };
}

const recent = (id: string, ts: number) => ({
  id,
  ts,
  text: `text-${id}`,
  status: "done" as const,
});

describe("recents", () => {
  it("newest first", () => {
    const s = new Store(memKV());
    s.addRecent(recent("a", 1000));
    s.addRecent(recent("b", 2000));
    expect(s.recents(3000).map((r) => r.id)).toEqual(["b", "a"]);
  });

  it("expire after 48h", () => {
    const s = new Store(memKV());
    s.addRecent(recent("old", 0));
    s.addRecent(recent("fresh", RECENTS_TTL_MS / 2));
    expect(s.recents(RECENTS_TTL_MS + 1).map((r) => r.id)).toEqual(["fresh"]);
  });

  it("update patches pending transcription", () => {
    const s = new Store(memKV());
    s.addRecent({ id: "x", ts: 100, text: null, status: "pending" });
    s.updateRecent("x", { text: "hello", status: "done" });
    expect(s.recents(200)[0]).toMatchObject({ text: "hello", status: "done" });
  });

  it("delete", () => {
    const s = new Store(memKV());
    s.addRecent(recent("x", 100));
    s.deleteRecent("x");
    expect(s.recents(200)).toEqual([]);
  });
});

describe("notes", () => {
  it("persist, newest first, no expiry", () => {
    const s = new Store(memKV());
    s.addNote({ id: "n1", ts: 1, text: "one", tags: [], synced: false });
    s.addNote({ id: "n2", ts: 2, text: "two", tags: ["podcast"], synced: false });
    const notes = s.notes();
    expect(notes.map((n) => n.id)).toEqual(["n2", "n1"]);
  });

  it("mark synced", () => {
    const s = new Store(memKV());
    s.addNote({ id: "n1", ts: 1, text: "one", tags: [], synced: false });
    s.markNoteSynced("n1");
    expect(s.notes()[0].synced).toBe(true);
  });

  it("delete", () => {
    const s = new Store(memKV());
    s.addNote({ id: "n1", ts: 1, text: "one", tags: [], synced: false });
    s.deleteNote("n1");
    expect(s.notes()).toEqual([]);
  });
});
