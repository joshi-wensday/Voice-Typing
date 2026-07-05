/** Local persistence: expiring recents + durable notes + upload queue records.
 *
 * Storage is injected (localStorage in the app, a Map in tests). Audio blobs
 * for the upload queue live in IndexedDB via idb.ts; this module holds the
 * pure bookkeeping.
 */

export interface KV {
  get(key: string): string | null;
  set(key: string, value: string): void;
}

export interface Recent {
  id: string;
  ts: number;
  text: string | null; // null = transcription still pending
  status: "pending" | "done" | "failed";
}

export interface Note {
  id: string;
  ts: number;
  text: string;
  tags: string[];
  synced: boolean;
}

export const RECENTS_TTL_MS = 48 * 3600 * 1000;

export class Store {
  constructor(private kv: KV) {}

  private read<T>(key: string): T[] {
    const raw = this.kv.get(key);
    return raw ? (JSON.parse(raw) as T[]) : [];
  }

  private write<T>(key: string, items: T[]): void {
    this.kv.set(key, JSON.stringify(items));
  }

  // ── Recents (auto-expire) ──────────────────────────────────────────────────

  recents(now: number): Recent[] {
    const alive = this.read<Recent>("recents").filter(
      (r) => now - r.ts < RECENTS_TTL_MS,
    );
    this.write("recents", alive);
    return alive.sort((a, b) => b.ts - a.ts);
  }

  addRecent(recent: Recent): void {
    this.write("recents", [...this.read<Recent>("recents"), recent]);
  }

  updateRecent(id: string, patch: Partial<Recent>): void {
    this.write(
      "recents",
      this.read<Recent>("recents").map((r) => (r.id === id ? { ...r, ...patch } : r)),
    );
  }

  deleteRecent(id: string): void {
    this.write("recents", this.read<Recent>("recents").filter((r) => r.id !== id));
  }

  // ── Notes (durable) ────────────────────────────────────────────────────────

  notes(): Note[] {
    return this.read<Note>("notes").sort((a, b) => b.ts - a.ts);
  }

  addNote(note: Note): void {
    this.write("notes", [...this.read<Note>("notes"), note]);
  }

  markNoteSynced(id: string): void {
    this.write(
      "notes",
      this.read<Note>("notes").map((n) => (n.id === id ? { ...n, synced: true } : n)),
    );
  }

  deleteNote(id: string): void {
    this.write("notes", this.read<Note>("notes").filter((n) => n.id !== id));
  }
}
