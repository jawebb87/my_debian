"""
Qtile Window Manager Configuration
==================================
This file is the master configuration for Qtile, a full-featured, hackable tiling
window manager written and configured entirely in Python.

Unlike traditional window managers that use static configuration languages (like JSON,
YAML, or custom DSLs like i3wm), Qtile configurations are executable Python programs.
When Qtile boots, its Python interpreter imports this file as a module and inspects
specific top-level variables (e.g. `keys`, `groups`, `layouts`, `screens`, `mouse`).

Architecture Overview:
----------------------
1. Event Loop & Asynchronous Model:
   Qtile runs on an asynchronous event loop (based on `asyncio` and `xcffib` for X11 / Wayland).
   It reacts to X11/Wayland events (keystrokes, mouse clicks, window creation/destruction).
2. The `lazy` Object (Deferred Execution):
   Because this file is executed at startup, functions cannot run immediately when parsed.
   Qtile uses a "lazy evaluation" command pattern (`libqtile.lazy.lazy`) which returns command
   descriptors. These descriptors are stored in data structures and only evaluated when the
   corresponding event actually occurs.
3. Extensibility via Pure Python:
   Any valid Python code can be embedded: helper functions, custom closures, regex matching,
   process spawning, and event hooks (Observer Pattern).
"""

import os
import re
import subprocess
import time
from libqtile import bar, hook, layout, qtile, widget
from libqtile.config import Click, Drag, DropDown, Group, Key, Match, ScratchPad, Screen
from libqtile.lazy import lazy
import theme

# Ensure user's local bin is in PATH for spawned processes
home_bin = os.path.expanduser("~/.local/bin")
if home_bin not in os.environ.get("PATH", ""):
    os.environ["PATH"] = f"{home_bin}:{os.environ.get('PATH', '')}"

# ==============================================================================
# SECTION 1: Modifier Keys
# ==============================================================================
# [What it does]:
# Defines readable aliases for keyboard modifier keys (Super/Windows, Alt, Ctrl, Shift).
#
# [Python Concepts]:
# - String variables: Assigning strings to identifiers avoids "magic strings" scattered
#   across the file. If you ever want to switch your primary mod key to Alt, you only
#   change `mod` here once (DRY: Don't Repeat Yourself).
#
# [Architecture Reasoning]:
# - X11/XKB Keymaps: In the X Window System, modifier keys are identified by symbolic names
#   like "mod4" (the 4th modifier mask, historically mapped to the Windows/Super key) and
#   "mod1" (historically mapped to the Alt key). Qtile uses these string identifiers to
#   register hardware key grabs via XGrabKey.
# ==============================================================================
mod = "mod4"      # Super / Windows key
alt = "mod1"      # Alt key
ctrl = "control"  # Control key
shift = "shift"   # Shift key


# ==============================================================================
# SECTION 2: Native Qtile Raise-or-Run Helper
# ==============================================================================
# Debounce tracker mapping spawn commands to their last invocation timestamp.
# Prevents asynchronous double-spawn race conditions when a hotkey is pressed rapidly
# before X11 emits the MapRequest event for the new client window.
_last_spawn_times: dict[str, float] = {}


