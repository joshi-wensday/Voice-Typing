/** IndexedDB adapter: queued jobs + their audio blobs. Audio is written here
 * the instant recording stops — a capture can never be lost to bad signal. */

import type { JobStorage, QueueJob } from "./queue";

const DB_NAME = "vype";
const JOBS = "jobs";
const BLOBS = "blobs";

function open(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, 1);
    request.onupgradeneeded = () => {
      request.result.createObjectStore(JOBS, { keyPath: "id" });
      request.result.createObjectStore(BLOBS);
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

function tx<T>(
  db: IDBDatabase,
  store: string,
  mode: IDBTransactionMode,
  fn: (s: IDBObjectStore) => IDBRequest<T>,
): Promise<T> {
  return new Promise((resolve, reject) => {
    const request = fn(db.transaction(store, mode).objectStore(store));
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

export interface StoredJob extends QueueJob {
  text?: string; // note jobs carry their text inline
  tags?: string[];
}

export class IdbJobStorage implements JobStorage {
  private db: Promise<IDBDatabase> = open();

  async all(): Promise<StoredJob[]> {
    return tx(await this.db, JOBS, "readonly", (s) => s.getAll());
  }

  async add(job: StoredJob, audio?: ArrayBuffer): Promise<void> {
    const db = await this.db;
    await tx(db, JOBS, "readwrite", (s) => s.put(job));
    if (audio) await tx(db, BLOBS, "readwrite", (s) => s.put(audio, job.id));
  }

  async audio(id: string): Promise<ArrayBuffer | undefined> {
    return tx(await this.db, BLOBS, "readonly", (s) => s.get(id));
  }

  async remove(id: string): Promise<void> {
    const db = await this.db;
    await tx(db, JOBS, "readwrite", (s) => s.delete(id));
    await tx(db, BLOBS, "readwrite", (s) => s.delete(id));
  }

  async bump(id: string): Promise<void> {
    const db = await this.db;
    const job = await tx<StoredJob>(db, JOBS, "readonly", (s) => s.get(id));
    if (job) {
      job.attempts += 1;
      await tx(db, JOBS, "readwrite", (s) => s.put(job));
    }
  }
}
