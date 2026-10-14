#!/usr/bin/env python3
"""
Central Theme Manager for Qtile & Desktop Dropdown Applications
===============================================================
Single source of truth for Gruvbox Dark and Gruvbox Light palettes.
Provides seamless live switching across:
- Qtile window manager bar & window borders
- All 7 bench dropdown scratchpads
- Kitty terminal (via SIGUSR1)
- Rofi application launcher
"""

import os
import json
import subprocess

STATE_FILE = os.path.expanduser("~/.config/qtile/theme_state.json")
KITTY_DIR = os.path.expanduser("~/.config/kitty")
ROFI_CONFIG = os.path.expanduser("~/.config/rofi/config.rasi")

# ==============================================================================
# Palettes: Gruvbox Dark & Gruvbox Light
# ==============================================================================
GRUVBOX_DARK_THEME = {
    "bg": "#282828",           # Dark0 background
    "bg_surface": "#32302f",   # Dark0_soft surface
    "bg_card": "#3c3836",      # Dark1 container
    "bg_hover": "#504945",     # Dark2 hover
    "bg_active": "#665c54",    # Dark3 active selection
    "bg_selected": "#3c3836",  # Dark1 selected
    "border": "#504945",       # Dark2 border
    "border_focus": "#83a598", # Bright blue border
    "border_today": "#fabd2f", # Bright yellow border for Today
    "fg": "#ebdbb2",           # Light1 main text
    "fg_dim": "#a89984",       # Light4 muted text
    "fg_header": "#fbf1c7",    # Light0 prominent text
    "key_bg": "#1d2021",       # Hard dark background for key badges
    "key_fg": "#fabd2f",       # Bright yellow for key text
    "status_running": "#b8bb26", # Bright green
    "status_stopped": "#fb4934", # Bright red
    "status_paused": "#fabd2f",  # Bright yellow
    "accent_blue": "#83a598",  # Information accent
    "accent_aqua": "#8ec07c",  # URL / code accent
    "accent_green": "#b8bb26", # Success accent
    "accent_yellow": "#fabd2f",# Yellow accent
    "accent_orange": "#fe8019",# Orange accent
    "accent_purple": "#d3869b",# Special accent
    "accent_red": "#fb4934",   # Danger accent
}

GRUVBOX_LIGHT_THEME = {
    "bg": "#f2e5bc",           # Gruvbox Soft parchment background
    "bg_surface": "#ebdbb2",   # Darker parchment surface
    "bg_card": "#e0d1a7",      # Container card / parchment paper
    "bg_hover": "#d5c4a1",     # Warm tan hover
    "bg_active": "#bdae93",    # Active selection
    "bg_selected": "#e0d1a7",  # Selected card
    "border": "#d5c4a1",       # Soft parchment border
    "border_focus": "#076678", # Deep teal/blue accent border
    "border_today": "#b57614", # Warm amber border for Today
    "fg": "#3c3836",           # Dark charcoal / ink text
    "fg_dim": "#7c6f64",       # Muted ink text
    "fg_header": "#282828",    # Deep contrast ink text
    "key_bg": "#d5c4a1",       # Parchment key badge background
    "key_fg": "#b57614",       # Warm amber for key text
    "status_running": "#79740e", # Deep green
    "status_stopped": "#9d0006", # Deep red
    "status_paused": "#b57614",  # Warm yellow
    "accent_blue": "#076678",  # Information accent
    "accent_aqua": "#427b58",  # URL / code accent
    "accent_green": "#79740e", # Success accent
    "accent_yellow": "#b57614",# Yellow accent
    "accent_orange": "#af3a03",# Orange accent
    "accent_purple": "#8f3f71",# Special accent
    "accent_red": "#9d0006",   # Danger accent
}

GRUVBOX_DARK_COLORS = {
    "bg": "#282828",
    "fg": "#ebdbb2",
    "selection_bg": "#665c54",
    "cursor": "#ebdbb2",
    "gray": "#928374",
    "dark_gray": "#3c3836",
    "light_gray": "#a89984",
    "bright_red": "#fb4934",
    "bright_green": "#b8bb26",
    "bright_yellow": "#fabd2f",
    "bright_blue": "#83a598",
    "bright_purple": "#d3869b",
    "bright_aqua": "#8ec07c",
    "neutral_red": "#cc241d",
    "neutral_green": "#98971a",
    "neutral_yellow": "#d79921",
    "neutral_blue": "#458588",
    "neutral_purple": "#b16286",
    "neutral_aqua": "#689d6a",
}

GRUVBOX_LIGHT_COLORS = {
    "bg": "#f2e5bc",           # Soft parchment background for top bar
    "fg": "#3c3836",           # Dark ink text
    "selection_bg": "#d5c4a1",
    "cursor": "#3c3836",
    "gray": "#7c6f64",
    "dark_gray": "#e0d1a7",    # Pill container surface
    "light_gray": "#928374",
    "bright_red": "#9d0006",
    "bright_green": "#79740e",
    "bright_yellow": "#b57614",
    "bright_blue": "#076678",
    "bright_purple": "#8f3f71",
    "bright_aqua": "#427b58",
    "neutral_red": "#cc241d",
    "neutral_green": "#98971a",
    "neutral_yellow": "#d79921",
    "neutral_blue": "#458588",
    "neutral_purple": "#b16286",
    "neutral_aqua": "#689d6a",
}


