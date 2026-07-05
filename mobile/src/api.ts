/** Server client — speaks the OpenAI-compatible transcription API plus the
 * vype notes inbox. `fetch` is injected for tests. */

export interface ApiConfig {
  baseUrl: string; // e.g. https://pc.tailnet.ts.net
  token: string;
}

export class VypeApi {
  constructor(
    private cfg: () => ApiConfig,
    private fetchFn: typeof fetch = fetch,
  ) {}

  private headers(): Record<string, string> {
    return { Authorization: `Bearer ${this.cfg().token}` };
  }

  private url(path: string): string {
    return this.cfg().baseUrl.replace(/\/+$/, "") + path;
  }

  async transcribe(wav: ArrayBuffer): Promise<string> {
    const form = new FormData();
    form.append("file", new Blob([wav], { type: "audio/wav" }), "clip.wav");
    const response = await this.fetchFn(this.url("/v1/audio/transcriptions"), {
      method: "POST",
      headers: this.headers(),
      body: form,
    });
    if (!response.ok) throw new Error(`transcribe failed: ${response.status}`);
    const data = (await response.json()) as { text: string };
    return data.text;
  }

  async addNote(text: string, tags: string[] = []): Promise<void> {
    const response = await this.fetchFn(this.url("/notes"), {
      method: "POST",
      headers: { ...this.headers(), "Content-Type": "application/json" },
      body: JSON.stringify({ text, source: "app", tags }),
    });
    if (!response.ok) throw new Error(`note sync failed: ${response.status}`);
  }

  async health(): Promise<boolean> {
    try {
      const response = await this.fetchFn(this.url("/health"));
      return response.ok;
    } catch {
      return false;
    }
  }
}