def raise_or_run(match_terms, spawn_cmd, exclude_terms=None):
    """
    Pure Python raise-or-run without external C/wnck binaries.
    Focuses and raises matching window, cycling if multiple instances exist.
    If no matching window exists, spawns the application.

    [What it does]:
    Implements "Raise-or-Run" behavior (also known as "Quick Switcher"):
    - If the desired application isn't open, launch it (`spawn_cmd`).
    - If one instance is open, switch to its workspace, unminimize it, and focus it.
    - If multiple instances exist, cycle through each instance on subsequent keypresses.
    - If `exclude_terms` are provided, ignores matching utility windows (e.g., ignores
      a btop terminal when trying to switch to a general terminal).

    [Python Concepts]:
    1. Higher-Order Function:
       `raise_or_run` is a function that returns another function wrapped inside
       `lazy.function(_inner)`. This allows Qtile to treat it as a deferred command.
    2. Closures & Lexical Scoping:
       The nested function `_inner(qtile)` captures and remembers `match_terms`,
       `spawn_cmd`, and `exclude_terms` from the outer scope, even after `raise_or_run` finishes.
    3. Default Arguments & Ternary Operator:
       `exclude_terms=None` allows the argument to be optional.
       `[e.lower() for e in exclude_terms] if exclude_terms else []` is a ternary expression
       that converts strings to lowercase only if a list was supplied.
    4. List Comprehensions:
       `[t.lower() for t in match_terms]` creates a new transformed list in a single,
       idiomatic, high-performance C-level loop.
    5. Defensive Programming & Short-Circuit Evaluation:
       `(win.get_wm_class() or [])`: If `get_wm_class()` returns `None`, the `or` falls back
       to an empty list `[]`, preventing `TypeError: 'NoneType' object is not iterable`.
    6. Built-in `any()` with Generator Expressions:
       `any(...)` returns True as soon as the first matching condition evaluates to True,
       stopping evaluation immediately (lazy evaluation / short-circuiting).
    7. Circular Cycling with Modulo (`%`):
       `target_idx = (curr_idx + 1) % len(all_matches)` cleanly wraps back to index 0 when
       we reach the end of the list, creating an infinite circular buffer.
    8. Dynamic Property Introspection:
       `getattr(target_win, "minimized", False)` and `hasattr(target_win, "bring_to_front")`
       safely inspect objects at runtime without throwing `AttributeError`.

    [Architecture Reasoning]:
    Many window managers rely on external shell scripts calling external tools (`xdotool`,
    `wmctrl`, `xprop`) to find and focus windows. Spawning external processes is slow and can
    flicker. Because Qtile is a pure Python engine, its internal state machine (`qtile.groups`,
    `group.windows`, `qtile.current_group`) is directly exposed as live Python objects.
    We query the internal window manager tree directly in memory with zero overhead.
    """
    def _inner(qtile):
        now = time.monotonic()
        terms = [t.lower() for t in match_terms]
        excludes = [e.lower() for e in exclude_terms] if exclude_terms else []

        all_matches = []
        # Traverse the window manager's object hierarchy: Qtile -> Groups -> Windows
        for group in qtile.groups:
            # Skip hidden scratchpad workspace to prevent corrupting active screen groups
            if getattr(group, "name", "") == "scratchpad" or hasattr(group, "dropdowns"):
                continue

            for win in list(group.windows):
                # Ensure the window is still alive and managed by Qtile
                if not hasattr(win, "wid") or win.wid not in qtile.windows_map:
                    continue

                classes = [c.lower() for c in (win.get_wm_class() or [])]
                if not classes:
                    continue

                # Check exclusions against window class only (e.g. ignore btop scratchpad)
                if excludes and any(any(e in c for c in classes) for e in excludes):
                    continue

                # Check matches strictly against window class (not title, avoiding browser false matches)
                if any(any(t in c for c in classes) for t in terms):
                    all_matches.append((group, win))

        # Case 1: Application is not running -> spawn it with debounce guard
        if not all_matches:
            last_time = _last_spawn_times.get(spawn_cmd, 0.0)
            if now - last_time < 1.0:
                return
            _last_spawn_times[spawn_cmd] = now
            qtile.spawn(spawn_cmd)
            return

        # Case 2: Find if the currently focused window is one of our matches
        curr_win = qtile.current_window
        curr_idx = -1
        for i, (grp, win) in enumerate(all_matches):
            if win == curr_win:
                curr_idx = i
                break

        # Calculate next window to focus (cycles to next if already focused)
        target_idx = (curr_idx + 1) % len(all_matches)
        target_grp, target_win = all_matches[target_idx]

        # Ensure target window is still alive before focusing
        if not hasattr(target_win, "wid") or target_win.wid not in qtile.windows_map:
            return

        # Switch to the target window's group/workspace if on another screen/group
        if qtile.current_group != target_grp:
            target_grp.toscreen()

        # Unminimize the window if it was hidden
        if getattr(target_win, "minimized", False):
            target_win.toggle_minimize()

        # Direct window focus to the target safely
        try:
            target_grp.focus(target_win)
        except Exception:
            pass

        # Floating Z-Order Management:
        # Only bring floating windows to the front so tiled windows never obscure
        # floating/pinned miniplayers.
        if target_win.floating and hasattr(target_win, "bring_to_front"):
            target_win.bring_to_front()

    return lazy.function(_inner)


def toggle_columns_split_or_switch(qtile):
    """
    Toggles between horizontal split (multiple columns) and vertical split
    (single column stacked/tiled) when in the 'columns' layout.
    If the current group is not in 'columns' layout, switches directly to it.
    """
    group = qtile.current_group
    if not group:
        return

    # If not currently in columns layout, switch directly to it
    if group.layout.name != "columns":
        group.setlayout("columns")
        return

    layout = group.layout
    # In columns layout:
    # Case A: Multiple columns (horizontal split) -> collapse to 1 column (vertical split)
    if len(layout.columns) > 1:
        col0 = layout.columns[0]
        col0.split = True
        for col in list(layout.columns[1:]):
            for client in list(col.clients):
                col0.add_client(client)
                col.remove(client)
            if len(col) == 0 and col in layout.columns:
                layout.remove_column(col)
        layout.current = 0
        group.layout_all()
    # Case B: 1 column (vertical split) -> expand windows to separate columns (horizontal split)
    elif len(layout.columns) == 1:
        col0 = layout.columns[0]
        if len(col0.clients) > 1:
            for client in list(col0.clients[1:]):
                col0.remove(client)
                new_col = layout.add_column()
                new_col.add_client(client)
                new_col.split = True
            layout.current = 0
            group.layout_all()
        else:
            col0.split = not col0.split
            group.layout_all()


def toggle_desktop_theme(qtile):
    """
    Toggles the entire desktop environment between Gruvbox Dark and Gruvbox Light:
    - Flips state in ~/.config/qtile/theme_state.json
    - Switches Kitty terminal palette live via SIGUSR1
    - Updates Rofi theme between gruvbox-dark.rasi and gruvbox-light.rasi
    - Resets dropdown scratchpads to pick up the new palette on next launch
    - Hot-reloads Qtile in-place to update the top bar and window borders
    """
    new_mode = theme.toggle_theme()
    qtile.reload_config()



