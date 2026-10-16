#!/usr/bin/env python3
"""
Wi-Fi Network Manager Scratchpad for Qtile
===========================================
A fast, keyboard-driven Wi-Fi selection and connection dashboard styled to
match Qtile's Gruvbox Dark / Light theme and designed to slide out seamlessly
from the top bar via Super + i.

Features:
- Live scan of available Wi-Fi networks (SSIDs, BSSIDs, frequencies, bands)
- Exact numerical RF signal strength in dBm and percentage (for precise distance assessment)
- Full security support: Open, WPA, WPA2, WPA3-SAE, WPA2/WPA3 mixed
- Seamless connection workflow with interactive modal passphrase dialog
- Instant keyboard actions (j/k: navigate, Enter: connect, r: rescan, d: disconnect, /: search)
- Non-blocking asynchronous scanning and association (UI never freezes)
- Auto-configures wpa_supplicant control socket via D-Bus fi.w1.wpa_supplicant1 if needed
- Native X11 WM_CLASS ("wifi-pad") for Qtile ScratchPad DropDown integration
"""

import os
import sys
import time
import shutil
import subprocess
import threading
import tkinter as tk
from tkinter import font as tkfont
from dataclasses import dataclass

# ==============================================================================
# Theme: Central Gruvbox (Dark / Light via Super + o)
# ==============================================================================
try:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from theme import get_theme
    THEME = get_theme()
except Exception:
    THEME = {
        "bg": "#282828",
        "bg_surface": "#32302f",
        "bg_card": "#3c3836",
        "bg_hover": "#504945",
        "bg_selected": "#3c3836",
        "border": "#504945",
        "border_focus": "#83a598",
        "fg": "#ebdbb2",
        "fg_dim": "#a89984",
        "fg_header": "#fbf1c7",
        "key_bg": "#1d2021",
        "key_fg": "#fabd2f",
        "status_running": "#b8bb26",
        "status_stopped": "#fb4934",
        "status_paused": "#fabd2f",
        "accent_blue": "#83a598",
        "accent_aqua": "#8ec07c",
        "accent_purple": "#d3869b",
        "accent_yellow": "#fabd2f",
        "accent_green": "#b8bb26",
        "accent_orange": "#fe8019",
        "accent_red": "#fb4934",
    }


# ==============================================================================
# Frequency & Signal Utilities
# ==============================================================================
def freq_to_channel_and_band(freq: int) -> tuple[int, str]:
    """Convert MHz frequency to 802.11 channel and human-readable band string."""
    if 2412 <= freq <= 2484:
        ch = 14 if freq == 2484 else (freq - 2407) // 5
        return ch, "2.4 GHz"
    elif 5170 <= freq <= 5825:
        ch = (freq - 5000) // 5
        return ch, "5 GHz"
    elif 5925 <= freq <= 7125:
        ch = (freq - 5950) // 5 + 1
        return ch, "6 GHz"
    return 0, f"{freq} MHz"


def dbm_to_pct(dbm: int) -> int:
    """Map raw dBm to 0-100% quality scale (standard clamped linear mapping)."""
    if dbm >= -50:
        return 100
    elif dbm <= -100:
        return 0
    return max(0, min(100, 2 * (dbm + 100)))


def parse_security_flags(flags: str) -> str:
    """Extract standard human-readable security protocol from wpa_supplicant flags."""
    flags_upper = flags.upper()
    has_sae = "SAE" in flags_upper or "WPA3" in flags_upper
    has_wpa2 = "WPA2" in flags_upper or "RSN" in flags_upper
    has_wpa = "WPA" in flags_upper
    has_wep = "WEP" in flags_upper

    if has_sae and has_wpa2:
        return "WPA2/WPA3"
    elif has_sae:
        return "WPA3"
    elif has_wpa2:
        return "WPA2"
    elif has_wpa:
        return "WPA"
    elif has_wep:
        return "WEP"
    return "Open"


@dataclass
class NetworkInfo:
    bssid: str
    freq: int
    channel: int
    band: str
    signal_dbm: int
    signal_pct: int
    flags: str
    security: str
    ssid: str
    is_connected: bool = False


