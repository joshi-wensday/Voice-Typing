import { describe, expect, it } from "vitest";
import { MAX_ATTEMPTS, UploadQueue, type JobStorage, type QueueJob } from "../src/queue";

function memStorage(jobs: QueueJob[]): JobStorage & { jobs: QueueJob[] } {
  const state = { jobs: [...jobs] };
  return {
    get jobs() {
      return state.jobs;
    },
    async all() {
      return [...state.jobs];
    },
    async remove(id) {
      state.jobs = state.jobs.filter((j) => j.id !== id);
    },
    async bump(id) {
      state.jobs = state.jobs.map((j) =>
        j.id === id ? { ...j, attempts: j.attempts + 1 } : j,
      );
    },
  };
}

const job = (id: string, createdAt = 0, attempts = 0): QueueJob => ({
  id,
  kind: "transcribe",
  createdAt,
  attempts,
});

describe("UploadQueue", () => {
  it("runs jobs oldest-first and removes on success", async () => {
    const storage = memStorage([job("b", 200), job("a", 100)]);
    const ran: string[] = [];
    const q = new UploadQueue(storage, async (j) => {
      ran.push(j.id);
    });
    const result = await q.flush();
    expect(ran).toEqual(["a", "b"]);
    expect(result).toEqual({ done: 2, remaining: 0 });
  });

  it("stops the batch on first failure and bumps attempts", async () => {
    const storage = memStorage([job("a", 100), job("b", 200)]);
    const q = new UploadQueue(storage, async () => {
      throw new Error("server unreachable");
    });
    const result = await q.flush();
    expect(result.done).toBe(0);
    expect(result.remaining).toBe(2);
    expect(storage.jobs.find((j) => j.id === "a")?.attempts).toBe(1);
    expect(storage.jobs.find((j) => j.id === "b")?.attempts).toBe(0); // not hammered
  });

  it("drops poison jobs at MAX_ATTEMPTS", async () => {
    const storage = memStorage([job("bad", 100, MAX_ATTEMPTS), job("ok", 200)]);
    const ran: string[] = [];
    const q = new UploadQueue(storage, async (j) => {
      ran.push(j.id);
    });
    await q.flush();
    expect(ran).toEqual(["ok"]);
    expect(storage.jobs).toEqual([]);
  });

  it("succeeds on retry after connectivity returns", async () => {
    const storage = memStorage([job("a", 100)]);
    let online = false;
    const q = new UploadQueue(storage, async () => {
      if (!online) throw new Error("offline");
    });
    await q.flush();
    expect(storage.jobs).toHaveLength(1);
    online = true;
    const result = await q.flush();
    expect(result).toEqual({ done: 1, remaining: 0 });
  });
});