# ==============================================================================
# SECTION 3: Keybindings Configuration (`keys`)
# ==============================================================================
# [What it does]:
# Registers the keyboard shortcut table for the window manager.
#
# [Python Concepts]:
# - Python Lists (`[...]`): `keys` is a list containing instances of `libqtile.config.Key`.
# - Object Instantiation:
#   `Key(modifiers_list, key_string, lazy_command, desc="description")`
# - Keyword Arguments (`desc=...`): Used by Qtile to generate interactive cheat-sheets
#   or help documentation.
# - Method Chaining:
#   Expressions like `lazy.group["scratchpad"].dropdown_toggle("btop")` chain attribute
#   lookups and indexing to build complex command representations without executing them yet.
#
# [Architecture Reasoning]:
# - Event Grabbing (XGrabKey): Qtile loops over this `keys` list during initialization
#   and informs the X11 server to intercept these specific key events so they are delivered
#   directly to Qtile rather than passing through to individual application windows.
# - Categorization: Organized into Application Launchers, Standalone Tools, Screenshots,
#   Hardware/Media Keys (PipeWire / WirePlumber), Layout Navigation, Window Controls,
#   and Window Manager Lifecycle (Reload / Exit).
# ==============================================================================
keys = [
    # --------------------------------------------------------------------------
    # 4.1 Custom App Launchers (Native Raise-or-Run)
    # --------------------------------------------------------------------------
    Key([mod], "Return", raise_or_run(["kitty", "ghostty", "alacritty", "terminal", "foot", "xterm"], "kitty", exclude_terms=["btop", "term-scratch", "lazygit", "ranger", "ipython", "agy-pad", "fzf-pad", "zodiac-pad", "emoji-pad", "key-cheat", "wifi-pad", "notes-pad", "weather-pad", "log-pad"]), desc="Raise or run Kitty terminal"),
    Key([], "F12", lazy.group["scratchpad"].dropdown_toggle("term-scratch"), desc="Toggle scratchpad terminal (launch/show/hide)"),
    Key([mod], "F1", lazy.group["scratchpad"].dropdown_toggle("key-cheat"), desc="Toggle Qtile keybindings cheatsheet (launch/show/hide)"),
    Key([mod], "b", raise_or_run(["firefox", "navigator"], "firefox"), desc="Raise or run Firefox"),
    Key([mod], "f", lazy.group["scratchpad"].dropdown_toggle("fzf-pad"), desc="Toggle FZF file search dropdown"),
    Key([mod], "t", lazy.group["scratchpad"].dropdown_toggle("btop"), desc="Toggle btop scratchpad (launch/show/hide)"),
    Key([mod], "v", lazy.group["scratchpad"].dropdown_toggle("vim-cheat"), desc="Toggle Vim cheatsheet scratchpad (launch/show/hide)"),
    Key([mod], "s", lazy.group["scratchpad"].dropdown_toggle("notes-pad"), desc="Toggle notes scratchpad (launch/show/hide)"),
    Key([mod], "w", lazy.group["scratchpad"].dropdown_toggle("weather-pad"), desc="Toggle Weather forecast dropdown (launch/show/hide)"),
    Key([mod], "n", lazy.group["scratchpad"].dropdown_toggle("log-pad"), desc="Toggle System Log Viewer scratchpad (launch/show/hide)"),
    Key([mod], "d", lazy.group["scratchpad"].dropdown_toggle("docker-pad"), desc="Toggle Docker services scratchpad (launch/show/hide)"),
    Key([mod], "x", lazy.group["scratchpad"].dropdown_toggle("clip-pad"), desc="Toggle Clipboard history scratchpad (launch/show/hide)"),
    Key([mod], "a", lazy.group["scratchpad"].dropdown_toggle("audio-pad"), desc="Toggle Audio mixer scratchpad (launch/show/hide)"),
    Key([mod], "i", lazy.group["scratchpad"].dropdown_toggle("wifi-pad"), desc="Toggle Wi-Fi network selection scratchpad (launch/show/hide)"),
    Key([mod], "g", lazy.group["scratchpad"].dropdown_toggle("agy-pad"), desc="Toggle Antigravity (agy) dropdown"),
    Key([mod], "r", lazy.group["scratchpad"].dropdown_toggle("ranger-pad"), desc="Toggle Ranger file manager scratchpad (launch/show/hide)"),
    Key([mod], "c", lazy.group["scratchpad"].dropdown_toggle("calc-pad"), desc="Toggle IPython calculator scratchpad (launch/show/hide)"),
    Key([mod], "z", lazy.group["scratchpad"].dropdown_toggle("zodiac-pad"), desc="Toggle Zodiac calendar scratchpad (launch/show/hide)"),
    Key([mod], "m", lazy.group["scratchpad"].dropdown_toggle("emoji-pad"), desc="Toggle Emoji picker scratchpad (launch/show/hide)"),
    Key([mod], "y", raise_or_run(["limusic-app", "limusic"], "/home/jaws/.local/bin/limusic.AppImage"), desc="Raise or run Limusic YouTube Music player"),
    Key([mod], "e", lazy.function(toggle_columns_split_or_switch), desc="Toggle Columns layout split H/V or switch to Columns"),
    Key([mod], "o", lazy.function(toggle_desktop_theme), desc="Toggle Gruvbox Dark / Light desktop theme opposite"),

    # --------------------------------------------------------------------------
    # 4.2 Standalone Application Launcher & Bar Prompt
    # --------------------------------------------------------------------------
    Key([mod], "space", lazy.spawn("rofi -show drun"), desc="Open App Launcher (rofi drun)"),
    Key([mod, shift], "space", lazy.spawncmd(), desc="Run command prompt in bar"),
    Key([alt], "F2", lazy.spawncmd(), desc="Run command prompt in bar"),

    # --------------------------------------------------------------------------
    # 4.3 Quick Utilities
    # --------------------------------------------------------------------------
    Key([mod], "l", lazy.spawn("slock"), desc="Lock screen (slock)"),
    Key([ctrl, alt], "Escape", lazy.spawn("xkill"), desc="xkill"),

    # --------------------------------------------------------------------------
    # 4.4 Screenshots (scrot + xclip via custom wrapper script)
    # --------------------------------------------------------------------------
    Key([], "Print", lazy.spawn("/home/jaws/.local/bin/qtile-screenshot full"), desc="Screenshot entire screen"),
    Key([alt], "Print", lazy.spawn("/home/jaws/.local/bin/qtile-screenshot window"), desc="Screenshot window"),
    Key([shift], "Print", lazy.spawn("/home/jaws/.local/bin/qtile-screenshot region"), desc="Screenshot region"),

    # --------------------------------------------------------------------------
    # 4.5 Hardware & Audio Keys (PipeWire / WirePlumber)
    # --------------------------------------------------------------------------
    # Note: `wpctl` controls the modern Linux PipeWire multimedia server.
    # Passing `-l 1.5` caps the maximum volume increase to 150%.
    Key([], "XF86AudioRaiseVolume", lazy.spawn("wpctl set-volume -l 1.5 @DEFAULT_AUDIO_SINK@ 5%+"), desc="Raise volume"),
    Key([], "XF86AudioLowerVolume", lazy.spawn("wpctl set-volume @DEFAULT_AUDIO_SINK@ 5%-"), desc="Lower volume"),
    Key([], "XF86AudioMute", lazy.spawn("wpctl set-mute @DEFAULT_AUDIO_SINK@ toggle"), desc="Toggle mute"),
    Key([], "XF86AudioMicMute", lazy.spawn("wpctl set-mute @DEFAULT_AUDIO_SOURCE@ toggle"), desc="Toggle mic mute"),
    Key([], "XF86WWW", lazy.spawn("firefox"), desc="Launch web browser"),
    Key([], "XF86HomePage", lazy.spawn("firefox"), desc="Launch web browser"),

    # --------------------------------------------------------------------------
    # 4.6 Window Management & Layout Navigation
    # --------------------------------------------------------------------------
    Key([alt], "Tab", lazy.layout.next(), desc="Cycle next window"),
    Key([alt, shift], "Tab", lazy.layout.previous(), desc="Cycle previous window"),
    Key([mod], "Tab", lazy.next_layout(), desc="Toggle layout (Monocle / Columns)"),
    Key([mod], "j", lazy.layout.next(), desc="Next window in layout"),
    Key([mod], "k", lazy.layout.previous(), desc="Previous window in layout"),

    # --------------------------------------------------------------------------
    # 4.7 Window State (Kill, Fullscreen, Float)
    # --------------------------------------------------------------------------
    Key([alt], "F4", lazy.window.kill(), desc="Close active window"),
    Key([mod], "q", lazy.window.kill(), desc="Close active window"),
    Key([alt], "F11", lazy.window.toggle_fullscreen(), desc="Toggle fullscreen"),
    Key([mod, shift], "f", lazy.window.toggle_fullscreen(), desc="Toggle fullscreen"),
    Key([alt], "space", lazy.window.toggle_floating(), desc="Toggle floating"),

    # --------------------------------------------------------------------------
    # 4.8 Workspace Navigation
    # --------------------------------------------------------------------------
    Key([mod], "Left", lazy.screen.prev_group(), desc="Previous workspace"),
    Key([mod], "Right", lazy.screen.next_group(), desc="Next workspace"),

    # --------------------------------------------------------------------------
    # 4.9 Qtile Lifecycle (In-place Reload & Session Shutdown)
    # --------------------------------------------------------------------------
    Key([mod, ctrl], "r", lazy.reload_config(), desc="Reload Qtile configuration"),
    Key([mod, ctrl], "q", lazy.shutdown(), desc="Exit Qtile"),
    Key([ctrl, alt], "Delete", lazy.shutdown(), desc="Exit Qtile"),
]


