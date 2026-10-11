#!/usr/bin/env python3
"""
Docker Services Scratchpad for Qtile
====================================
A fast, keyboard-driven Docker management dashboard styled to match Qtile's
Gruvbox Dark theme and designed to slide out seamlessly from the top bar.

Features:
- Live container status, uptime, port mappings, and CPU/RAM usage
- Instant keyboard actions (r: restart, s: stop, u: start, l: view logs)
- Integrated log viewer overlay (last 100 lines)
- Live search/filter across container names, images, and ports
- Non-blocking asynchronous Docker operations (UI never freezes)
- Native X11 WM_CLASS ("docker-pad") for Qtile ScratchPad integration
- Handles Docker socket permissions gracefully (auto-detects 'docker' group)
"""

import sys
import os
import json
import time
import shlex
import subprocess
import threading
import tkinter as tk
from tkinter import font as tkfont

# ==============================================================================
# Theme: Gruvbox Dark (matching Qtile & Kitty config)
# ==============================================================================
THEME = {
    "bg": "#282828",           # Dark0 background
    "bg_surface": "#32302f",   # Dark0_soft surface
    "bg_card": "#3c3836",      # Dark1 container
    "bg_hover": "#504945",     # Dark2 hover
    "bg_selected": "#3c3836",  # Dark1 selected
    "border": "#504945",       # Dark2 border
    "border_focus": "#83a598", # Bright blue border
    "fg": "#ebdbb2",           # Light1 main text
    "fg_dim": "#a89984",       # Light4 muted text
    "fg_header": "#fbf1c7",    # Light0 prominent text
    "key_bg": "#1d2021",       # Hard dark background for key badges
    "key_fg": "#fabd2f",       # Bright yellow for key text
    "status_running": "#b8bb26", # Bright green
    "status_stopped": "#fb4934", # Bright red
    "status_paused": "#fabd2f",  # Bright yellow
    "accent_blue": "#83a598",  # Information accent
    "accent_aqua": "#8ec07c",  # Port / network accent
    "accent_purple": "#d3869b",# Special / ID accent
}


def run_docker(cmd_args: list[str]) -> subprocess.CompletedProcess:
    """Execute a docker CLI command, wrapping with sg docker if needed."""
    sock_path = "/var/run/docker.sock"
    needs_sg = os.path.exists(sock_path) and not os.access(sock_path, os.R_OK | os.W_OK)

    if needs_sg:
        cmd_str = "docker " + " ".join(shlex.quote(arg) for arg in cmd_args)
        return subprocess.run(
            ["sg", "docker", "-c", cmd_str],
            capture_output=True,
            text=True,
            check=False,
        )
    else:
        return subprocess.run(
            ["docker"] + cmd_args,
            capture_output=True,
            text=True,
            check=False,
        )