# ==============================================================================
# Wireless Stack Manager (wpa_supplicant / wpa_cli / D-Bus)
# ==============================================================================
class WifiManager:
    """Manages wireless interface discovery, scanning, and connection."""

    def __init__(self):
        self.wpa_cli = self._find_binary("wpa_cli", ["/sbin/wpa_cli", "/usr/sbin/wpa_cli"])
        self.iw = self._find_binary("iw", ["/sbin/iw", "/usr/sbin/iw"])
        self.iface = self._detect_interface()
        self._ensure_ctrl_socket()

    def _find_binary(self, name: str, fallback_paths: list[str]) -> str:
        found = shutil.which(name)
        if found:
            return found
        for p in fallback_paths:
            if os.path.exists(p) and os.access(p, os.X_OK):
                return p
        return name

    def _detect_interface(self) -> str:
        # Check /sys/class/net for wireless interface
        net_dir = "/sys/class/net"
        if os.path.exists(net_dir):
            for dev in os.listdir(net_dir):
                if os.path.exists(os.path.join(net_dir, dev, "wireless")) or os.path.exists(os.path.join(net_dir, dev, "phy80211")):
                    return dev

        # Fallback to checking `iw dev`
        if self.iw:
            try:
                out = subprocess.check_output([self.iw, "dev"], text=True, stderr=subprocess.DEVNULL)
                for line in out.splitlines():
                    line = line.strip()
                    if line.startswith("Interface "):
                        return line.split()[1]
            except Exception:
                pass

        return "wlp3s0"

    def _ensure_ctrl_socket(self):
        """Ensure wpa_supplicant control socket exists in /run/wpa_supplicant."""
        sock_path = f"/run/wpa_supplicant/{self.iface}"
        if os.path.exists(sock_path):
            return

        # Attempt to create interface in wpa_supplicant via D-Bus fi.w1.wpa_supplicant1
        busctl = shutil.which("busctl")
        if busctl:
            try:
                subprocess.run(
                    [
                        busctl, "call",
                        "fi.w1.wpa_supplicant1",
                        "/fi/w1/wpa_supplicant1",
                        "fi.w1.wpa_supplicant1",
                        "CreateInterface",
                        "a{sv}", "1", "Ifname", "s", self.iface,
                    ],
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=3,
                )
            except Exception:
                pass

    def run_cli(self, args: list[str], timeout: int = 5, stdin_data: str | None = None) -> subprocess.CompletedProcess:
        """Run wpa_cli with current interface."""
        self._ensure_ctrl_socket()
        cmd = [self.wpa_cli, "-i", self.iface] + args
        try:
            return subprocess.run(
                cmd,
                input=stdin_data,
                capture_output=True,
                text=True,
                check=False,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            return subprocess.CompletedProcess(
                args=cmd,
                returncode=124,
                stdout="",
                stderr="wpa_cli command timed out",
            )
        except Exception as e:
            return subprocess.CompletedProcess(
                args=cmd,
                returncode=1,
                stdout="",
                stderr=str(e),
            )

    def get_status(self) -> dict:
        """Fetch connection status from wpa_cli."""
        res = self.run_cli(["status"])
        status = {
            "wpa_state": "DISCONNECTED",
            "ssid": "",
            "bssid": "",
            "ip_address": "",
            "freq": "",
        }
        if res.returncode == 0:
            for line in res.stdout.splitlines():
                if "=" in line:
                    k, v = line.split("=", 1)
                    status[k.strip()] = v.strip()
        return status

    def scan_networks(self) -> list[NetworkInfo]:
        """Trigger scan and parse scan_results from wpa_cli."""
        # 1. Trigger scan
        self.run_cli(["scan"], timeout=3)
        # Give hardware ~1.2s to capture beacons
        time.sleep(1.2)

        # 2. Get status to identify connected network
        current_status = self.get_status()
        connected_bssid = current_status.get("bssid", "").lower()
        connected_ssid = current_status.get("ssid", "")

        # 3. Retrieve scan results
        res = self.run_cli(["scan_results"], timeout=5)
        networks: list[NetworkInfo] = []

        if res.returncode == 0:
            lines = res.stdout.strip().split("\n")
            # Format: bssid / frequency / signal level / flags / ssid
            for line in lines[1:]:
                if not line.strip():
                    continue
                parts = line.split("\t")
                if len(parts) >= 5:
                    bssid = parts[0].strip()
                    freq_str = parts[1].strip()
                    sig_str = parts[2].strip()
                    flags = parts[3].strip()
                    ssid = parts[4].strip()
                elif len(parts) == 4:
                    bssid = parts[0].strip()
                    freq_str = parts[1].strip()
                    sig_str = parts[2].strip()
                    flags = parts[3].strip()
                    ssid = ""
                else:
                    continue

                try:
                    freq = int(freq_str)
                    sig_dbm = int(sig_str)
                except ValueError:
                    continue

                ch, band = freq_to_channel_and_band(freq)
                sig_pct = dbm_to_pct(sig_dbm)
                sec = parse_security_flags(flags)
                is_conn = (
                    (connected_bssid and bssid.lower() == connected_bssid)
                    or (connected_ssid and ssid == connected_ssid and current_status.get("wpa_state") == "COMPLETED")
                )

                networks.append(
                    NetworkInfo(
                        bssid=bssid,
                        freq=freq,
                        channel=ch,
                        band=band,
                        signal_dbm=sig_dbm,
                        signal_pct=sig_pct,
                        flags=flags,
                        security=sec,
                        ssid=ssid if ssid else "<Hidden Network>",
                        is_connected=is_conn,
                    )
                )

        # Sort: connected network first, then strongest signal (highest dBm / closest proximity)
        networks.sort(key=lambda n: (1 if n.is_connected else 0, n.signal_dbm), reverse=True)
        return networks

    def connect(self, net: NetworkInfo, passphrase: str | None = None) -> tuple[bool, str]:
        """Configure wpa_supplicant and connect to specified network."""
        # 1. Check existing networks in wpa_supplicant
        list_res = self.run_cli(["list_networks"])
        net_id = None
        if list_res.returncode == 0:
            for line in list_res.stdout.splitlines()[1:]:
                parts = line.split("\t")
                if len(parts) >= 2 and parts[1].strip() == net.ssid:
                    net_id = parts[0].strip()
                    break

        # 2. If not found, add a new network block
        if net_id is None:
            if net.ssid == "<Hidden Network>":
                return False, "Cannot connect directly to unnamed hidden network without SSID."
            add_res = self.run_cli(["add_network"])
            if add_res.returncode != 0 or not add_res.stdout.strip().isdigit():
                return False, f"Failed to allocate network block: {add_res.stderr.strip()}"
            net_id = add_res.stdout.strip()

        # 3. Configure network parameters
        clean_ssid = net.ssid.replace('\r', '').replace('\n', '')
        escaped_ssid = clean_ssid.replace('\\', '\\\\').replace('"', '\\"')

        clean_pass = passphrase.replace('\r', '').replace('\n', '') if passphrase else ""
        escaped_pass = clean_pass.replace('\\', '\\\\').replace('"', '\\"') if clean_pass else ""

        commands = [
            f'set_network {net_id} ssid "{escaped_ssid}"'
        ]

        if net.security == "Open":
            commands.append(f'set_network {net_id} key_mgmt NONE')
        elif net.security == "WPA3":
            commands.append(f'set_network {net_id} key_mgmt SAE')
            if clean_pass:
                commands.append(f'set_network {net_id} sae_password "{escaped_pass}"')
            commands.append(f'set_network {net_id} ieee80211w 2')
        elif net.security == "WPA2/WPA3":
            commands.append(f'set_network {net_id} key_mgmt WPA-PSK SAE')
            if clean_pass:
                commands.append(f'set_network {net_id} psk "{escaped_pass}"')
            commands.append(f'set_network {net_id} ieee80211w 1')
        else:  # WPA / WPA2
            commands.append(f'set_network {net_id} key_mgmt WPA-PSK')
            if clean_pass:
                commands.append(f'set_network {net_id} psk "{escaped_pass}"')

        commands.extend([
            f'enable_network {net_id}',
            f'select_network {net_id}',
            'reassociate',
            'quit'
        ])

        batch_input = "\n".join(commands) + "\n"
        self.run_cli([], stdin_data=batch_input)

        # 5. Monitor association for up to 14 seconds
        start_time = time.time()
        while time.time() - start_time < 14:
            time.sleep(1.0)
            st = self.get_status()
            wpa_state = st.get("wpa_state", "")
            if wpa_state == "COMPLETED":
                # Save configuration
                self.run_cli(["save_config"])
                return True, f"Successfully connected to {net.ssid}"
            elif wpa_state in ("DISCONNECTED", "INACTIVE") and (time.time() - start_time > 8):
                # Check if authentication failed
                break

        return False, "Connection failed: Authentication timeout or rejected passphrase."

    def disconnect(self) -> tuple[bool, str]:
        """Disconnect from currently active wireless network."""
        res = self.run_cli(["disconnect"])
        if res.returncode == 0:
            return True, "Disconnected from Wi-Fi"
        return False, f"Disconnect failed: {res.stderr.strip()}"


# ==============================================================================
# UI Component: Network Card
# ==============================================================================
class NetworkCard:
    """Card representing a single Wi-Fi access point in the scrollable view."""

    def __init__(self, parent, net: NetworkInfo, on_click_cb, on_connect_cb):
        self.parent = parent
        self.net = net
        self.on_click = on_click_cb
        self.on_connect = on_connect_cb
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

        self.inner = tk.Frame(self.card, bg=THEME["bg_card"])
        self.inner.pack(fill="x", padx=12, pady=8)

        # ----------------------------------------------------------------------
        # Top Row: Security / Status Badge + SSID + Signal Strength Metric Pill
        # ----------------------------------------------------------------------
        top_row = tk.Frame(self.inner, bg=THEME["bg_card"])
        top_row.pack(fill="x")

        # Status or Security Badge
        if self.net.is_connected:
            badge_text = "● CONNECTED"
            badge_color = THEME["status_running"]
        elif self.net.security == "WPA3":
            badge_text = "WPA3-SAE"
            badge_color = THEME["accent_purple"]
        elif self.net.security == "WPA2/WPA3":
            badge_text = "WPA2/3"
            badge_color = THEME["accent_aqua"]
        elif self.net.security == "WPA2":
            badge_text = "WPA2"
            badge_color = THEME["accent_blue"]
        elif self.net.security == "WPA":
            badge_text = "WPA"
            badge_color = THEME["accent_orange"]
        elif self.net.security == "Open":
            badge_text = "OPEN"
            badge_color = THEME["accent_aqua"]
        else:
            badge_text = self.net.security
            badge_color = THEME["fg_dim"]

        self.lbl_badge = tk.Label(
            top_row,
            text=f" {badge_text} ",
            font=("DejaVu Sans Mono", 9, "bold"),
            fg=badge_color,
            bg=THEME["key_bg"],
            padx=6,
            pady=2,
        )
        self.lbl_badge.pack(side="left")

        # SSID Label
        is_hidden = self.net.ssid == "<Hidden Network>"
        ssid_fg = THEME["fg_dim"] if is_hidden else THEME["fg_header"]
        ssid_font = ("DejaVu Sans Mono", 11, "italic" if is_hidden else "bold")

        self.lbl_ssid = tk.Label(
            top_row,
            text=self.net.ssid,
            font=ssid_font,
            fg=ssid_fg,
            bg=THEME["bg_card"],
            padx=10,
        )
        self.lbl_ssid.pack(side="left")

        # Numerical Signal Strength Pill (dBm and percentage for exact proximity assessment)
        dbm = self.net.signal_dbm
        pct = self.net.signal_pct
        if dbm >= -60:
            sig_color = THEME["status_running"]
        elif dbm >= -75:
            sig_color = THEME["accent_yellow"]
        else:
            sig_color = THEME["status_stopped"]

        sig_text = f"{dbm} dBm ({pct}%)"
        self.lbl_signal = tk.Label(
            top_row,
            text=sig_text,
            font=("DejaVu Sans Mono", 9, "bold"),
            fg=sig_color,
            bg=THEME["key_bg"],
            padx=8,
            pady=2,
        )
        self.lbl_signal.pack(side="right")

        # ----------------------------------------------------------------------
        # Bottom Row: BSSID (MAC), Channel/Band, Frequency, Action Hint
        # ----------------------------------------------------------------------
        bot_row = tk.Frame(self.inner, bg=THEME["bg_card"])
        bot_row.pack(fill="x", pady=(6, 0))

        # Endpoint BSSID
        self.lbl_bssid = tk.Label(
            bot_row,
            text=f"BSSID: {self.net.bssid}",
            font=("DejaVu Sans Mono", 9),
            fg=THEME["fg_dim"],
            bg=THEME["bg_card"],
        )
        self.lbl_bssid.pack(side="left")

        # Channel & Band
        ch_str = f"Ch {self.net.channel} ({self.net.freq / 1000.0:.3f} GHz)  |  {self.net.band}"
        self.lbl_channel = tk.Label(
            bot_row,
            text=ch_str,
            font=("DejaVu Sans Mono", 9),
            fg=THEME["accent_blue"],
            bg=THEME["bg_card"],
            padx=12,
        )
        self.lbl_channel.pack(side="left")

        # Action Button / Indicator
        action_text = "Active" if self.net.is_connected else "Connect [Enter]"
        action_fg = THEME["status_running"] if self.net.is_connected else THEME["key_fg"]
        self.lbl_action = tk.Label(
            bot_row,
            text=action_text,
            font=("DejaVu Sans Mono", 9, "bold" if self.net.is_connected else "normal"),
            fg=action_fg,
            bg=THEME["bg_card"],
        )
        self.lbl_action.pack(side="right")

        self._bind_clicks()

    def _bind_clicks(self):
        widgets = [
            self.card, self.inner, self.lbl_badge, self.lbl_ssid,
            self.lbl_signal, self.lbl_bssid, self.lbl_channel, self.lbl_action
        ]
        for w in widgets:
            w.bind("<Button-1>", lambda e: self.on_click(self))
            w.bind("<Double-Button-1>", lambda e: self.on_connect(self))

    def set_selected(self, selected: bool):
        self.is_selected = selected
        bg = THEME["bg_selected"] if selected else THEME["bg_card"]
        border = THEME["border_focus"] if selected else THEME["border"]

        self.card.configure(highlightbackground=border, bg=bg)
        self.inner.configure(bg=bg)
        for w in [self.lbl_ssid, self.lbl_bssid, self.lbl_channel, self.lbl_action]:
            w.configure(bg=bg)


# ==============================================================================
# Modal Dialog: Passphrase Prompt
# ==============================================================================
class PassphraseModal:
    """Centered modal overlay for entering Wi-Fi network password."""

    def __init__(self, parent, net: NetworkInfo, on_submit_cb, on_cancel_cb):
        self.parent = parent
        self.net = net
        self.on_submit = on_submit_cb
        self.on_cancel = on_cancel_cb

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(f"Connect to {net.ssid}")
        self.dialog.configure(bg=THEME["bg_surface"])
        self.dialog.transient(parent)
        self.dialog.grab_set()

        # Center in parent window
        pw = parent.winfo_width()
        ph = parent.winfo_height()
        px = parent.winfo_rootx()
        py = parent.winfo_rooty()
        dw = 500
        dh = 240
        dx = px + max(0, (pw - dw) // 2)
        dy = py + max(0, (ph - dh) // 2)
        self.dialog.geometry(f"{dw}x{dh}+{dx}+{dy}")
        self.dialog.resizable(False, False)

        container = tk.Frame(
            self.dialog,
            bg=THEME["bg_card"],
            bd=0,
            highlightthickness=2,
            highlightbackground=THEME["border_focus"],
        )
        container.pack(fill="both", expand=True, padx=8, pady=8)

        # Title / SSID Header
        lbl_title = tk.Label(
            container,
            text=f"Connect to {net.ssid}",
            font=("DejaVu Sans Mono", 12, "bold"),
            fg=THEME["fg_header"],
            bg=THEME["bg_card"],
        )
        lbl_title.pack(anchor="w", padx=16, pady=(14, 4))

        # Details subtitle
        info_str = f"Security: {net.security}  |  Signal: {net.signal_dbm} dBm ({net.signal_pct}%)  |  Band: {net.band}"
        lbl_info = tk.Label(
            container,
            text=info_str,
            font=("DejaVu Sans Mono", 9),
            fg=THEME["fg_dim"],
            bg=THEME["bg_card"],
        )
        lbl_info.pack(anchor="w", padx=16, pady=(0, 12))

        # Password input box
        input_frame = tk.Frame(
            container,
            bg=THEME["bg_surface"],
            bd=1,
            highlightthickness=1,
            highlightbackground=THEME["border"],
        )
        input_frame.pack(fill="x", padx=16, pady=4, ipady=4)

        self.show_password = False
        self.entry_pass = tk.Entry(
            input_frame,
            font=("DejaVu Sans Mono", 11),
            fg=THEME["fg"],
            bg=THEME["bg_surface"],
            insertbackground=THEME["key_fg"],
            show="•",
            bd=0,
            highlightthickness=0,
        )
        self.entry_pass.pack(side="left", fill="x", expand=True, padx=8)

        self.btn_toggle = tk.Button(
            input_frame,
            text="Show",
            font=("DejaVu Sans Mono", 8),
            fg=THEME["key_fg"],
            bg=THEME["key_bg"],
            activebackground=THEME["bg_hover"],
            activeforeground=THEME["key_fg"],
            bd=0,
            padx=6,
            pady=2,
            command=self._toggle_show,
            cursor="hand2",
        )
        self.btn_toggle.pack(side="right", padx=6)

        # Action Buttons Row
        btn_row = tk.Frame(container, bg=THEME["bg_card"])
        btn_row.pack(fill="x", padx=16, pady=(16, 12))

        btn_cancel = tk.Button(
            btn_row,
            text="Cancel [Esc]",
            font=("DejaVu Sans Mono", 9),
            fg=THEME["fg_dim"],
            bg=THEME["bg_surface"],
            activebackground=THEME["bg_hover"],
            activeforeground=THEME["fg"],
            bd=0,
            padx=12,
            pady=4,
            command=self._cancel,
            cursor="hand2",
        )
        btn_cancel.pack(side="right", padx=(8, 0))

        btn_connect = tk.Button(
            btn_row,
            text="Connect [Enter]",
            font=("DejaVu Sans Mono", 9, "bold"),
            fg=THEME["key_bg"],
            bg=THEME["status_running"],
            activebackground=THEME["accent_green"],
            activeforeground=THEME["key_bg"],
            bd=0,
            padx=14,
            pady=4,
            command=self._submit,
            cursor="hand2",
        )
        btn_connect.pack(side="right")

        # Keyboard bindings
        self.dialog.bind("<Return>", lambda e: self._submit())
        self.dialog.bind("<Escape>", lambda e: self._cancel())

        self.entry_pass.focus_set()

    def _toggle_show(self):
        self.show_password = not self.show_password
        self.entry_pass.configure(show="" if self.show_password else "•")
        self.btn_toggle.configure(text="Hide" if self.show_password else "Show")

    def _submit(self):
        pwd = self.entry_pass.get()
        self.dialog.destroy()
        self.on_submit(pwd)

    def _cancel(self):
        self.dialog.destroy()
        self.on_cancel()


# ==============================================================================
# Main Application Window: WifiPadApp
# ==============================================================================
class WifiPadApp:
    """Main Wi-Fi Scratchpad Application."""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Wi-Fi Networks")
        self.root.configure(bg=THEME["bg"])

        try:
            self.root.wm_attributes("-type", "dialog")
        except Exception:
            pass

        # Set initial dimensions to match Qtile DropDown proportions
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        target_w = min(1500, int(sw * 0.8))
        target_h = int(sh * 0.88)
        self.root.geometry(f"{target_w}x{target_h}")

        self.wifi = WifiManager()
        self.networks: list[NetworkInfo] = []
        self.filtered_networks: list[NetworkInfo] = []
        self.cards: list[NetworkCard] = []
        self.selected_index = 0
        self.is_scanning = False
        self.is_connecting = False
        self.active_modal: PassphraseModal | None = None

        self._build_header()
        self._build_content_area()
        self._build_footer()
        self._bind_keys()

        # Initial background scan on launch
        self.refresh_networks()

    # --------------------------------------------------------------------------
    # Header Bar
    # --------------------------------------------------------------------------
    def _build_header(self):
        header_bar = tk.Frame(
            self.root,
            bg=THEME["bg_card"],
            bd=0,
            highlightthickness=1,
            highlightbackground=THEME["border"],
        )
        header_bar.pack(fill="x", padx=12, pady=(12, 4), ipady=8)

        # Title & Interface Badge
        title_box = tk.Frame(header_bar, bg=THEME["bg_card"])
        title_box.pack(side="left", padx=12)

        lbl_title = tk.Label(
            title_box,
            text="WI-FI NETWORKS",
            font=("DejaVu Sans Mono", 12, "bold"),
            fg=THEME["fg_header"],
            bg=THEME["bg_card"],
        )
        lbl_title.pack(side="left")

        lbl_iface = tk.Label(
            title_box,
            text=f" [{self.wifi.iface}] ",
            font=("DejaVu Sans Mono", 9, "bold"),
            fg=THEME["accent_aqua"],
            bg=THEME["key_bg"],
            padx=4,
            pady=1,
        )
        lbl_iface.pack(side="left", padx=(8, 0))

        # Search / Filter Bar
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
            text="Filter (/):",
            font=("DejaVu Sans Mono", 9, "bold"),
            fg=THEME["key_fg"],
            bg=THEME["bg_surface"],
        )
        lbl_search_icon.pack(side="left", padx=(8, 4))

        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *args: self._filter_networks())

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

        # Current Connection Pill / Counter
        self.lbl_counts = tk.Label(
            header_bar,
            text="Scanning...",
            font=("DejaVu Sans Mono", 10, "bold"),
            fg=THEME["fg"],
            bg=THEME["bg_card"],
            padx=12,
        )
        self.lbl_counts.pack(side="right")

    # --------------------------------------------------------------------------
    # Content Area: Scrollable Card Canvas
    # --------------------------------------------------------------------------
    def _build_content_area(self):
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

        # Mouse wheel & touchpad scrolling
        self.root.bind_all("<Button-4>", lambda e: self.canvas.yview_scroll(-2, "units"))
        self.root.bind_all("<Button-5>", lambda e: self.canvas.yview_scroll(2, "units"))
        self.root.bind_all("<MouseWheel>", lambda e: self.canvas.yview_scroll(-1 if e.delta > 0 else 1, "units"))

    # --------------------------------------------------------------------------
    # Footer: Keybindings Bar & Live Toast
    # --------------------------------------------------------------------------
    def _build_footer(self):
        footer = tk.Frame(
            self.root,
            bg=THEME["bg_card"],
            bd=0,
            highlightthickness=1,
            highlightbackground=THEME["border"],
        )
        footer.pack(fill="x", side="bottom", padx=12, pady=(4, 12), ipady=5)

        hints = [
            ("j/k", "Navigate"),
            ("Enter", "Connect"),
            ("r", "Rescan"),
            ("d", "Disconnect"),
            ("/", "Filter"),
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

        # Live Toast Label
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

    # --------------------------------------------------------------------------
    # Scan & Render Networks
    # --------------------------------------------------------------------------
    def refresh_networks(self):
        """Trigger asynchronous background scan without blocking UI."""
        if self.is_scanning or self.is_connecting:
            return
        self.is_scanning = True
        self.show_toast("Scanning Wi-Fi frequencies...", THEME["accent_blue"])
        self.lbl_counts.configure(text="Scanning...")

        def _worker():
            nets = self.wifi.scan_networks()
            self.root.after(0, lambda: self._on_scan_finished(nets))

        t = threading.Thread(target=_worker, daemon=True)
        t.start()

    def _on_scan_finished(self, nets: list[NetworkInfo]):
        self.is_scanning = False
        self.networks = nets
        self._filter_networks()

        connected_net = next((n for n in nets if n.is_connected), None)
        if connected_net:
            st = self.wifi.get_status()
            ip = st.get("ip_address", "")
            ip_str = f" ({ip})" if ip else ""
            self.show_toast(f"Connected to {connected_net.ssid}{ip_str}", THEME["status_running"])
            self.lbl_counts.configure(text=f"● {connected_net.ssid} | {len(nets)} APs", fg=THEME["status_running"])
        else:
            self.show_toast(f"Found {len(nets)} access points", THEME["accent_aqua"])
            self.lbl_counts.configure(text=f"{len(nets)} Networks", fg=THEME["fg"])

    def _filter_networks(self):
        query = self.search_var.get().strip().lower()
        if not query:
            self.filtered_networks = list(self.networks)
        else:
            self.filtered_networks = [
                n for n in self.networks
                if query in n.ssid.lower() or query in n.bssid.lower() or query in n.security.lower()
            ]

        self._render_cards()

    def _render_cards(self):
        for widget in self.content_frame.winfo_children():
            widget.destroy()
        self.cards.clear()

        if not self.filtered_networks:
            empty_frame = tk.Frame(self.content_frame, bg=THEME["bg"])
            empty_frame.pack(fill="both", expand=True, pady=60)
            msg = "No matching networks found" if self.search_var.get() else "No Wi-Fi access points detected in range."
            lbl_empty = tk.Label(
                empty_frame,
                text=msg,
                font=("DejaVu Sans Mono", 12),
                fg=THEME["fg_dim"],
                bg=THEME["bg"],
            )
            lbl_empty.pack()
            lbl_hint = tk.Label(
                empty_frame,
                text="Press 'r' to trigger an active RF rescan",
                font=("DejaVu Sans Mono", 9),
                fg=THEME["key_fg"],
                bg=THEME["bg"],
                pady=8,
            )
            lbl_hint.pack()
            self.selected_index = 0
            return

        for net in self.filtered_networks:
            card = NetworkCard(
                self.content_frame,
                net,
                on_click_cb=self._select_card,
                on_connect_cb=self._initiate_connection,
            )
            self.cards.append(card)

        # Maintain or clamp selection
        if self.cards:
            self.selected_index = max(0, min(self.selected_index, len(self.cards) - 1))
            self._select_card(self.cards[self.selected_index])
        else:
            self.selected_index = 0

        self.root.update_idletasks()
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _select_card(self, card: NetworkCard):
        for idx, c in enumerate(self.cards):
            if c == card:
                c.set_selected(True)
                self.selected_index = idx
            else:
                c.set_selected(False)

        # Scroll into view if needed
        if card and hasattr(card, "card"):
            self.root.update_idletasks()
            card_top = card.card.winfo_y()
            card_bot = card_top + card.card.winfo_height()
            canvas_h = self.canvas.winfo_height()
            top_visible = self.canvas.canvasy(0)
            bot_visible = top_visible + canvas_h
            content_h = max(1, self.content_frame.winfo_height())
            if card_top < top_visible:
                self.canvas.yview_moveto(card_top / content_h)
            elif card_bot > bot_visible:
                self.canvas.yview_moveto(max(0.0, (card_bot - canvas_h) / content_h))

    # --------------------------------------------------------------------------
    # Connection Flow
    # --------------------------------------------------------------------------
    def _initiate_connection(self, card: NetworkCard):
        if self.is_connecting or not card:
            return

        net = card.net
        if net.is_connected:
            self.show_toast(f"Already connected to {net.ssid}", THEME["status_running"])
            return

        if net.security == "Open":
            self._execute_connect(net, None)
        else:
            # Prompt for passphrase via modal
            self.active_modal = PassphraseModal(
                self.root,
                net,
                on_submit_cb=lambda pwd: self._execute_connect(net, pwd),
                on_cancel_cb=self._on_modal_close,
            )

    def _on_modal_close(self):
        self.active_modal = None
        self.root.focus_set()

    def _execute_connect(self, net: NetworkInfo, passphrase: str | None):
        self.active_modal = None
        self.is_connecting = True
        self.show_toast(f"Connecting to {net.ssid}...", THEME["accent_yellow"])

        def _worker():
            success, msg = self.wifi.connect(net, passphrase)
            self.root.after(0, lambda: self._on_connect_finished(success, msg))

        t = threading.Thread(target=_worker, daemon=True)
        t.start()

    def _on_connect_finished(self, success: bool, msg: str):
        self.is_connecting = False
        color = THEME["status_running"] if success else THEME["status_stopped"]
        self.show_toast(msg, color)
        # Rescan to update connection status
        self.refresh_networks()

    def action_disconnect(self):
        """Disconnect from Wi-Fi."""
        if self.is_connecting:
            return
        self.show_toast("Disconnecting...", THEME["accent_yellow"])

        def _worker():
            ok, msg = self.wifi.disconnect()
            self.root.after(0, lambda: self._on_disconnect_finished(ok, msg))

        t = threading.Thread(target=_worker, daemon=True)
        t.start()

    def _on_disconnect_finished(self, success: bool, msg: str):
        color = THEME["status_running"] if success else THEME["status_stopped"]
        self.show_toast(msg, color)
        self.refresh_networks()

    # --------------------------------------------------------------------------
    # Keyboard Bindings & Vim Navigation
    # --------------------------------------------------------------------------
    def _bind_keys(self):
        self.root.bind("<Escape>", self._on_escape)
        self.root.bind("q", self._on_q)
        self.root.bind("<slash>", self._on_slash)
        self.root.bind("j", lambda e: self._navigate(1))
        self.root.bind("k", lambda e: self._navigate(-1))
        self.root.bind("<Down>", lambda e: self._navigate(1))
        self.root.bind("<Up>", lambda e: self._navigate(-1))
        self.root.bind("<Return>", lambda e: self._on_enter())
        self.root.bind("r", lambda e: self.refresh_networks() if self._is_normal_mode() else None)
        self.root.bind("d", lambda e: self.action_disconnect() if self._is_normal_mode() else None)

    def _is_normal_mode(self) -> bool:
        return self.root.focus_get() != self.search_entry and self.active_modal is None

    def _navigate(self, delta: int):
        if not self._is_normal_mode() or not self.cards:
            return
        new_idx = max(0, min(len(self.cards) - 1, self.selected_index + delta))
        if new_idx != self.selected_index:
            self._select_card(self.cards[new_idx])

    def _on_enter(self):
        if self.active_modal:
            return
        if self.root.focus_get() == self.search_entry:
            # Shift focus back to list on Enter in search
            self.root.focus_set()
            return
        if self.cards and 0 <= self.selected_index < len(self.cards):
            self._initiate_connection(self.cards[self.selected_index])

    def _on_escape(self, event):
        if self.active_modal:
            self.active_modal._cancel()
        elif self.root.focus_get() == self.search_entry:
            if self.search_var.get():
                self.search_var.set("")
            self.root.focus_set()
        else:
            self.root.destroy()

    def _on_q(self, event):
        if self.active_modal:
            return
        if self._is_normal_mode():
            self.root.destroy()

    def _on_slash(self, event):
        if self._is_normal_mode():
            self.search_entry.focus_set()
            self.search_entry.select_range(0, "end")
            return "break"


# ==============================================================================
# Application Entry Point
# ==============================================================================
def main():
    root = tk.Tk(className="wifi-pad")
    app = WifiPadApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