# ==============================================================================
# SECTION 5: Groups (Workspaces 1 - 9) & Dynamic Key Generation
# ==============================================================================
# [What it does]:
# Initializes virtual workspaces 1 through 9, and programmatically generates the
# keybindings to switch to each workspace and move windows between workspaces.
#
# [Python Concepts]:
# 1. List Comprehension:
#    `groups = [Group(str(i)) for i in range(1, 10)]` creates 9 `Group` instances.
# 2. `range(start, stop)`:
#    In Python, `range(1, 10)` starts at 1 and stops *before* 10 (yielding 1..9).
# 3. Type Conversion:
#    `str(i)` converts each integer to a string because Group names in Qtile must be strings.
# 4. `list.extend()` vs `list.append()`:
#    `keys.extend([...])` unpacks and appends each element of the given list into `keys`.
#    (If `append()` was used here, it would insert a nested sublist, breaking Qtile).
# 5. Formatted String Literals (F-Strings):
#    `f"Switch to group {g.name}"` dynamically interpolates variable values directly into strings.
#
# [Architecture Reasoning]:
# In traditional non-Python window managers (like i3 or bspwm), setting up 9 workspaces
# requires writing 27 lines of repetitive configuration.
# Because Qtile uses Python, we write one loop that programmatically generates all 27 key
# combinations, eliminating code duplication and human error.
# ==============================================================================
groups = [Group(str(i)) for i in range(1, 10)]