class ContainerCard:
    """Widget representing a single Docker container row."""

    def __init__(self, parent, container_data, on_click_callback):
        self.parent = parent
        self.data = container_data
        self.on_click = on_click_callback
        self.is_selected = False

        self.card = tk.Frame(
            parent,
            bg=THEME["bg_card"],
            bd=0,
            highlightthickness=2,
            highlightbackground=THEME["border"],
            cursor="hand2",
        )
        self.card.pack(fill="x", padx=12, pady=4)

        # Main content row
        self.inner = tk.Frame(self.card, bg=THEME["bg_card"])
        self.inner.pack(fill="x", padx=10, pady=8)

        # Top row: Status Badge + Name + Stats
        top_row = tk.Frame(self.inner, bg=THEME["bg_card"])
        top_row.pack(fill="x")

        state = self.data.get("State", "unknown").lower()
        if state == "running":
            status_text = "● RUNNING"
            status_color = THEME["status_running"]
        elif state in ("exited", "dead"):
            status_text = "○ EXITED"
            status_color = THEME["status_stopped"]
        elif state == "paused":
            status_text = "◌ PAUSED"
            status_color = THEME["status_paused"]
        else:
            status_text = f"● {state.upper()}"
            status_color = THEME["fg_dim"]

        self.lbl_status = tk.Label(
            top_row,
            text=f" {status_text} ",
            font=("DejaVu Sans Mono", 9, "bold"),
            fg=status_color,
            bg=THEME["key_bg"],
            padx=6,
            pady=2,
        )
        self.lbl_status.pack(side="left")

        # Name
        self.lbl_name = tk.Label(
            top_row,
            text=self.data.get("Names", "unknown"),
            font=("DejaVu Sans Mono", 11, "bold"),
            fg=THEME["fg_header"],
            bg=THEME["bg_card"],
            padx=10,
        )
        self.lbl_name.pack(side="left")

        # Stats pills (CPU / RAM)
        cpu = self.data.get("CPUPerc", "")
        mem = self.data.get("MemUsage", "")
        if cpu or mem:
            mem_short = mem.split("/")[0].strip() if "/" in mem else mem
            stats_str = f"CPU: {cpu or '0%'}  |  RAM: {mem_short or '0B'}"
            self.lbl_stats = tk.Label(
                top_row,
                text=stats_str,
                font=("DejaVu Sans Mono", 9),
                fg=THEME["accent_blue"],
                bg=THEME["key_bg"],
                padx=8,
                pady=2,
            )
            self.lbl_stats.pack(side="right")
        else:
            self.lbl_stats = None

        # Bottom row: Image, Ports, Uptime
        bot_row = tk.Frame(self.inner, bg=THEME["bg_card"])
        bot_row.pack(fill="x", pady=(6, 0))

        image = self.data.get("Image", "")
        self.lbl_image = tk.Label(
            bot_row,
            text=f"Image: {image}",
            font=("DejaVu Sans Mono", 9),
            fg=THEME["fg_dim"],
            bg=THEME["bg_card"],
        )
        self.lbl_image.pack(side="left")

        ports = self.data.get("Ports", "")
        if ports:
            # Clean up ports format for readability
            clean_ports = self._clean_ports(ports)
            self.lbl_ports = tk.Label(
                bot_row,
                text=f"Ports: {clean_ports}",
                font=("DejaVu Sans Mono", 9),
                fg=THEME["accent_aqua"],
                bg=THEME["bg_card"],
                padx=12,
            )
            self.lbl_ports.pack(side="left")
        else:
            self.lbl_ports = None

        status_msg = self.data.get("Status", "")
        self.lbl_status_msg = tk.Label(
            bot_row,
            text=status_msg,
            font=("DejaVu Sans Mono", 9),
            fg=THEME["fg_dim"],
            bg=THEME["bg_card"],
        )
        self.lbl_status_msg.pack(side="right")

        # Bind clicks to entire row
        self._bind_clicks()

    def _clean_ports(self, ports: str) -> str:
        items = ports.split(", ")
        clean = []
        for p in items:
            if "->" in p:
                parts = p.split("->")
                host = parts[0].replace("0.0.0.0:", "").replace(":::", "").replace("127.0.0.1:", "local:")
                container = parts[1].replace("/tcp", "").replace("/udp", "")
                mapping = f"{host}→{container}"
                if mapping not in clean:
                    clean.append(mapping)
        return ", ".join(clean) if clean else ports[:40]

    def _bind_clicks(self):
        widgets = [self.card, self.inner, self.lbl_status, self.lbl_name, self.lbl_image, self.lbl_status_msg]
        if self.lbl_stats:
            widgets.append(self.lbl_stats)
        if self.lbl_ports:
            widgets.append(self.lbl_ports)
        for w in widgets:
            w.bind("<Button-1>", lambda e: self.on_click(self))

    def set_selected(self, selected: bool):
        self.is_selected = selected
        if selected:
            self.card.configure(highlightbackground=THEME["border_focus"], bg=THEME["bg_selected"])
            self.inner.configure(bg=THEME["bg_selected"])
        else:
            self.card.configure(highlightbackground=THEME["border"], bg=THEME["bg_card"])
            self.inner.configure(bg=THEME["bg_card"])


