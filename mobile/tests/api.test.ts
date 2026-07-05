import { describe, expect, it } from "vitest";
import { VypeApi } from "../src/api";

const cfg = () => ({ baseUrl: "https://pc.ts.net/", token: "tok" });

function fakeFetch(status = 200, body: unknown = { text: "hi" }) {
  const calls: { url: string; init?: RequestInit }[] = [];
  const fn = (async (url: string | URL | Request, init?: RequestInit) => {
    calls.push({ url: String(url), init });
    return {
      ok: status < 400,
      status,
      json: async () => body,
    } as Response;
  }) as typeof fetch;
  return { fn, calls };
}

describe("VypeApi", () => {
  it("transcribe posts multipart wav with auth, strips trailing slash", async () => {
    const { fn, calls } = fakeFetch(200, { text: "hello world" });
    const api = new VypeApi(cfg, fn);
    const text = await api.transcribe(new ArrayBuffer(44));
    expect(text).toBe("hello world");
    expect(calls[0].url).toBe("https://pc.ts.net/v1/audio/transcriptions");
    const headers = calls[0].init?.headers as Record<string, string>;
    expect(headers.Authorization).toBe("Bearer tok");
    expect(calls[0].init?.body).toBeInstanceOf(FormData);
  });

  it("transcribe throws on server error", async () => {
    const api = new VypeApi(cfg, fakeFetch(500).fn);
    await expect(api.transcribe(new ArrayBuffer(44))).rejects.toThrow("500");
  });

  it("addNote posts json", async () => {
    const { fn, calls } = fakeFetch();
    await new VypeApi(cfg, fn).addNote("thought", ["podcast"]);
    expect(calls[0].url).toBe("https://pc.ts.net/notes");
    expect(JSON.parse(String(calls[0].init?.body))).toEqual({
      text: "thought",
      source: "app",
      tags: ["podcast"],
    });
  });

  it("health returns false on network error", async () => {
    const failing = (async () => {
      throw new Error("net down");
    }) as unknown as typeof fetch;
    expect(await new VypeApi(cfg, failing).health()).toBe(false);
  });
});