def get_current_mode() -> str:
    """Retrieve active theme mode ('dark' or 'light')."""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                mode = data.get("mode", "dark").lower()
                if mode in ("dark", "light"):
                    return mode
        except Exception:
            pass
    return "dark"


def set_mode(mode: str) -> None:
    """Save active theme mode."""
    mode = "light" if mode == "light" else "dark"
    try:
        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump({"mode": mode}, f, indent=2)
    except Exception:
        pass


def get_theme() -> dict:
    """Get Tkinter THEME dictionary for currently active mode."""
    mode = get_current_mode()
    return GRUVBOX_LIGHT_THEME.copy() if mode == "light" else GRUVBOX_DARK_THEME.copy()


def get_colors() -> dict:
    """Get Qtile COLORS dictionary for currently active mode."""
    mode = get_current_mode()
    return GRUVBOX_LIGHT_COLORS.copy() if mode == "light" else GRUVBOX_DARK_COLORS.copy()


def update_external_apps(mode: str):
    """Synchronize Kitty terminal, Rofi launcher, and running scratchpads."""
    # 1. Update Kitty configuration
    try:
        current_theme_link = os.path.join(KITTY_DIR, "current-theme.conf")
        target_theme = f"gruvbox-{mode}.conf"
        target_path = os.path.join(KITTY_DIR, target_theme)
        if os.path.exists(target_path):
            if os.path.islink(current_theme_link) or os.path.exists(current_theme_link):
                try:
                    os.remove(current_theme_link)
                except Exception:
                    pass
            os.symlink(target_theme, current_theme_link)

        # Notify active Kitty terminals via SIGUSR1 to reload palette live
        subprocess.run(["pkill", "-USR1", "-x", "kitty"], check=False)
    except Exception:
        pass

    # 2. Update Rofi theme
    try:
        rofi_theme = "gruvbox-light-soft.rasi" if mode == "light" else "gruvbox-dark.rasi"
        rofi_theme_path = f"/usr/share/rofi/themes/{rofi_theme}"
        if os.path.exists(rofi_theme_path):
            with open(ROFI_CONFIG, "w", encoding="utf-8") as f:
                f.write(f'@theme "{rofi_theme_path}"\n')
    except Exception:
        pass

    # 3. Terminate running dropdown pads so their next invocation loads the new palette
    try:
        subprocess.run(
            ["pkill", "-f", "(_pad\\.py|vim_cheat\\.py|key_cheat\\.py)"],
            check=False,
        )
    except Exception:
        pass

    # 4. Synchronize xdg-desktop-portal-gtk and GTK settings (for Firefox & web content)
    try:
        is_dark = (mode == "dark")
        color_scheme = "prefer-dark" if is_dark else "prefer-light"
        gtk_theme = "Adwaita-dark" if is_dark else "Adwaita"
        prefer_dark_int = 1 if is_dark else 0

        # Update GSettings via Gio (which xdg-desktop-portal-gtk monitors)
        from gi.repository import Gio
        settings = Gio.Settings(schema="org.gnome.desktop.interface")
        settings.set_string("color-scheme", color_scheme)
        settings.set_string("gtk-theme", gtk_theme)

        # Update GTK 3 & 4 settings.ini
        for gtk_ver in ("gtk-3.0", "gtk-4.0"):
            conf_dir = os.path.expanduser(f"~/.config/{gtk_ver}")
            conf_path = os.path.join(conf_dir, "settings.ini")
            os.makedirs(conf_dir, exist_ok=True)
            content = (
                "[Settings]\n"
                f"gtk-theme-name = {gtk_theme}\n"
                f"gtk-application-prefer-dark-theme = {prefer_dark_int}\n"
                "gtk-icon-theme-name = Adwaita\n"
                "gtk-font-name = DejaVu Sans 10\n"
            )
            with open(conf_path, "w", encoding="utf-8") as f:
                f.write(content)

        # Ping the FreeDesktop Portal over D-Bus to ensure immediate signal emission
        import dbus
        bus = dbus.SessionBus()
        portal = bus.get_object("org.freedesktop.portal.Desktop", "/org/freedesktop/portal/desktop")
        settings_iface = dbus.Interface(portal, "org.freedesktop.portal.Settings")
        settings_iface.Read("org.freedesktop.appearance", "color-scheme")
    except Exception:
        pass


def toggle_theme() -> str:
    """Flip between dark and light modes, update external apps, and return new mode."""
    current = get_current_mode()
    new_mode = "light" if current == "dark" else "dark"
    set_mode(new_mode)
    update_external_apps(new_mode)
    return new_mode


# Module-level alias for convenient direct imports
THEME = get_theme()
COLORS = get_colors()
