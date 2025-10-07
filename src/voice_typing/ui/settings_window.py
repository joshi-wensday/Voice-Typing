"""Settings window (Tkinter) for basic configuration."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional

from ..config.manager import ConfigManager
from ..audio.capture import AudioCapture


class SettingsWindow:
    def __init__(self, cfgm: ConfigManager, root: Optional[tk.Tk] = None) -> None:
        self.cfgm = cfgm
        self.root: Optional[tk.Tk] = root
        self.win: Optional[tk.Toplevel] = None

    def _build(self) -> None:
        assert self.win is not None
        print("[SettingsWindow] Building settings UI")
        self.win.title("Voice Typing Settings")
        self.win.geometry("480x420+200+200")
        pad = {"padx": 8, "pady": 6}

        nb = ttk.Notebook(self.win)
        nb.pack(fill=tk.BOTH, expand=True)

        # General tab
        general = ttk.Frame(nb)
        nb.add(general, text="General")

        ttk.Label(general, text="Hotkey (e.g., ctrl+shift+space)").grid(row=0, column=0, sticky="w", **pad)
        self.var_hotkey = tk.StringVar(master=self.win, value=self.cfgm.config.ui.hotkey)
        ttk.Entry(general, textvariable=self.var_hotkey, width=32).grid(row=0, column=1, **pad)

        ttk.Label(general, text="Model").grid(row=1, column=0, sticky="w", **pad)
        self.var_model = tk.StringVar(master=self.win, value=self.cfgm.config.stt.model)
        ttk.Combobox(general, textvariable=self.var_model, values=["tiny", "base", "small", "medium", "large-v2"], width=28).grid(row=1, column=1, **pad)

        ttk.Label(general, text="Device").grid(row=2, column=0, sticky="w", **pad)
        self.var_device = tk.StringVar(master=self.win, value=self.cfgm.config.stt.device)
        ttk.Combobox(general, textvariable=self.var_device, values=["auto", "cpu", "cuda"], width=28).grid(row=2, column=1, **pad)

        ttk.Label(general, text="Compute Type").grid(row=3, column=0, sticky="w", **pad)
        self.var_compute = tk.StringVar(master=self.win, value=self.cfgm.config.stt.compute_type)
        ttk.Combobox(general, textvariable=self.var_compute, values=["float16", "float32", "int8"], width=28).grid(row=3, column=1, **pad)

        # Audio tab
        audio_tab = ttk.Frame(nb)
        nb.add(audio_tab, text="Audio")
        devices = AudioCapture().list_devices()
        device_names = [f"{d['id']}: {d['name']}" for d in devices]
        ttk.Label(audio_tab, text="Input Device").grid(row=0, column=0, sticky="w", **pad)
        self.var_device_id = tk.StringVar(master=self.win, value="default" if self.cfgm.config.audio.device_id is None else str(self.cfgm.config.audio.device_id))
        cb = ttk.Combobox(audio_tab, textvariable=self.var_device_id, values=["default"] + device_names, width=36)
        cb.grid(row=0, column=1, **pad)

        ttk.Label(audio_tab, text="Sample Rate").grid(row=1, column=0, sticky="w", **pad)
        self.var_sr = tk.IntVar(master=self.win, value=self.cfgm.config.audio.sample_rate)
        ttk.Entry(audio_tab, textvariable=self.var_sr, width=12).grid(row=1, column=1, sticky="w", **pad)

        # Streaming tab
        stream_tab = ttk.Frame(nb)
        nb.add(stream_tab, text="Streaming")

        ttk.Label(stream_tab, text="Mode").grid(row=0, column=0, sticky="w", **pad)
        self.var_stream_mode = tk.StringVar(master=self.win, value=self.cfgm.config.streaming.mode)
        ttk.Combobox(stream_tab, textvariable=self.var_stream_mode, values=["final_only"], width=18).grid(row=0, column=1, **pad)

        ttk.Label(stream_tab, text="Segmentation").grid(row=1, column=0, sticky="w", **pad)
        self.var_seg = tk.StringVar(master=self.win, value=self.cfgm.config.streaming.segmentation)
        ttk.Combobox(stream_tab, textvariable=self.var_seg, values=["energy", "vad"], width=18).grid(row=1, column=1, **pad)

        ttk.Label(stream_tab, text="Min Segment (s)").grid(row=2, column=0, sticky="w", **pad)
        self.var_min_seg = tk.DoubleVar(master=self.win, value=self.cfgm.config.streaming.min_segment_sec)
        ttk.Entry(stream_tab, textvariable=self.var_min_seg, width=10).grid(row=2, column=1, sticky="w", **pad)

        ttk.Label(stream_tab, text="Min Silence (s)").grid(row=3, column=0, sticky="w", **pad)
        self.var_min_sil = tk.DoubleVar(master=self.win, value=self.cfgm.config.streaming.min_silence_sec)
        ttk.Entry(stream_tab, textvariable=self.var_min_sil, width=10).grid(row=3, column=1, sticky="w", **pad)

        ttk.Label(stream_tab, text="Energy Threshold").grid(row=4, column=0, sticky="w", **pad)
        self.var_energy = tk.DoubleVar(master=self.win, value=self.cfgm.config.streaming.energy_threshold)
        ttk.Entry(stream_tab, textvariable=self.var_energy, width=10).grid(row=4, column=1, sticky="w", **pad)

        # Decoding tab
        dec_tab = ttk.Frame(nb)
        nb.add(dec_tab, text="Decoding")

        ttk.Label(dec_tab, text="Beam Size").grid(row=0, column=0, sticky="w", **pad)
        self.var_beam = tk.IntVar(master=self.win, value=self.cfgm.config.decoding.beam_size)
        ttk.Entry(dec_tab, textvariable=self.var_beam, width=10).grid(row=0, column=1, sticky="w", **pad)

        ttk.Label(dec_tab, text="Temperature").grid(row=1, column=0, sticky="w", **pad)
        self.var_temp = tk.DoubleVar(master=self.win, value=self.cfgm.config.decoding.temperature)
        ttk.Entry(dec_tab, textvariable=self.var_temp, width=10).grid(row=1, column=1, sticky="w", **pad)

        # Buttons
        btns = ttk.Frame(self.win)
        btns.pack(fill=tk.X, padx=8, pady=8)
        ttk.Button(btns, text="Save", command=self._save).pack(side=tk.RIGHT, padx=6)
        ttk.Button(btns, text="Close", command=self.win.destroy).pack(side=tk.RIGHT)

    def _save(self) -> None:
        try:
            hk = self.var_hotkey.get().strip()
            model = self.var_model.get().strip()
            device = self.var_device.get().strip()
            compute = self.var_compute.get().strip()
            sr = int(self.var_sr.get())
            device_id = self.var_device_id.get()
            if device_id == "default" or device_id == "":
                did = None
            else:
                did = int(device_id.split(":", 1)[0]) if ":" in device_id else int(device_id)

            self.cfgm.update(
                ui__hotkey=hk,
                stt__model=model,
                stt__device=device,
                stt__compute_type=compute,
                audio__sample_rate=sr,
                audio__device_id=did,
                streaming__mode=self.var_stream_mode.get().strip(),
                streaming__segmentation=self.var_seg.get().strip(),
                streaming__min_segment_sec=float(self.var_min_seg.get()),
                streaming__min_silence_sec=float(self.var_min_sil.get()),
                streaming__energy_threshold=float(self.var_energy.get()),
                decoding__beam_size=int(self.var_beam.get()),
                decoding__temperature=float(self.var_temp.get()),
            )
            messagebox.showinfo("Settings", "Saved. Some changes may require restart.")
        except Exception as e:
            messagebox.showerror("Settings", f"Failed to save: {e}")

    def _show_impl(self) -> None:
        print("[SettingsWindow] Show requested")
        if self.root is None:
            print("[SettingsWindow] Creating root")
            self.root = tk.Tk()
            self.root.withdraw()
        if self.win is not None and tk.Toplevel.winfo_exists(self.win):
            print("[SettingsWindow] Deiconify existing window")
            self.win.deiconify()
            self.win.lift()
            self.win.focus_force()
            self.win.update_idletasks()
            return
        print("[SettingsWindow] Creating Toplevel")
        self.win = tk.Toplevel(self.root)
        self._build()
        try:
            self.win.attributes('-topmost', True)
        except Exception:
            pass
        self.win.update_idletasks()
        self.win.deiconify()
        self.win.lift()
        self.win.focus_force()
        print("[SettingsWindow] Shown")

    def show(self) -> None:
        # Always marshal to Tk main thread
        if self.root is not None:
            try:
                self.root.after(0, self._show_impl)
                return
            except Exception:
                pass
        # Fallback (should not happen if root exists)
        self._show_impl()
