/** Offline resilience: work that failed (no signal, PC asleep) is retried when
 * connectivity returns. Event-driven — `flush()` is called from `online` /
 * `visibilitychange` events and after each capture; there is NO polling loop,
 * so an offline phone in a pocket costs zero battery.
 */

export interface QueueJob {
  id: string;
  kind: "transcribe" | "note";
  createdAt: number;
  attempts: number;
}

export interface JobStorage {
  all(): Promise<QueueJob[]>;
  remove(id: string): Promise<void>;
  bump(id: string): Promise<void>; // attempts += 1
}

export type JobRunner = (job: QueueJob) => Promise<void>;

export const MAX_ATTEMPTS = 20;

export class UploadQueue {
  private flushing = false;

  constructor(
    private storage: JobStorage,
    private run: JobRunner,
  ) {}

  /** Try every queued job once, oldest first. Safe to call repeatedly. */
  async flush(): Promise<{ done: number; remaining: number }> {
    if (this.flushing) return { done: 0, remaining: (await this.storage.all()).length };
    this.flushing = true;
    let done = 0;
    try {
      const jobs = (await this.storage.all()).sort((a, b) => a.createdAt - b.createdAt);
      for (const job of jobs) {
        if (job.attempts >= MAX_ATTEMPTS) {
          await this.storage.remove(job.id); // poison job — audio stays in store
          continue;
        }
        try {
          await this.run(job);
          await this.storage.remove(job.id);
          done += 1;
        } catch {
          await this.storage.bump(job.id);
          break; // server unreachable — stop hammering, wait for next event
        }
      }
    } finally {
      this.flushing = false;
    }
    return { done, remaining: (await this.storage.all()).length };
  }
}