for g in groups:
    keys.extend([
        # Mod + [1-9]: Switch active screen view to workspace
        Key([mod], g.name, lazy.group[g.name].toscreen(), desc=f"Switch to group {g.name}"),
        # Mod + Shift + [1-9]: Move active window to workspace & follow it
        Key([mod, shift], g.name, lazy.window.togroup(g.name, switch_group=True), desc=f"Move window to group {g.name}"),
        # Ctrl + F[1-9]: Alternate workspace switch shortcut
        Key([ctrl], f"F{g.name}", lazy.group[g.name].toscreen(), desc=f"Switch to group {g.name}"),
    ])


# ==============================================================================
# SECTION 6: Special ScratchPad Workspace (btop)
# ==============================================================================
# [What it does]:
# Appends a hidden workspace ("scratchpad") containing a Quake-style dropdown terminal
# running the `btop` system monitor.
#
# [Python Concepts]:
# 1. `groups.append(...)`:
#    Adds a specialized subclass of `Group` (`ScratchPad`) to the existing `groups` list.
# 2. Regular Expressions (`re.compile`):
#    `re.compile(r"btop", re.I)` creates a pre-compiled regular expression pattern.
#    The `r""` prefix indicates a raw string, and `re.I` is the case-insensitive flag.
# 3. Relative Coordinate Floats:
#    `x=0.05, y=0.05, width=0.9, height=0.9` use floating-point numbers between 0.0 and 1.0
#    representing percentages of total screen dimensions (here: 90% wide/tall, centered with 5% margins).
#
# [Architecture Reasoning]:
# A `ScratchPad` in Qtile is an isolated workspace that does not appear in pager widgets or
# cycling keybindings. When toggled via `lazy.group["scratchpad"].dropdown_toggle("btop")`,
# Qtile animates/maps the window onto the current screen as a floating overlay without
# disrupting the active tiled workspace layout.
# ==============================================================================
groups.append(
    ScratchPad(
        "scratchpad",
        [
            DropDown(
                "btop",
                "kitty --class btop-float -e btop",
                match=Match(wm_class=re.compile(r"btop", re.I)),
                x=0.05,
                y=0.05,
                width=0.9,
                height=0.9,
                opacity=1.0,
                on_focus_lost_hide=False,
            ),
            DropDown(
                "vim-cheat",
                "/home/jaws/Projects/qtile_bench/vim_cheat.py",
                match=Match(wm_class=re.compile(r"vim-cheat", re.I)),
                x=0.1,
                y=0.024,
                width=0.8,
                height=0.88,
                opacity=1.0,
                on_focus_lost_hide=False,
            ),
            DropDown(
                "docker-pad",
                "/home/jaws/Projects/qtile_bench/docker_pad.py",
                match=Match(wm_class=re.compile(r"docker-pad", re.I)),
                x=0.1,
                y=0.024,
                width=0.8,
                height=0.88,
                opacity=1.0,
                on_focus_lost_hide=False,
            ),
            DropDown(
                "clip-pad",
                "/home/jaws/Projects/qtile_bench/clip_pad.py",
                match=Match(wm_class=re.compile(r"clip-pad", re.I)),
                x=0.1,
                y=0.024,
                width=0.8,
                height=0.88,
                opacity=1.0,
                on_focus_lost_hide=False,
            ),
            DropDown(
                "term-scratch",
                "kitty --class term-scratch",
                match=Match(wm_class=re.compile(r"term-scratch", re.I)),
                x=0.05,
                y=0.024,
                width=0.9,
                height=0.65,
                opacity=1.0,
                on_focus_lost_hide=False,
            ),
            DropDown(
                "audio-pad",
                "/home/jaws/Projects/qtile_bench/audio_pad.py",
                match=Match(wm_class=re.compile(r"audio-pad", re.I)),
                x=0.1,
                y=0.024,
                width=0.8,
                height=0.88,
                opacity=1.0,
                on_focus_lost_hide=False,
            ),
            DropDown(
                "wifi-pad",
                "/home/jaws/Projects/qtile_bench/wifi_pad.py",
                match=Match(wm_class=re.compile(r"wifi-pad", re.I)),
                x=0.1,
                y=0.024,
                width=0.8,
                height=0.88,
                opacity=1.0,
                on_focus_lost_hide=False,
            ),
            DropDown(
                "lazygit-pad",
                "kitty --class lazygit-pad sh -c 'lazygit || (echo \"lazygit not installed. Run: sudo apt install lazygit\" && read -n 1)'",
                match=Match(wm_class=re.compile(r"lazygit-pad", re.I)),
                x=0.05,
                y=0.024,
                width=0.9,
                height=0.88,
                opacity=1.0,
                on_focus_lost_hide=False,
            ),
            DropDown(
                "ranger-pad",
                "kitty --class ranger-pad sh -c 'ranger || (echo \"ranger not installed. Run: sudo apt install ranger\" && read -n 1)'",
                match=Match(wm_class=re.compile(r"ranger-pad", re.I)),
                x=0.05,
                y=0.024,
                width=0.9,
                height=0.88,
                opacity=1.0,
                on_focus_lost_hide=False,
            ),
            DropDown(
                "calc-pad",
                "kitty --class ipython-pad sh -c 'ipython3 || python3'",
                match=Match(wm_class=re.compile(r"ipython-pad", re.I)),
                x=0.1,
                y=0.024,
                width=0.8,
                height=0.7,
                opacity=1.0,
                on_focus_lost_hide=False,
            ),
            DropDown(
                "agy-pad",
                "kitty --class agy-pad /home/jaws/.local/bin/agy --dangerously-skip-permissions",
                match=Match(wm_class=re.compile(r"agy-pad", re.I)),
                x=0.05,
                y=0.024,
                width=0.9,
                height=0.88,
                opacity=1.0,
                on_focus_lost_hide=False,
            ),
            DropDown(
                "fzf-pad",
                "kitty --class fzf-pad /home/jaws/.local/bin/qtile-fzf",
                match=Match(wm_class=re.compile(r"fzf-pad", re.I)),
                x=0.05,
                y=0.024,
                width=0.9,
                height=0.88,
                opacity=1.0,
                on_focus_lost_hide=False,
            ),
            DropDown(
                "zodiac-pad",
                "/home/jaws/Projects/qtile_bench/zodiac_pad.py",
                match=Match(wm_class=re.compile(r"zodiac-pad", re.I)),
                x=0.1,
                y=0.024,
                width=0.8,
                height=0.88,
                opacity=1.0,
                on_focus_lost_hide=False,
            ),
            DropDown(
                "emoji-pad",
                "/home/jaws/Projects/qtile_bench/emoji_pad.py",
                match=Match(wm_class=re.compile(r"emoji-pad", re.I)),
                x=0.40,
                y=0.024,
                width=0.20,
                height=0.50,
                opacity=1.0,
                on_focus_lost_hide=False,
            ),
            DropDown(
                "key-cheat",
                "/home/jaws/Projects/qtile_bench/key_cheat.py",
                match=Match(wm_class=re.compile(r"key-cheat", re.I)),
                x=0.1,
                y=0.024,
                width=0.8,
                height=0.88,
                opacity=1.0,
                on_focus_lost_hide=False,
            ),
            DropDown(
                "notes-pad",
                "kitty --class notes-pad /home/jaws/.local/bin/qtile-notes",
                match=Match(wm_class=re.compile(r"notes-pad", re.I)),
                x=0.1,
                y=0.024,
                width=0.8,
                height=0.88,
                opacity=1.0,
                on_focus_lost_hide=False,
            ),
            DropDown(
                "weather-pad",
                "/home/jaws/Projects/qtile_bench/weather_pad.py",
                match=Match(wm_class=re.compile(r"weather-pad", re.I)),
                x=0.1,
                y=0.024,
                width=0.8,
                height=0.88,
                opacity=1.0,
                on_focus_lost_hide=False,
            ),
            DropDown(
                "log-pad",
                "/home/jaws/Projects/qtile_bench/log_pad.py",
                match=Match(wm_class=re.compile(r"log-pad", re.I)),
                x=0.1,
                y=0.024,
                width=0.8,
                height=0.88,
                opacity=1.0,
                on_focus_lost_hide=False,
            ),
        ],
    )
)


