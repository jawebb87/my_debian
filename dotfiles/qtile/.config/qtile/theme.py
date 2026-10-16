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
    "bg_surface": "#ebdbb2",   # Darker parchment surface framing
    "bg_card": "#fbf1c7",      # Clean ivory elevated paper card (13.0:1 text contrast!)
    "bg_hover": "#ebdbb2",     # Warm parchment hover
    "bg_active": "#d5c4a1",    # Active selection
    "bg_selected": "#ebdbb2",  # Selected card surface
    "border": "#d5c4a1",       # Soft warm parchment border
    "border_focus": "#076678", # Deep teal/blue accent border (5.25:1)
    "border_today": "#9d3202", # Warm rust/amber border for Today (5.3:1)
    "fg": "#3c3836",           # Dark charcoal ink text (10.2:1 on card)
    "fg_dim": "#504945",       # Muted ink text (7.8:1 on card, 7.0:1 on bg)
    "fg_header": "#282828",    # Deep contrast ink text (13.0:1 on card)
    "key_bg": "#282828",       # Crisp physical keycap badge background (13.0:1)
    "key_fg": "#fbf1c7",       # Warm ivory text for key badges
    "status_running": "#425e0b", # Deep forest/moss green (6.5:1 on card)
    "status_stopped": "#9d0006", # Deep crimson red (7.6:1 on card)
    "status_paused": "#8f4a00",  # Deep golden bronze/amber (5.9:1 on card)
    "accent_blue": "#076678",  # Deep teal/blue accent (5.8:1 on card)
    "accent_aqua": "#1b6348",  # Deep pine aqua accent (6.3:1 on card)
    "accent_green": "#425e0b", # Success accent (6.5:1 on card)
    "accent_yellow": "#8f4a00",# Golden amber accent (5.9:1 on card)
    "accent_orange": "#af3a03",# Burnt orange accent (5.4:1 on card)
    "accent_purple": "#8f3f71",# Deep plum purple accent (5.9:1 on card)
    "accent_red": "#9d0006",   # Danger accent (7.6:1 on card)
}

GRUVBOX_DARK_COLORS = {
    "bg": "#282828",
    "fg": "#ebdbb2",
    "pill_fg": "#282828",       # Dark text on colored pills (preserving dark perfection)
    "pill_notice": "#fabd2f",   # Bright yellow text on dark_gray for updates & thermal
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
    "fg": "#282828",           # Deep dark charcoal ink text (11.7:1 contrast on parchment)
    "pill_fg": "#fbf1c7",      # Clean ivory text on deep colored status pills (5.5+:1 contrast)
    "pill_notice": "#9d3202",  # Deep rust amber for ThermalSensor & CheckUpdates (5.3:1 on dark_gray)
    "selection_bg": "#d5c4a1", # Warm tan selection/unfocused border
    "cursor": "#282828",
    "gray": "#504945",         # High-contrast muted text (6.4:1 on dark_gray, 7.0:1 on bg)
    "dark_gray": "#ebdbb2",    # Crisp parchment container surface for GroupBox/Clock/Systray
    "light_gray": "#7c6f64",
    "bright_red": "#9d0006",   # Deep crimson alert (7.6:1)
    "bright_green": "#425e0b", # Deep moss green (5.9:1)
    "bright_yellow": "#8f4a00",# Deep golden bronze/amber (5.3:1)
    "bright_blue": "#076678",  # Deep teal/blue (5.25:1)
    "bright_purple": "#8f3f71",# Deep plum purple (5.36:1)
    "bright_aqua": "#1b6348",  # Deep pine aqua (5.71:1)
    "neutral_red": "#9d0006",   # Rich red status pill (6.86:1 vs bar, 7.60:1 vs pill_fg)
    "neutral_green": "#425e0b", # Rich green status pill (5.89:1 vs bar, 6.52:1 vs pill_fg)
    "neutral_yellow": "#8f4a00",# Rich golden bronze status pill (5.31:1 vs bar, 5.88:1 vs pill_fg)
    "neutral_blue": "#076678",  # Rich blue status pill (5.25:1 vs bar, 5.82:1 vs pill_fg)
    "neutral_purple": "#8f3f71",# Rich purple status pill (5.36:1 vs bar, 5.94:1 vs pill_fg)
    "neutral_aqua": "#1b6348",  # Rich teal aqua status pill (5.71:1 vs bar, 6.33:1 vs pill_fg)
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


def get_wallpaper(mode: str | None = None) -> str | None:
    """Retrieve appropriate wallpaper path for dark/light mode from ~/Pictures."""
    if mode is None:
        mode = get_current_mode()
    pictures_dir = os.path.expanduser("~/Pictures")
    if mode == "light":
        candidates = [
            "light_wallpaper.png",
            "light_wallpaper.jpg",
            "light_wallpaper.jpeg",
            "wallpaper_light.png",
            "wallpaper_light.jpg",
        ]
    else:
        candidates = [
            "dark_wallpaper.png",
            "dark_wallpaper.jpg",
            "dark_wallpaper.jpeg",
            "wallpaper_dark.png",
            "wallpaper_dark.jpg",
        ]

    for name in candidates:
        candidate_path = os.path.join(pictures_dir, name)
        if os.path.exists(candidate_path):
            return candidate_path
    return None


def toggle_theme() -> str:
    """Flip between dark and light modes, update external apps, and return new mode."""
    current = get_current_mode()
    new_mode = "light" if current == "dark" else "dark"
    set_mode(new_mode)
    update_external_apps(new_mode)
    return new_mode


# Module-level aliases for convenient direct imports
THEME = get_theme()
COLORS = get_colors()
WALLPAPER = get_wallpaper()
