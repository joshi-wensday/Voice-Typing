/** UI wiring — everything interesting lives in the tested modules. */

import { VypeApi, type ApiConfig } from "./api";
import { HoldGesture } from "./gestures";
import { IdbJobStorage, type StoredJob } from "./idb";
import { AuthError, UploadQueue } from "./queue";
import { Recorder } from "./recorder";
import { Store, type Recent } from "./store";
import { downsample, encodeWav } from "./wav";

// ── Composition ──────────────────────────────────────────────────────────────

const store = new Store({
  get: (k) => localStorage.getItem(k),
  set: (k, v) => localStorage.setItem(k, v),
});
const storage = new IdbJobStorage();
const recorder = new Recorder();
const gesture = new HoldGesture();

// the PWA is normally served BY the vype server, so its own origin is the
// right default — the URL field only matters for separately-hosted builds
const apiConfig = (): ApiConfig => ({
  baseUrl: localStorage.getItem("serverUrl") || location.origin,
  token: localStorage.getItem("apiToken") ?? "",
});
const api = new VypeApi(apiConfig);

const queue = new UploadQueue(storage, async (job) => {
  const stored = job as StoredJob;
  try {
    if (job.kind === "transcribe") {
      const audio = await storage.audio(job.id);
      if (!audio) return;
      const text = await api.transcribe(audio);
      store.updateRecent(job.id, { text: text || "(silence)", status: "done" });
      renderList();
    } else if (stored.text) {
      await api.addNote(stored.text, stored.tags ?? []);
      store.markNoteSynced(job.id);
    }
  } catch (err) {
    if (err instanceof Error && err.message.includes("401")) {
      status.textContent = "wrong API token — fix it in ⚙";
      throw new AuthError();
    }
    throw err;
  }
});

const flush = () => queue.flush().then(() => renderList());
window.addEventListener("online", flush);
document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "visible") flush();
});

// ── Elements ─────────────────────────────────────────────────────────────────

const $ = (id: string) => document.getElementById(id)!;
const surface = $("surface");
const status = $("status");
const timer = $("timer");
const history = $("history");
const list = $("list");

let tab: "recents" | "notes" = "recents";
let recordStart = 0;
let timerHandle: number | undefined;

// ── Capture flow ─────────────────────────────────────────────────────────────

function setSurface(cls: string, text: string) {
  surface.className = cls;
  status.textContent = text;
}