# ==============================================================================
# Color Palette: Dynamic Gruvbox (Dark / Light via Super + o)
# ==============================================================================
# [What it does]:
# Fetches the active color palette dynamically from the central theme manager
# (theme.py), allowing instant switching between Gruvbox Dark and Gruvbox Light.
# ==============================================================================
colors = theme.get_colors()


# ==============================================================================
# SECTION 7: Window Layouts
# ==============================================================================
# [What it does]:
# Defines the tiling algorithms available to arrange non-floating windows on workspaces.
#
# [Python Concepts]:
# - Class Instantiation with Keyword Arguments:
#   `layout.Max(...)` and `layout.Columns(...)` configure layout properties like borders and margins.
# - Color Representation:
#   Colors are defined as standard 6-character hex strings (using the Ghostty Gruvbox Dark
#   palette: `colors["bright_blue"]` for active focus, `colors["selection_bg"]` for unfocused).
#
# [Architecture Reasoning]:
# Qtile separates window management policy into modular Layout classes.
# - `layout.Max` (Monocle): Gives 100% of the screen area to the focused window (like browser tabs),
#   maximizing focus and screen real estate on laptops or single monitors.
# - `layout.Columns`: Arranges windows in columns, subdividing columns vertically as new windows open.
# The user switches between these layouts on the fly using `lazy.next_layout()`.
# ==============================================================================
layouts = [
    layout.Max(
        margin=0,
        border_width=0,
    ),
    layout.Columns(
        border_focus=colors["bright_blue"],
        border_normal=colors["selection_bg"],
        border_width=2,
        margin=4,
    ),
]