class DockerPadApp:
    """Main Application Window."""

    def __init__(self, root):
        self.root = root
        self.root.title("Docker Services Manager")
        self.root.configure(bg=THEME["bg"])

        try:
            self.root.wm_attributes("-type", "dialog")
        except Exception:
            pass

        # Set initial dimensions to match Qtile DropDown proportions
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        target_w = int(sw * 0.8)
        target_h = int(sh * 0.88)
        self.root.geometry(f"{target_w}x{target_h}")
        self.root.minsize(target_w, target_h)

        self.containers = []
        self.cards = []
        self.selected_index = 0
        self.is_loading = False
        self.log_modal = None

        self._build_header()
        self._build_content_area()
        self._build_footer()
        self._bind_keys()

        # Initial fetch in background thread
        self.refresh_containers()

        # Periodic refresh every 5 seconds
        self.root.after(5000, self._auto_refresh)

    def _build_header(self):
        """Top bar with title, search input, and counts."""
        header_bar = tk.Frame(
            self.root,
            bg=THEME["bg_card"],
            bd=0,
            highlightthickness=1,
            highlightbackground=THEME["border"],
        )
        header_bar.pack(fill="x", padx=12, pady=(12, 6), ipady=8)

        # Title & Logo
        title_box = tk.Frame(header_bar, bg=THEME["bg_card"])
        title_box.pack(side="left", padx=14)

        lbl_logo = tk.Label(
            title_box,
            text="\uf120",  # FontAwesome terminal icon
            font=("FontAwesome", 15),
            fg=THEME["accent_blue"],
            bg=THEME["bg_card"],
        )
        lbl_logo.pack(side="left", padx=(0, 8))

        lbl_title = tk.Label(
            title_box,
            text="DOCKER SERVICES",
            font=("DejaVu Sans Mono", 12, "bold"),
            fg=THEME["fg_header"],
            bg=THEME["bg_card"],
        )
        lbl_title.pack(side="left")

        # Search Bar
        search_frame = tk.Frame(
            header_bar,
            bg=THEME["bg_surface"],
            bd=1,
            highlightthickness=1,
            highlightbackground=THEME["border"],
        )
        search_frame.pack(side="left", fill="x", expand=True, padx=20, ipady=3)

        lbl_search_icon = tk.Label(
            search_frame,
            text="\uf002",  # fa-search
            font=("FontAwesome", 10),
            fg=THEME["fg_dim"],
            bg=THEME["bg_surface"],
        )
        lbl_search_icon.pack(side="left", padx=(8, 4))

        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *args: self._filter_containers())

        self.search_entry = tk.Entry(
            search_frame,
            textvariable=self.search_var,
            font=("DejaVu Sans Mono", 11),
            fg=THEME["fg"],
            bg=THEME["bg_surface"],
            insertbackground=THEME["key_fg"],
            bd=0,
            highlightthickness=0,
        )
        self.search_entry.pack(side="left", fill="x", expand=True, padx=6)

        # Summary Counter Badge
        self.lbl_counts = tk.Label(
            header_bar,
            text="Loading...",
            font=("DejaVu Sans Mono", 10, "bold"),
            fg=THEME["fg"],
            bg=THEME["bg_card"],
            padx=12,
        )
        self.lbl_counts.pack(side="right")

    def _build_content_area(self):
        """Scrollable canvas for the container cards."""
        container = tk.Frame(self.root, bg=THEME["bg"])
        container.pack(fill="both", expand=True, padx=0, pady=2)

        self.canvas = tk.Canvas(
            container,
            bg=THEME["bg"],
            bd=0,
            highlightthickness=0,
        )
        self.scrollbar = tk.Scrollbar(
            container,
            orient="vertical",
            command=self.canvas.yview,
            bg=THEME["bg_card"],
            troughcolor=THEME["bg"],
            activebackground=THEME["accent_blue"],
            bd=0,
            width=10,
        )

        self.content_frame = tk.Frame(self.canvas, bg=THEME["bg"])
        self.content_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")),
        )

        self.canvas_window = self.canvas.create_window(
            (0, 0), window=self.content_frame, anchor="nw"
        )
        self.canvas.configure(xscrollcommand=None, yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        self.canvas.bind(
            "<Configure>",
            lambda e: self.canvas.itemconfig(self.canvas_window, width=e.width),
        )

        # Mouse wheel bindings
        self.root.bind_all("<Button-4>", lambda e: self.canvas.yview_scroll(-2, "units"))
        self.root.bind_all("<Button-5>", lambda e: self.canvas.yview_scroll(2, "units"))
        self.root.bind_all("<MouseWheel>", lambda e: self.canvas.yview_scroll(-1 if e.delta > 0 else 1, "units"))

    def _build_footer(self):
        """Bottom status bar with action pills and toast notification."""
        footer = tk.Frame(
            self.root,
            bg=THEME["bg_card"],
            bd=0,
            highlightthickness=1,
            highlightbackground=THEME["border"],
        )
        footer.pack(fill="x", side="bottom", padx=12, pady=(4, 12), ipady=5)

        hints = [
            ("r", "Restart"),
            ("s", "Stop"),
            ("u", "Start"),
            ("l", "Logs"),
            ("j/k", "Navigate"),
            ("/", "Search"),
            ("Esc/q", "Close"),
        ]

        hints_box = tk.Frame(footer, bg=THEME["bg_card"])
        hints_box.pack(side="left", padx=6)

        for key, action in hints:
            box = tk.Frame(hints_box, bg=THEME["bg_card"])
            box.pack(side="left", padx=6)

            k_lbl = tk.Label(
                box,
                text=key,
                font=("DejaVu Sans Mono", 8, "bold"),
                fg=THEME["key_fg"],
                bg=THEME["key_bg"],
                padx=5,
                pady=1,
            )
            k_lbl.pack(side="left", padx=(0, 4))

            a_lbl = tk.Label(
                box,
                text=action,
                font=("DejaVu Sans Mono", 8),
                fg=THEME["fg_dim"],
                bg=THEME["bg_card"],
            )
            a_lbl.pack(side="left")

        # Live Toast / Feedback Message
        self.lbl_toast = tk.Label(
            footer,
            text="Ready",
            font=("DejaVu Sans Mono", 9),
            fg=THEME["accent_aqua"],
            bg=THEME["bg_card"],
            padx=10,
        )
        self.lbl_toast.pack(side="right")

    def show_toast(self, msg: str, color: str = None):
        self.lbl_toast.configure(text=msg, fg=color or THEME["accent_aqua"])

    def refresh_containers(self):
        """Fetch containers in background thread."""
        if self.is_loading:
            return
        self.is_loading = True
        self.show_toast("Refreshing containers...")

        def _worker():
            try:
                # 1. Fetch container list
                res = run_docker(["ps", "-a", "--format", "{{json .}}"])
                if res.returncode != 0:
                    err_msg = res.stderr.strip() or f"Docker exited with code {res.returncode}"
                    self.root.after(0, lambda: self.show_toast(f"Error: {err_msg}", THEME["status_stopped"]))
                    return

                containers = []
                if res.stdout.strip():
                    for line in res.stdout.strip().split("\n"):
                        if line.strip():
                            try:
                                containers.append(json.loads(line))
                            except json.JSONDecodeError:
                                pass

                # 2. Fetch live stats
                stats_res = run_docker(["stats", "--no-stream", "--format", "{{json .}}"])
                stats_map = {}
                if stats_res.returncode == 0 and stats_res.stdout.strip():
                    for line in stats_res.stdout.strip().split("\n"):
                        if line.strip():
                            try:
                                s = json.loads(line)
                                stats_map[s.get("Name")] = s
                            except json.JSONDecodeError:
                                pass

                # Merge stats
                for c in containers:
                    name = c.get("Names")
                    if name in stats_map:
                        c["CPUPerc"] = stats_map[name].get("CPUPerc", "")
                        c["MemUsage"] = stats_map[name].get("MemUsage", "")

                self.root.after(0, lambda: self._on_containers_fetched(containers))
            except Exception as e:
                self.root.after(0, lambda: self.show_toast(f"Error: {e}", THEME["status_stopped"]))
            finally:
                self.is_loading = False

        threading.Thread(target=_worker, daemon=True).start()

    def _on_containers_fetched(self, containers: list):
        self.containers = containers
        self._filter_containers()
        self.show_toast("Ready")

    def _filter_containers(self):
        query = self.search_var.get().strip().lower()

        # Clear existing card widgets
        for c in self.cards:
            c.card.destroy()
        self.cards.clear()

        # Filter
        running_cnt = 0
        stopped_cnt = 0

        for item in self.containers:
            state = item.get("State", "").lower()
            if state == "running":
                running_cnt += 1
            else:
                stopped_cnt += 1

            name = item.get("Names", "").lower()
            image = item.get("Image", "").lower()
            ports = item.get("Ports", "").lower()

            if query and not (query in name or query in image or query in ports or query in state):
                continue

            card = ContainerCard(self.content_frame, item, on_click_callback=self._select_card)
            self.cards.append(card)

        # Update counter badge
        self.lbl_counts.configure(
            text=f"● {running_cnt} Running   ○ {stopped_cnt} Stopped"
        )

        # Maintain selection
        if self.cards:
            if self.selected_index >= len(self.cards):
                self.selected_index = len(self.cards) - 1
            self._select_card(self.cards[self.selected_index])
        else:
            self.selected_index = 0

        self.root.update_idletasks()
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _select_card(self, card: ContainerCard):
        for idx, c in enumerate(self.cards):
            if c == card:
                c.set_selected(True)
                self.selected_index = idx
            else:
                c.set_selected(False)

    def _auto_refresh(self):
        if self.log_modal is None:
            self.refresh_containers()
        self.root.after(5000, self._auto_refresh)

    def _get_selected_name(self) -> str | None:
        if 0 <= self.selected_index < len(self.cards):
            return self.cards[self.selected_index].data.get("Names")
        return None

    # ==========================================================================
    # Container Actions (Restart, Stop, Start, Logs)
    # ==========================================================================
    def action_restart(self):
        name = self._get_selected_name()
        if not name:
            return
        self.show_toast(f"Restarting {name}...", THEME["key_fg"])

        def _worker():
            res = run_docker(["restart", name])
            if res.returncode == 0:
                self.root.after(0, lambda: self.show_toast(f"✓ {name} restarted successfully!"))
            else:
                self.root.after(0, lambda: self.show_toast(f"Error restarting {name}", THEME["status_stopped"]))
            self.refresh_containers()

        threading.Thread(target=_worker, daemon=True).start()

    def action_stop(self):
        name = self._get_selected_name()
        if not name:
            return
        self.show_toast(f"Stopping {name}...", THEME["key_fg"])

        def _worker():
            res = run_docker(["stop", name])
            if res.returncode == 0:
                self.root.after(0, lambda: self.show_toast(f"✓ {name} stopped successfully!"))
            else:
                self.root.after(0, lambda: self.show_toast(f"Error stopping {name}", THEME["status_stopped"]))
            self.refresh_containers()

        threading.Thread(target=_worker, daemon=True).start()

    def action_start(self):
        name = self._get_selected_name()
        if not name:
            return
        self.show_toast(f"Starting {name}...", THEME["key_fg"])

        def _worker():
            res = run_docker(["start", name])
            if res.returncode == 0:
                self.root.after(0, lambda: self.show_toast(f"✓ {name} started successfully!"))
            else:
                self.root.after(0, lambda: self.show_toast(f"Error starting {name}", THEME["status_stopped"]))
            self.refresh_containers()

        threading.Thread(target=_worker, daemon=True).start()

    def action_logs(self):
        name = self._get_selected_name()
        if not name:
            return
        self.show_toast(f"Fetching logs for {name}...")

        def _worker():
            res = run_docker(["logs", "--tail", "150", name])
            logs_text = res.stdout if res.stdout else res.stderr
            if not logs_text:
                logs_text = "[No log output available]"
            self.root.after(0, lambda: self._show_logs_modal(name, logs_text))

        threading.Thread(target=_worker, daemon=True).start()

    def _show_logs_modal(self, name: str, logs_text: str):
        if self.log_modal:
            self.log_modal.destroy()

        modal = tk.Frame(
            self.root,
            bg=THEME["bg_surface"],
            bd=0,
            highlightthickness=2,
            highlightbackground=THEME["border_focus"],
        )
        modal.place(relx=0.05, rely=0.05, relwidth=0.9, relheight=0.9)
        self.log_modal = modal

        # Header
        hdr = tk.Frame(modal, bg=THEME["bg_card"])
        hdr.pack(fill="x", ipady=6, padx=8)

        tk.Label(
            hdr,
            text=f"Logs: {name} (Last 150 lines)",
            font=("DejaVu Sans Mono", 11, "bold"),
            fg=THEME["fg_header"],
            bg=THEME["bg_card"],
        ).pack(side="left", padx=8)

        btn_close = tk.Button(
            hdr,
            text="✕ Close (Esc)",
            font=("DejaVu Sans Mono", 9, "bold"),
            fg=THEME["fg"],
            bg=THEME["bg_hover"],
            activebackground=THEME["status_stopped"],
            bd=0,
            padx=8,
            pady=3,
            command=self._close_logs_modal,
        )
        btn_close.pack(side="right", padx=8)

        # Text area
        txt_frame = tk.Frame(modal, bg=THEME["bg"])
        txt_frame.pack(fill="both", expand=True, padx=8, pady=8)

        scroll = tk.Scrollbar(txt_frame, orient="vertical")
        txt = tk.Text(
            txt_frame,
            bg=THEME["key_bg"],
            fg=THEME["fg"],
            font=("DejaVu Sans Mono", 9),
            bd=0,
            yscrollcommand=scroll.set,
            wrap="none",
        )
        scroll.config(command=txt.yview)

        scroll.pack(side="right", fill="y")
        txt.pack(side="left", fill="both", expand=True)

        txt.insert("1.0", logs_text)
        txt.see("end")
        txt.configure(state="disabled")

        self.show_toast(f"Viewing logs for {name}")

    def _close_logs_modal(self):
        if self.log_modal:
            self.log_modal.destroy()
            self.log_modal = None
            self.show_toast("Ready")

    # ==========================================================================
    # Keyboard Bindings
    # ==========================================================================
    def _bind_keys(self):
        self.root.bind("<Escape>", self._on_escape)
        self.root.bind("q", self._on_q)
        self.root.bind("<slash>", self._on_slash)
        self.root.bind("j", lambda e: self._navigate(1))
        self.root.bind("k", lambda e: self._navigate(-1))
        self.root.bind("<Down>", lambda e: self._navigate(1))
        self.root.bind("<Up>", lambda e: self._navigate(-1))
        self.root.bind("r", lambda e: self.action_restart() if self._is_normal_mode() else None)
        self.root.bind("s", lambda e: self.action_stop() if self._is_normal_mode() else None)
        self.root.bind("u", lambda e: self.action_start() if self._is_normal_mode() else None)
        self.root.bind("l", lambda e: self.action_logs() if self._is_normal_mode() else None)

    def _is_normal_mode(self) -> bool:
        return self.root.focus_get() != self.search_entry and self.log_modal is None

    def _navigate(self, delta: int):
        if not self._is_normal_mode() or not self.cards:
            return
        new_idx = max(0, min(len(self.cards) - 1, self.selected_index + delta))
        if new_idx != self.selected_index:
            self._select_card(self.cards[new_idx])

    def _on_escape(self, event):
        if self.log_modal:
            self._close_logs_modal()
        elif self.root.focus_get() == self.search_entry and self.search_var.get():
            self.search_var.set("")
            self.root.focus_set()
        else:
            self.root.destroy()

    def _on_q(self, event):
        if self.log_modal:
            self._close_logs_modal()
        elif self.root.focus_get() != self.search_entry:
            self.root.destroy()

    def _on_slash(self, event):
        if self.root.focus_get() != self.search_entry and not self.log_modal:
            self.search_entry.focus_set()
            self.search_entry.select_range(0, "end")
            return "break"


def main():
    root = tk.Tk(className="docker-pad")
    app = DockerPadApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