async function startCapture() {
  try {
    await recorder.start();
    recordStart = Date.now();
    setSurface("recording", "listening…");
    timerHandle = window.setInterval(() => {
      const s = Math.floor((Date.now() - recordStart) / 1000);
      timer.textContent = `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
    }, 500);
  } catch {
    setSurface("", "microphone unavailable");
    gesture.processingDone();
  }
}

async function stopCapture(discard = false) {
  window.clearInterval(timerHandle);
  timer.textContent = "";
  const { samples, sampleRate } = await recorder.stop();

  if (discard || samples.length < sampleRate * 0.3) {
    setSurface("", "hold to talk");
    gesture.processingDone();
    return;
  }

  setSurface("processing", "transcribing…");
  const wav = encodeWav(downsample(samples, sampleRate));
  const id = crypto.randomUUID();
  const recent: Recent = { id, ts: Date.now(), text: null, status: "pending" };
  store.addRecent(recent);
  // audio is safe on disk before we ever touch the network
  await storage.add({ id, kind: "transcribe", createdAt: Date.now(), attempts: 0 }, wav);

  try {
    const text = await api.transcribe(wav);
    store.updateRecent(id, { text: text || "(silence)", status: "done" });
    await storage.remove(id);
    setSurface("", "hold to talk");
    openHistory();
  } catch {
    setSurface("", "queued — will retry when online");
  }
  gesture.processingDone();
  renderList();
}

// ── Gestures on the capture surface ──────────────────────────────────────────

surface.addEventListener("pointerdown", (e) => {
  const action = gesture.down(e.clientY, performance.now());
  if (action === "start") startCapture();
  if (action === "stop") stopCapture();
});

surface.addEventListener("pointermove", (e) => {
  const action = gesture.move(e.clientY, performance.now());
  if (action === "lock") setSurface("locked", "locked — tap to stop");
  if (action === "history") {
    stopCapture(true);
    openHistory();
  }
});

surface.addEventListener("pointerup", (e) => {
  const action = gesture.up(performance.now());
  if (action === "stop") stopCapture();
  if (action === "cancel") stopCapture(true);
});

// ── History drawer ───────────────────────────────────────────────────────────

function openHistory() {
  history.classList.remove("hidden");
  renderList();
}

$("close-history").addEventListener("click", () => history.classList.add("hidden"));
$("tab-recents").addEventListener("click", () => switchTab("recents"));
$("tab-notes").addEventListener("click", () => switchTab("notes"));

function switchTab(t: "recents" | "notes") {
  tab = t;
  $("tab-recents").classList.toggle("active", t === "recents");
  $("tab-notes").classList.toggle("active", t === "notes");
  renderList();
}

function renderList() {
  if (history.classList.contains("hidden")) return;
  list.innerHTML = "";
  const items = tab === "recents" ? store.recents(Date.now()) : store.notes();
  if (!items.length) {
    list.innerHTML = `<div class="empty">nothing here yet</div>`;
    return;
  }
  for (const item of items) list.appendChild(card(item));
}

function card(item: Recent | { id: string; ts: number; text: string; synced?: boolean }) {
  const el = document.createElement("div");
  const pending = "status" in item && item.status === "pending";
  el.className = `card${pending ? " pending" : ""}`;
  const when = new Date(item.ts).toLocaleString([], {
    month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
  });
  const badge =
    "synced" in item ? `<span class="badge">${item.synced ? "synced" : "local"}</span>` : "";
  el.innerHTML = `
    <div class="text">${escapeHtml(item.text ?? "queued for transcription…")}</div>
    <div class="meta">${when}${badge}</div>
    <button class="del" aria-label="Delete">✕</button>`;

  el.querySelector(".del")!.addEventListener("click", (e) => {
    e.stopPropagation();
    tab === "recents" ? store.deleteRecent(item.id) : store.deleteNote(item.id);
    storage.remove(item.id);
    renderList();
  });

  // swipe right = copy (blink), swipe left = save as note; tap = copy
  let startX = 0;
  el.addEventListener("pointerdown", (e) => (startX = e.clientX));
  el.addEventListener("pointerup", async (e) => {
    const dx = e.clientX - startX;
    if (!item.text) return;
    if (dx < -60 && tab === "recents") {
      const id = crypto.randomUUID();
      store.addNote({ id, ts: Date.now(), text: item.text, tags: [], synced: false });
      await storage.add({ id, kind: "note", createdAt: Date.now(), attempts: 0, text: item.text } as StoredJob);
      flush();
      blink(el);
    } else if (Math.abs(dx) < 10 || dx > 60) {
      await navigator.clipboard.writeText(item.text);
      blink(el);
    }
  });
  return el;
}

function blink(el: HTMLElement) {
  el.classList.add("blink");
  setTimeout(() => el.classList.remove("blink"), 140);
  setTimeout(() => el.classList.add("blink"), 260);
  setTimeout(() => el.classList.remove("blink"), 420);
}

function escapeHtml(s: string): string {
  return s.replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`);
}

// ── Settings ─────────────────────────────────────────────────────────────────

const settings = $("settings") as HTMLDialogElement;
$("settings-btn").addEventListener("click", () => {
  ($("cfg-url") as HTMLInputElement).value = localStorage.getItem("serverUrl") ?? "";
  ($("cfg-token") as HTMLInputElement).value = localStorage.getItem("apiToken") ?? "";
  $("cfg-status").textContent = "";
  settings.showModal();
});
$("cfg-cancel").addEventListener("click", () => settings.close());
$("cfg-save").addEventListener("click", () => {
  localStorage.setItem("serverUrl", ($("cfg-url") as HTMLInputElement).value.trim());
  localStorage.setItem("apiToken", ($("cfg-token") as HTMLInputElement).value.trim());
  settings.close();
  flush();
});
$("cfg-test").addEventListener("click", async () => {
  const probe = new VypeApi(() => ({
    baseUrl: ($("cfg-url") as HTMLInputElement).value.trim() || location.origin,
    token: ($("cfg-token") as HTMLInputElement).value.trim(),
  }));
  $("cfg-status").textContent = "testing…";
  const result = await probe.checkAuth(); // validates the TOKEN, not just reachability
  $("cfg-status").textContent =
    result === "ok" ? "✓ connected" : result === "bad-token" ? "✗ wrong token" : "✗ unreachable";
});

// ── Boot ─────────────────────────────────────────────────────────────────────

if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("./sw.js").catch(() => {});
}
// one-tap setup: /#token=XXXX stores the token and cleans the URL
const hashToken = new URLSearchParams(location.hash.slice(1)).get("token");
if (hashToken) {
  localStorage.setItem("apiToken", hashToken);
  history.classList.add("hidden");
  window.history.replaceState(null, "", location.pathname);
}
if (!apiConfig().token) {
  status.textContent = "set your API token in ⚙ (swipe ↓)";
}
flush();