# ==============================================================================
# SECTION 8: Top Status Bar & Screens
# ==============================================================================
# [What it does]:
# Checks for wallpaper file availability and configures physical screens with a top status bar
# populated by informative widgets (Layout indicator, Group tags, Prompt, Window Title, Systray,
# Volume, CPU, RAM, Battery, Clock, and Exit button).
#
# [Python Concepts]:
# 1. Filesystem Access with `os.path.exists()`:
#    Verifies whether a wallpaper file exists on the disk before attempting to pass it to Qtile,
#    falling back safely to `None` if absent to prevent runtime errors.
# 2. Composition Pattern (Objects containing Objects):
#    `Screen` contains a `Bar`, which contains a list of `Widget` instances.
# 3. String Formatting Specifications:
#    - `fmt="[{}]"`: Basic placeholder substitution.
#    - `format="CPU: {load_percent}%"`: Named parameter substitution from widget data dictionaries.
#    - `format="RAM: {MemUsed:.1f}G"`: Format specification (`.1f` rounds floating point to 1 decimal place).
#    - `format="Bat: {percent:2.0%} {char}"`: Format specification (`2.0%` formats float as whole percentage).
# 4. Asynchronous Polling:
#    `update_interval=2.0` instructs Qtile's event loop to poll system stats every 2 seconds.
#
# [Architecture Reasoning]:
# Qtile's UI rendering pipeline utilizes Cairo and Pango to render directly to an X11 pixmap.
# Widgets are lightweight asynchronous coroutines or threads that update their state without
# blocking the main window manager thread or freezing the desktop during heavy system load.
# ==============================================================================
wallpaper_file = "/home/jaws/Pictures/wallpaper/tux.png"
if not os.path.exists(wallpaper_file):
    wallpaper_file = None

# Default font and sizing applied across all bar widgets
# Font fallback: FontAwesome primary for icons + DejaVu Sans Mono fallback for text
widget_defaults = dict(
    font="FontAwesome, DejaVu Sans Mono",
    fontsize=12,
    padding=4,
    foreground=colors["fg"],
)
extension_defaults = widget_defaults.copy()


screens = [
    Screen(
        top=bar.Bar(
            [
                # Shows current active layout (e.g. monocle max or columns)
                widget.CurrentLayout(
                    fmt=" {}",
                    background=colors["neutral_blue"],
                    foreground=colors["bg"],
                    padding=8,
                ),
                # Visual workspace switcher (clickable group indicators)
                widget.GroupBox(
                    background=colors["dark_gray"],
                    highlight_method="line",
                    highlight_color=[colors["dark_gray"], colors["dark_gray"]],
                    this_current_screen_border=colors["bright_blue"],
                    this_screen_border=colors["bright_blue"],
                    other_current_screen_border=colors["dark_gray"],
                    other_screen_border=colors["dark_gray"],
                    active=colors["fg"],
                    inactive=colors["gray"],
                    urgent_border=colors["bright_red"],
                    padding_y=4,
                    padding_x=6,
                    margin_y=3,
                    margin_x=2,
                    disable_drag=True,
                ),
                # Interactive command prompt for typing shell commands directly in the bar
                widget.Prompt(
                    prompt="Run ❯ ",
                    cursor_color=colors["bright_blue"],
                    background=colors["bg"],
                    foreground=colors["bright_green"],
                    padding=6,
                ),
                # Displays title of currently focused active window
                widget.WindowName(
                    background=colors["bg"],
                    foreground=colors["fg"],
                    max_chars=40,
                    padding=8,
                ),
                # Flexible space pusher: expands to push subsequent widgets to the right edge
                widget.Spacer(background=colors["bg"]),
                # System notification tray icons (Network, Bluetooth, Discord, etc.)
                widget.Systray(
                    background=colors["dark_gray"],
                    padding=6,
                    icon_size=16,
                ),
                # Real-time CPU utilization percentage
                widget.CPU(
                    format=" {load_percent}%",
                    update_interval=2.0,
                    background=colors["neutral_yellow"],
                    foreground=colors["bg"],
                    padding=8,
                ),
                # Real-time RAM utilization in Gigabytes
                widget.Memory(
                    format=" {MemUsed:.1f}G",
                    measure_mem="G",
                    update_interval=2.0,
                    background=colors["neutral_aqua"],
                    foreground=colors["bg"],
                    padding=8,
                ),
                # Laptop battery status and discharge indicator
                widget.Battery(
                    format="{char} {percent:2.0%}",
                    charge_char="",
                    discharge_char="",
                    full_char="",
                    not_charging_char="",
                    empty_char="",
                    update_interval=10,
                    background=colors["neutral_green"],
                    foreground=colors["bg"],
                    padding=8,
                ),
                # Formatted real-time date and clock
                widget.Clock(
                    format=" %a %b %d   %I:%M %p",
                    background=colors["neutral_blue"],
                    foreground=colors["bg"],
                    padding=8,
                ),
                # Quick power/session exit button (flush edge with no trailing arrow)
                widget.QuickExit(
                    default_text="",
                    countdown_format="[{}]",
                    background=colors["neutral_red"],
                    foreground=colors["bg"],
                    padding=10,
                ),
            ],
            26,  # Height of the bar in pixels
            background=colors["bg"],
            margin=[0, 0, 0, 0],
        ),
        wallpaper=wallpaper_file,
        wallpaper_mode="fill",
    ),
]


