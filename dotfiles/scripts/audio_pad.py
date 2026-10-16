#!/usr/bin/env python3
"""
Audio Controller Dropdown for Qtile (PipeWire / WirePlumber)
=============================================================
A fast, keyboard-driven audio mixer dashboard styled to match Qtile's
Gruvbox Dark theme and designed to slide out seamlessly from the top bar.

Features:
- Master Sink volume control, status, and mute toggle
- Microphone / input source volume control and mute toggle
- Live per-application stream volume sliders (e.g. Limusic, mpv, Firefox)
- Output device switcher (Headphones, Speakers, HDMI, Bluetooth)
- Keyboard shortcuts:
    j / Down : Master Volume -5%
    k / Up   : Master Volume +5%
    m        : Toggle Master Mute
    M        : Toggle Mic Mute
    r        : Refresh devices and streams
    q / Esc  : Dismiss dropdown
- Native X11 WM_CLASS ("audio-pad") for Qtile ScratchPad integration
"""

import sys
import os
import re
import subprocess
import threading
import tkinter as tk
from tkinter import ttk, font as tkfont

# ==============================================================================
# Theme: Central Gruvbox (Dark / Light via Super + o)
# ==============================================================================
try:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from theme import get_theme
    THEME = get_theme()
except Exception:
    THEME = {
        "bg": "#282828", "bg_surface": "#32302f", "bg_card": "#3c3836",
        "bg_hover": "#504945", "bg_selected": "#504945", "border": "#504945",
        "border_focus": "#83a598", "fg": "#ebdbb2", "fg_dim": "#a89984",
        "fg_header": "#fbf1c7", "key_bg": "#1d2021", "key_fg": "#fabd2f",
        "status_running": "#b8bb26", "status_stopped": "#fb4934",
        "status_paused": "#fabd2f", "accent_blue": "#83a598",
        "accent_aqua": "#8ec07c", "accent_purple": "#d3869b",
    }


class PipeWireManager:
    """Helper to query and control PipeWire via wpctl."""

    @staticmethod
    def get_status():
        """Parses wpctl status to find sinks, sources, and active streams."""
        sinks = []
        sources = []
        streams = []

        try:
            out = subprocess.check_output(["wpctl", "status"], text=True, stderr=subprocess.DEVNULL)
        except Exception:
            return sinks, sources, streams

        if isinstance(out, (bytes, bytearray)):
            try:
                out = out.decode("utf-8", errors="replace")
            except Exception:
                out = ""

        if not out or not isinstance(out, str):
            return sinks, sources, streams

        in_audio_block = False
        current_section = None
        for line in out.splitlines():
            clean_line = re.sub(r"^[│├└─\s]+", "", line).strip()
            if clean_line == "Audio":
                in_audio_block = True
                continue
            elif clean_line in ("Video", "Settings") or clean_line.startswith("Filters:"):
                in_audio_block = False
                current_section = None
                continue

            if not in_audio_block:
                continue

            if clean_line.startswith("Sinks:"):
                current_section = "sinks"
                continue
            elif clean_line.startswith("Sources:"):
                current_section = "sources"
                continue
            elif clean_line.startswith("Streams:"):
                current_section = "streams"
                continue
            elif clean_line.startswith("Filters:"):
                current_section = None
                continue

            if current_section == "sinks":
                m = re.match(r"(\*?)\s*(\d+)\.\s+(.*?)(?:\s+\[vol:\s*([\d\.]+)(?:\s+(MUTED))?\])?$", clean_line)
                if m:
                    is_def = bool(m.group(1))
                    nid = int(m.group(2))
                    name = m.group(3).strip()
                    vol = float(m.group(4)) if m.group(4) else 1.0
                    muted = bool(m.group(5))
                    sinks.append({"id": nid, "name": name, "vol": vol, "muted": muted, "is_default": is_def})
            elif current_section == "sources":
                m = re.match(r"(\*?)\s*(\d+)\.\s+(.*?)(?:\s+\[vol:\s*([\d\.]+)(?:\s+(MUTED))?\])?$", clean_line)
                if m:
                    is_def = bool(m.group(1))
                    nid = int(m.group(2))
                    name = m.group(3).strip()
                    vol = float(m.group(4)) if m.group(4) else 1.0
                    muted = bool(m.group(5))
                    sources.append({"id": nid, "name": name, "vol": vol, "muted": muted, "is_default": is_def})
            elif current_section == "streams":
                m = re.match(r"(\d+)\.\s+([^>]+)$", clean_line)
                if m:
                    nid = int(m.group(1))
                    name = m.group(2).strip()
                    try:
                        v_out = subprocess.check_output(["wpctl", "get-volume", str(nid)], text=True, stderr=subprocess.DEVNULL).strip()
                        vm = re.search(r"([\d\.]+)", v_out)
                        vol = float(vm.group(1)) if vm else 1.0
                        muted = "MUTED" in v_out
                    except Exception:
                        vol, muted = 1.0, False
                    streams.append({"id": nid, "name": name, "vol": vol, "muted": muted})

        return sinks, sources, streams

    @staticmethod
    def set_volume(target, vol_percent):
        """Sets volume for target node or @DEFAULT_AUDIO_SINK@ (0.0 to 1.5)."""
        vol_float = max(0.0, min(1.5, vol_percent / 100.0))
        subprocess.run(["wpctl", "set-volume", "-l", "1.5", str(target), f"{vol_float:.2f}"], stderr=subprocess.DEVNULL)

    @staticmethod
    def toggle_mute(target):
        """Toggles mute on target node."""
        subprocess.run(["wpctl", "set-mute", str(target), "toggle"], stderr=subprocess.DEVNULL)

    @staticmethod
    def set_default(node_id):
        """Sets node as default sink."""
        subprocess.run(["wpctl", "set-default", str(node_id)], stderr=subprocess.DEVNULL)


class AudioPadApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Audio Controller")
        self.root.configure(bg=THEME["bg"])

        try:
            self.root.wm_attributes("-type", "dialog")
        except Exception:
            pass

        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        target_w = min(1500, int(sw * 0.8))
        target_h = int(sh * 0.88)
        self.root.geometry(f"{target_w}x{target_h}")

        self.sinks = []
        self.sources = []
        self.streams = []

        self._updating_slider = False
        self._vol_debounce_timers = {}

        self._build_header()
        self._build_content_area()
        self._build_footer()
        self._bind_keys()

        self.refresh_audio()
        self.root.after(2000, self._auto_refresh)

    def _debounced_set_volume(self, target, vol_percent: int, delay_ms: int = 40):
        """Throttle volume adjustments during rapid slider drag events."""
        if target in self._vol_debounce_timers:
            try:
                self.root.after_cancel(self._vol_debounce_timers[target])
            except Exception:
                pass

        def _apply():
            PipeWireManager.set_volume(target, vol_percent)
            self._updating_slider = False
            self._vol_debounce_timers.pop(target, None)

        self._vol_debounce_timers[target] = self.root.after(delay_ms, _apply)

    def _build_header(self):
        header_bar = tk.Frame(
            self.root,
            bg=THEME["bg_card"],
            bd=0,
            highlightthickness=1,
            highlightbackground=THEME["border"],
        )
        header_bar.pack(fill="x", padx=12, pady=(12, 6), ipady=8)

        title_box = tk.Frame(header_bar, bg=THEME["bg_card"])
        title_box.pack(side="left", padx=14)

        lbl_logo = tk.Label(
            title_box,
            text="🔊",
            font=("DejaVu Sans Mono", 14),
            fg=THEME["accent_blue"],
            bg=THEME["bg_card"],
        )
        lbl_logo.pack(side="left", padx=(0, 8))

        lbl_title = tk.Label(
            title_box,
            text="PIPEWIRE AUDIO CONTROLLER",
            font=("DejaVu Sans Mono", 12, "bold"),
            fg=THEME["fg_header"],
            bg=THEME["bg_card"],
        )
        lbl_title.pack(side="left")

        btn_refresh = tk.Button(
            header_bar,
            text="⟳ Refresh",
            font=("DejaVu Sans Mono", 9, "bold"),
            fg=THEME["key_fg"],
            bg=THEME["key_bg"],
            activebackground=THEME["bg_hover"],
            activeforeground=THEME["fg"],
            bd=0,
            padx=10,
            pady=3,
            cursor="hand2",
            command=self.refresh_audio,
        )
        btn_refresh.pack(side="right", padx=14)

    def _build_content_area(self):
        container = tk.Frame(self.root, bg=THEME["bg"])
        container.pack(fill="both", expand=True, padx=12, pady=4)

        self.canvas = tk.Canvas(container, bg=THEME["bg"], bd=0, highlightthickness=0)
        self.scrollbar = tk.Scrollbar(container, orient="vertical", command=self.canvas.yview, bg=THEME["bg_card"])
        self.scroll_frame = tk.Frame(self.canvas, bg=THEME["bg"])

        self.scroll_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas_window = self.canvas.create_window((0, 0), window=self.scroll_frame, anchor="nw")
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfig(self.canvas_window, width=e.width))

        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

    def _build_footer(self):
        footer_bar = tk.Frame(
            self.root,
            bg=THEME["bg_surface"],
            bd=0,
            highlightthickness=1,
            highlightbackground=THEME["border"],
        )
        footer_bar.pack(fill="x", padx=12, pady=(6, 12), ipady=6)

        shortcuts = [
            ("j / Down", "Vol -5%"),
            ("k / Up", "Vol +5%"),
            ("m", "Mute Out"),
            ("M", "Mute Mic"),
            ("r", "Refresh"),
            ("q / Esc", "Close"),
        ]

        for key, desc in shortcuts:
            box = tk.Frame(footer_bar, bg=THEME["bg_surface"])
            box.pack(side="left", padx=10)

            lbl_k = tk.Label(
                box,
                text=f" {key} ",
                font=("DejaVu Sans Mono", 8, "bold"),
                fg=THEME["key_fg"],
                bg=THEME["key_bg"],
                padx=4,
                pady=1,
            )
            lbl_k.pack(side="left")

            lbl_d = tk.Label(
                box,
                text=f" {desc}",
                font=("DejaVu Sans Mono", 8),
                fg=THEME["fg_dim"],
                bg=THEME["bg_surface"],
            )
            lbl_d.pack(side="left")

    def _bind_keys(self):
        self.root.bind("<Escape>", lambda e: self.root.destroy())
        self.root.bind("q", lambda e: self.root.destroy())
        self.root.bind("Q", lambda e: self.root.destroy())
        self.root.bind("r", lambda e: self.refresh_audio())
        self.root.bind("R", lambda e: self.refresh_audio())
        self.root.bind("m", lambda e: self._on_master_mute())
        self.root.bind("M", lambda e: self._on_mic_mute())
        self.root.bind("k", lambda e: self._adjust_master(5))
        self.root.bind("<Up>", lambda e: self._adjust_master(5))
        self.root.bind("j", lambda e: self._adjust_master(-5))
        self.root.bind("<Down>", lambda e: self._adjust_master(-5))

    def _on_master_mute(self):
        PipeWireManager.toggle_mute("@DEFAULT_AUDIO_SINK@")
        self.refresh_audio()

    def _on_mic_mute(self):
        PipeWireManager.toggle_mute("@DEFAULT_AUDIO_SOURCE@")
        self.refresh_audio()

    def _adjust_master(self, delta):
        def_sink = next((s for s in self.sinks if s["is_default"]), None)
        curr = int(def_sink["vol"] * 100) if def_sink else 80
        new_vol = max(0, min(150, curr + delta))
        PipeWireManager.set_volume("@DEFAULT_AUDIO_SINK@", new_vol)
        self.refresh_audio()

    def _auto_refresh(self):
        if not self._updating_slider:
            self.refresh_audio()
        self.root.after(3000, self._auto_refresh)

    def refresh_audio(self):
        self.sinks, self.sources, self.streams = PipeWireManager.get_status()
        self._render_ui()

    def _render_ui(self):
        for w in self.scroll_frame.winfo_children():
            w.destroy()

        # 1. Master Output Card
        self._render_master_card()

        # 2. Microphone Input Card
        self._render_mic_card()

        # 3. Active Streams Section
        self._render_streams_section()

        # 4. Available Sinks Section
        self._render_sinks_section()

    def _render_master_card(self):
        def_sink = next((s for s in self.sinks if s["is_default"]), None)
        vol_pct = int((def_sink["vol"] if def_sink else 0.8) * 100)
        is_muted = def_sink["muted"] if def_sink else False
        name = def_sink["name"] if def_sink else "Default Audio Sink"

        card = tk.Frame(self.scroll_frame, bg=THEME["bg_card"], bd=0, highlightthickness=1, highlightbackground=THEME["border"])
        card.pack(fill="x", padx=8, pady=4)

        inner = tk.Frame(card, bg=THEME["bg_card"])
        inner.pack(fill="x", padx=14, pady=10)

        # Header
        row_top = tk.Frame(inner, bg=THEME["bg_card"])
        row_top.pack(fill="x")

        status_text = "MUTED" if is_muted else "ACTIVE"
        status_color = THEME["status_stopped"] if is_muted else THEME["status_running"]

        lbl_badge = tk.Label(row_top, text=f" {status_text} ", font=("DejaVu Sans Mono", 9, "bold"), fg=status_color, bg=THEME["key_bg"], padx=6, pady=2)
        lbl_badge.pack(side="left")

        lbl_name = tk.Label(row_top, text=f" Master Output: {name}", font=("DejaVu Sans Mono", 11, "bold"), fg=THEME["fg_header"], bg=THEME["bg_card"])
        lbl_name.pack(side="left", padx=8)

        lbl_val = tk.Label(row_top, text=f"{vol_pct}%", font=("DejaVu Sans Mono", 11, "bold"), fg=THEME["accent_blue"], bg=THEME["bg_card"])
        lbl_val.pack(side="right")

        # Controls row
        row_ctrl = tk.Frame(inner, bg=THEME["bg_card"])
        row_ctrl.pack(fill="x", pady=(8, 0))

        scale = tk.Scale(
            row_ctrl,
            from_=0,
            to=150,
            orient="horizontal",
            showvalue=0,
            bg=THEME["bg_card"],
            troughcolor=THEME["bg_surface"],
            activebackground=THEME["accent_blue"],
            highlightthickness=0,
            bd=0,
            sliderrelief="flat",
        )
        scale.set(vol_pct)

        def on_scale(val):
            self._updating_slider = True
            v = int(float(val))
            lbl_val.config(text=f"{v}%")
            self._debounced_set_volume("@DEFAULT_AUDIO_SINK@", v)

        scale.config(command=on_scale)
        scale.pack(side="left", fill="x", expand=True, padx=(0, 14))

        btn_mute = tk.Button(
            row_ctrl,
            text="Unmute" if is_muted else "Mute (m)",
            font=("DejaVu Sans Mono", 9, "bold"),
            fg=THEME["status_running"] if is_muted else THEME["status_stopped"],
            bg=THEME["key_bg"],
            activebackground=THEME["bg_hover"],
            bd=0,
            padx=10,
            pady=3,
            cursor="hand2",
            command=self._on_master_mute,
        )
        btn_mute.pack(side="right")

    def _render_mic_card(self):
        def_src = next((s for s in self.sources if s["is_default"]), None)
        vol_pct = int((def_src["vol"] if def_src else 1.0) * 100)
        is_muted = def_src["muted"] if def_src else False
        name = def_src["name"] if def_src else "Default Microphone"

        card = tk.Frame(self.scroll_frame, bg=THEME["bg_card"], bd=0, highlightthickness=1, highlightbackground=THEME["border"])
        card.pack(fill="x", padx=8, pady=4)

        inner = tk.Frame(card, bg=THEME["bg_card"])
        inner.pack(fill="x", padx=14, pady=10)

        row_top = tk.Frame(inner, bg=THEME["bg_card"])
        row_top.pack(fill="x")

        status_text = "MUTED" if is_muted else "ACTIVE"
        status_color = THEME["status_stopped"] if is_muted else THEME["status_running"]

        lbl_badge = tk.Label(row_top, text=f" {status_text} ", font=("DejaVu Sans Mono", 9, "bold"), fg=status_color, bg=THEME["key_bg"], padx=6, pady=2)
        lbl_badge.pack(side="left")

        lbl_name = tk.Label(row_top, text=f" Microphone: {name}", font=("DejaVu Sans Mono", 11, "bold"), fg=THEME["fg_header"], bg=THEME["bg_card"])
        lbl_name.pack(side="left", padx=8)

        lbl_val = tk.Label(row_top, text=f"{vol_pct}%", font=("DejaVu Sans Mono", 11, "bold"), fg=THEME["accent_aqua"], bg=THEME["bg_card"])
        lbl_val.pack(side="right")

        row_ctrl = tk.Frame(inner, bg=THEME["bg_card"])
        row_ctrl.pack(fill="x", pady=(8, 0))

        scale = tk.Scale(
            row_ctrl,
            from_=0,
            to=100,
            orient="horizontal",
            showvalue=0,
            bg=THEME["bg_card"],
            troughcolor=THEME["bg_surface"],
            activebackground=THEME["accent_aqua"],
            highlightthickness=0,
            bd=0,
            sliderrelief="flat",
        )
        scale.set(vol_pct)

        def on_scale(val):
            self._updating_slider = True
            v = int(float(val))
            lbl_val.config(text=f"{v}%")
            self._debounced_set_volume("@DEFAULT_AUDIO_SOURCE@", v)

        scale.config(command=on_scale)
        scale.pack(side="left", fill="x", expand=True, padx=(0, 14))

        btn_mute = tk.Button(
            row_ctrl,
            text="Unmute" if is_muted else "Mute (M)",
            font=("DejaVu Sans Mono", 9, "bold"),
            fg=THEME["status_running"] if is_muted else THEME["status_stopped"],
            bg=THEME["key_bg"],
            activebackground=THEME["bg_hover"],
            bd=0,
            padx=10,
            pady=3,
            cursor="hand2",
            command=self._on_mic_mute,
        )
        btn_mute.pack(side="right")

    def _render_streams_section(self):
        sec_box = tk.Frame(self.scroll_frame, bg=THEME["bg"])
        sec_box.pack(fill="x", padx=8, pady=(12, 2))

        lbl_sec = tk.Label(sec_box, text="ACTIVE APPLICATION STREAMS", font=("DejaVu Sans Mono", 10, "bold"), fg=THEME["key_fg"], bg=THEME["bg"])
        lbl_sec.pack(side="left")

        if not self.streams:
            empty_card = tk.Frame(self.scroll_frame, bg=THEME["bg_card"], bd=0, highlightthickness=1, highlightbackground=THEME["border"])
            empty_card.pack(fill="x", padx=8, pady=4)
            lbl_empty = tk.Label(empty_card, text="No application playback streams currently active.", font=("DejaVu Sans Mono", 9, "italic"), fg=THEME["fg_dim"], bg=THEME["bg_card"], pady=12)
            lbl_empty.pack()
            return

        for st in self.streams:
            nid = st["id"]
            name = st["name"]
            vol_pct = int(st["vol"] * 100)
            is_muted = st["muted"]

            card = tk.Frame(self.scroll_frame, bg=THEME["bg_card"], bd=0, highlightthickness=1, highlightbackground=THEME["border"])
            card.pack(fill="x", padx=8, pady=4)

            inner = tk.Frame(card, bg=THEME["bg_card"])
            inner.pack(fill="x", padx=12, pady=8)

            row_top = tk.Frame(inner, bg=THEME["bg_card"])
            row_top.pack(fill="x")

            lbl_icon = tk.Label(row_top, text="▶", font=("DejaVu Sans Mono", 9), fg=THEME["accent_purple"], bg=THEME["bg_card"])
            lbl_icon.pack(side="left", padx=(0, 6))

            lbl_st_name = tk.Label(row_top, text=f"{name} (Node #{nid})", font=("DejaVu Sans Mono", 10, "bold"), fg=THEME["fg_header"], bg=THEME["bg_card"])
            lbl_st_name.pack(side="left")

            lbl_st_val = tk.Label(row_top, text=f"{vol_pct}%", font=("DejaVu Sans Mono", 10, "bold"), fg=THEME["accent_purple"], bg=THEME["bg_card"])
            lbl_st_val.pack(side="right")

            row_ctrl = tk.Frame(inner, bg=THEME["bg_card"])
            row_ctrl.pack(fill="x", pady=(6, 0))

            scale = tk.Scale(
                row_ctrl,
                from_=0,
                to=150,
                orient="horizontal",
                showvalue=0,
                bg=THEME["bg_card"],
                troughcolor=THEME["bg_surface"],
                activebackground=THEME["accent_purple"],
                highlightthickness=0,
                bd=0,
                sliderrelief="flat",
            )
            scale.set(vol_pct)

            def make_scale_cmd(target_id, target_lbl):
                def _cmd(val):
                    self._updating_slider = True
                    v = int(float(val))
                    target_lbl.config(text=f"{v}%")
                    self._debounced_set_volume(target_id, v)
                return _cmd

            scale.config(command=make_scale_cmd(nid, lbl_st_val))
            scale.pack(side="left", fill="x", expand=True, padx=(0, 14))

            def make_mute_cmd(target_id):
                def _cmd():
                    PipeWireManager.toggle_mute(target_id)
                    self.refresh_audio()
                return _cmd

            btn_mute = tk.Button(
                row_ctrl,
                text="Unmute" if is_muted else "Mute",
                font=("DejaVu Sans Mono", 8, "bold"),
                fg=THEME["status_running"] if is_muted else THEME["status_stopped"],
                bg=THEME["key_bg"],
                activebackground=THEME["bg_hover"],
                bd=0,
                padx=8,
                pady=2,
                cursor="hand2",
                command=make_mute_cmd(nid),
            )
            btn_mute.pack(side="right")

    def _render_sinks_section(self):
        sec_box = tk.Frame(self.scroll_frame, bg=THEME["bg"])
        sec_box.pack(fill="x", padx=8, pady=(12, 2))

        lbl_sec = tk.Label(sec_box, text="AVAILABLE OUTPUT DEVICES", font=("DejaVu Sans Mono", 10, "bold"), fg=THEME["key_fg"], bg=THEME["bg"])
        lbl_sec.pack(side="left")

        for s in self.sinks:
            nid = s["id"]
            name = s["name"]
            is_def = s["is_default"]

            card = tk.Frame(self.scroll_frame, bg=THEME["bg_card"], bd=0, highlightthickness=1, highlightbackground=THEME["border_focus"] if is_def else THEME["border"])
            card.pack(fill="x", padx=8, pady=3)

            inner = tk.Frame(card, bg=THEME["bg_card"])
            inner.pack(fill="x", padx=12, pady=6)

            star = "★ " if is_def else "☆ "
            star_color = THEME["key_fg"] if is_def else THEME["fg_dim"]

            lbl_star = tk.Label(inner, text=star, font=("DejaVu Sans Mono", 11), fg=star_color, bg=THEME["bg_card"])
            lbl_star.pack(side="left")

            lbl_name = tk.Label(inner, text=f"{name} (Node #{nid})", font=("DejaVu Sans Mono", 9, "bold" if is_def else "normal"), fg=THEME["fg_header"] if is_def else THEME["fg"], bg=THEME["bg_card"])
            lbl_name.pack(side="left")

            if not is_def:
                def make_set_def_cmd(target_id):
                    def _cmd():
                        PipeWireManager.set_default(target_id)
                        self.refresh_audio()
                    return _cmd

                btn_set = tk.Button(
                    inner,
                    text="Set Default",
                    font=("DejaVu Sans Mono", 8),
                    fg=THEME["key_fg"],
                    bg=THEME["key_bg"],
                    activebackground=THEME["bg_hover"],
                    bd=0,
                    padx=8,
                    pady=2,
                    cursor="hand2",
                    command=make_set_def_cmd(nid),
                )
                btn_set.pack(side="right")
            else:
                lbl_curr = tk.Label(inner, text="DEFAULT SINK", font=("DejaVu Sans Mono", 8, "bold"), fg=THEME["status_running"], bg=THEME["key_bg"], padx=6, pady=2)
                lbl_curr.pack(side="right")


if __name__ == "__main__":
    root = tk.Tk(className="audio-pad")
    app = AudioPadApp(root)
    root.mainloop()