# ==============================================================================
# SECTION 9: Floating Window Rules (`floating_layout`)
# ==============================================================================
# [What it does]:
# Tells Qtile which windows should float by default instead of being tiled into layouts
# (e.g., authentication prompts, audio mixers, calculators, file progress bars).
#
# [Python Concepts]:
# 1. Asterisk / Splat Unpacking Operator (`*`):
#    `*layout.Floating.default_float_rules` unpacks the existing list of default rules provided
#    by Qtile into this new list, allowing us to extend it without overwriting built-in sanity rules.
# 2. Matching Criteria Objects:
#    `Match(wm_class=...)` and `Match(title=...)` create criteria evaluated against X11 properties.
#
# [Architecture Reasoning]:
# Windows in X11 advertise WM_CLASS and WM_NAME properties. Qtile evaluates newly created
# client windows against these rules during the map-request phase. Matching windows bypass
# the active layout algorithm and are granted independent floating geometries.
# ==============================================================================
floating_layout = layout.Floating(
    float_rules=[
        *layout.Floating.default_float_rules,
        Match(wm_class="confirmreset"),
        Match(wm_class="makebranch"),
        Match(wm_class="maketag"),
        Match(wm_class="ssh-askpass"),
        Match(title="branchdialog"),
        Match(title="pinentry"),
        # Dialogs and lightweight popup utilities
        Match(wm_class="pavucontrol"),
        Match(wm_class="polkit-gnome-authentication-agent-1"),
        Match(wm_class="blueman-manager"),
        Match(wm_class="nm-connection-editor"),
        Match(wm_class="galculator"),
        Match(wm_class="btop-float"),
        Match(wm_class="kdialog"),
        Match(title="File Operation Progress"),
    ],
    border_focus=colors["bright_blue"],
    border_normal=colors["selection_bg"],
    border_width=2,
)


# ==============================================================================
# SECTION 10: Mouse Bindings (`mouse`)
# ==============================================================================
# [What it does]:
# Allows moving and resizing floating windows interactively using mouse drag gestures.
#
# [Python Concepts]:
# - Class Instantiation:
#   `Drag` captures continuous mouse motion events while a button is held down.
#   `Click` captures single press-and-release events.
# - Dynamic Initial State Capture:
#   `start=lazy.window.get_position()` registers a callback that records the window's
#   coordinates at the exact moment the drag gesture begins.
#
# [Architecture Reasoning]:
# Traditional X11 desktop ergonomics: holding the `Mod` (Super) key allows left-click dragging
# to reposition floating windows and right-click dragging to resize them from anywhere inside
# the window, eliminating the need for bulky titlebars or tiny resize borders.
# ==============================================================================
mouse = [
    Drag([mod], "Button1", lazy.window.set_position_floating(), start=lazy.window.get_position()),
    Drag([mod], "Button3", lazy.window.set_size_floating(), start=lazy.window.get_size()),
    Click([mod], "Button2", lazy.window.bring_to_front()),
]


# ==============================================================================
# SECTION 11: General Qtile Configuration Settings
# ==============================================================================
# [What it does]:
# Global configuration variables recognized by Qtile to fine-tune window manager behavior.
#
# [Architecture Reasoning]:
# - `follow_mouse_focus = True`: Window focus follows the mouse pointer without requiring a click.
# - `bring_front_click = False`: Clicking a window focuses it without necessarily popping it over others.
# - `floats_kept_above = True`: Floating windows remain on top of tiled windows so dialogs aren't lost.
# - `cursor_warp = False`: Prevents the mouse cursor from jumping automatically when switching windows.
# - `auto_fullscreen = True`: Honors fullscreen requests from games or video players.
# - `focus_on_window_activation = "smart"`: Only switches focus to activating windows if they are urgent.
# - `reconfigure_screens = True`: Automatically adapts layout when monitors are connected or disconnected.
# - `auto_minimize = True`: Minimizes full-screen windows if focus is lost.
# - `wmname = "LG3D"`: Emulates the Sun Java Look-and-Feel window manager name to fix rendering bugs
#   in legacy Java AWT/Swing graphical applications (which fail to draw windows in non-reparenting WMs).
# ==============================================================================
dgroups_key_binder = None
dgroups_app_rules = []
follow_mouse_focus = True
bring_front_click = False
floats_kept_above = True
cursor_warp = False
auto_fullscreen = True
focus_on_window_activation = "smart"
reconfigure_screens = True
auto_minimize = True
wmname = "LG3D"


# ==============================================================================
# SECTION 12: Startup Lifecycle Hook
# ==============================================================================
# [What it does]:
# Executes an external shell script (`autostart.sh`) once when Qtile starts up.
#
# [Python Concepts]:
# 1. Path Expansion (`os.path.expanduser`):
#    Expands the tilde `~` symbol into the absolute path `/home/jaws`.
# 2. Asynchronous Process Execution (`subprocess.Popen`):
#    Unlike `subprocess.run()`, which blocks execution until the script finishes,
#    `Popen` starts the script as an independent background process and returns
#    immediately, allowing Qtile to finish starting up without delay.
#
# [Architecture Reasoning]:
# - Difference between `startup` and `startup_once`:
#   `startup` runs every time the config is reloaded (`Mod + Ctrl + R`).
#   `startup_once` ONLY runs on initial login. Background daemons (compositors like picom,
#   notification daemons, polkit agents) should only be launched once to avoid spawning
#   duplicate background processes.
# ==============================================================================
@hook.subscribe.startup_once
def autostart():
    autostart_script = os.path.expanduser("~/.config/qtile/autostart.sh")
    if os.path.exists(autostart_script):
        subprocess.Popen([autostart_script])
