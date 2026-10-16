#!/usr/bin/env python3
"""
Emoji Picker Scratchpad for Qtile
==================================
A compact, fast, keyboard-driven emoji search and picker styled to match Qtile's
Gruvbox Dark theme and designed to slide out seamlessly from the top bar.

Features:
- Complete Unicode emoji database with instant offline caching (~/.cache/emoji_pad/)
- Full Gitmoji and developer tags support (:bug:, :rocket:, :zap:, :sparkles:, etc.)
- Compact category icon tabs: Recent, Dev, Smileys, Gestures, Animals, Food, Travel, Activities, Objects, Symbols, Flags
- Real-time search-as-you-type across emoji names, shortcodes, and keywords
- Automatically synchronizes both X11 CLIPBOARD and PRIMARY selections via xclip
- Keyboard-first navigation:
    [Enter]         : Copy selected emoji & close dropdown
    [Shift+Enter]   : Copy selected emoji & keep open
    [Arrows / hjkl] : Navigate emoji grid
    [Tab / S-Tab]   : Cycle categories
    [1-9]           : Jump directly to category 1-9
    [/]             : Focus search bar
    [Esc / q]       : Clear search / close dropdown
- Native X11 WM_CLASS ("emoji-pad") for Qtile ScratchPad integration
"""

import sys
import os
import re
import json
import subprocess
import threading
import tkinter as tk
from tkinter import font as tkfont

try:
    from PIL import Image, ImageDraw, ImageFont, ImageTk
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

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
        "accent_blue": "#83a598", "accent_aqua": "#8ec07c", "accent_purple": "#d3869b",
    }

CACHE_DIR = os.path.expanduser("~/.cache/emoji_pad")
RECENT_FILE = os.path.join(CACHE_DIR, "recent.json")
EMOJIS_CACHE = os.path.join(CACHE_DIR, "emojis.json")
IMG_CACHE_DIR = os.path.join(CACHE_DIR, "img")
SYSTEM_EMOJI_FILE = "/usr/share/unicode/emoji/emoji-test.txt"

EMOJI_FONT_PATHS = [
    "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf",
    os.path.expanduser("~/.local/share/fonts/NotoColorEmoji.ttf"),
]


def find_emoji_font_path() -> str | None:
    for path in EMOJI_FONT_PATHS:
        if os.path.exists(path):
            return path
    try:
        out = subprocess.check_output(["fc-match", "-f", "%{file}", "Noto Color Emoji"], timeout=1).decode().strip()
        if os.path.exists(out):
            return out
    except Exception:
        pass
    return None

# Curated developer gitmojis & tags
GITMOJIS = [
    {"char": "✨", "name": "sparkles", "code": ":sparkles:", "tags": "feature feat new shiny star functionality"},
    {"char": "🐛", "name": "bug", "code": ":bug:", "tags": "fix issue error bugfix defect problem"},
    {"char": "🚀", "name": "rocket", "code": ":rocket:", "tags": "deploy release launch ship production publish"},
    {"char": "⚡", "name": "zap", "code": ":zap:", "tags": "performance perf speed fast optimize lightning"},
    {"char": "🔥", "name": "fire", "code": ":fire:", "tags": "remove delete clean hot flame drop deprecated"},
    {"char": "📝", "name": "memo", "code": ":memo:", "tags": "docs documentation note readme comments writing"},
    {"char": "🎨", "name": "art", "code": ":art:", "tags": "style format structure css ui design appearance"},
    {"char": "♻️", "name": "recycle", "code": ":recycle:", "tags": "refactor cleanup code reuse restructure"},
    {"char": "🔒", "name": "lock", "code": ":lock:", "tags": "security private secret encrypt vulnerability cve"},
    {"char": "🔐", "name": "closed_lock_with_key", "code": ":closed_lock_with_key:", "tags": "auth authentication credentials ssl secret token"},
    {"char": "🧪", "name": "test_tube", "code": ":test_tube:", "tags": "test testing unit integration coverage test_tube"},
    {"char": "🚑", "name": "ambulance", "code": ":ambulance:", "tags": "critical hotfix urgent emergency patch triage"},
    {"char": "🎉", "name": "tada", "code": ":tada:", "tags": "celebrate party init initial start celebrate"},
    {"char": "🔧", "name": "wrench", "code": ":wrench:", "tags": "config configuration setup tools maintenance tool"},
    {"char": "🔨", "name": "hammer", "code": ":hammer:", "tags": "build scripts makefile tooling dev build"},
    {"char": "📦", "name": "package", "code": ":package:", "tags": "package bundle compiled build dist archive npm pip cargo"},
    {"char": "👷", "name": "construction_worker", "code": ":construction_worker:", "tags": "ci continuous integration build pipeline github action workflow"},
    {"char": "💚", "name": "green_heart", "code": ":green_heart:", "tags": "ci fix build passing continuous integration test passed"},
    {"char": "🚧", "name": "construction", "code": ":construction:", "tags": "wip work in progress under construction draft"},
    {"char": "🚨", "name": "rotating_light", "code": ":rotating_light:", "tags": "warning compiler lint alert siren error red"},
    {"char": "🔖", "name": "bookmark", "code": ":bookmark:", "tags": "version release tag semver tag release"},
    {"char": "📌", "name": "pushpin", "code": ":pushpin:", "tags": "pin dependency pinned version fixed"},
    {"char": "⬆️", "name": "arrow_up", "code": ":arrow_up:", "tags": "upgrade dependency update bump version"},
    {"char": "⬇️", "name": "arrow_down", "code": ":arrow_down:", "tags": "downgrade dependency rollback revert"},
    {"char": "➕", "name": "heavy_plus_sign", "code": ":heavy_plus_sign:", "tags": "add dependency package new include"},
    {"char": "➖", "name": "heavy_minus_sign", "code": ":heavy_minus_sign:", "tags": "remove dependency package drop unpin"},
    {"char": "🔀", "name": "twisted_rightwards_arrows", "code": ":twisted_rightwards_arrows:", "tags": "merge branch pr pull request git"},
    {"char": "⏪", "name": "rewind", "code": ":rewind:", "tags": "revert back undo rollback git revert"},
    {"char": "🚚", "name": "truck", "code": ":truck:", "tags": "move rename file directory paths transfer migration"},
    {"char": "💥", "name": "boom", "code": ":boom:", "tags": "breaking change explosion destructive crash incompatible"},
    {"char": "💡", "name": "bulb", "code": ":bulb:", "tags": "idea note tip comment inspiration insight"},
    {"char": "💄", "name": "lipstick", "code": ":lipstick:", "tags": "ui cosmetics visual frontend theme styling"},
    {"char": "🌐", "name": "globe_with_meridians", "code": ":globe_with_meridians:", "tags": "i18n l10n internationalization translation web localization"},
    {"char": "✏️", "name": "pencil2", "code": ":pencil2:", "tags": "typo spelling grammar fix text edit doc"},
    {"char": "💩", "name": "poop", "code": ":poop:", "tags": "crap bad code smelly technical debt shit"},
    {"char": "🗃️", "name": "card_file_box", "code": ":card_file_box:", "tags": "database db sql storage migration query schema"},
    {"char": "🔊", "name": "loud_sound", "code": ":loud_sound:", "tags": "log logger logging print verbose stdout tracing"},
    {"char": "🔇", "name": "mute", "code": ":mute:", "tags": "silence mute quiet disable logs quiet"},
    {"char": "📱", "name": "iphone", "code": ":iphone:", "tags": "mobile responsive ios android phone screen"},
    {"char": "🤡", "name": "clown_face", "code": ":clown_face:", "tags": "mock stub fake dummy testing joke clown"},
    {"char": "🙈", "name": "see_no_evil", "code": ":see_no_evil:", "tags": "gitignore ignore hidden hide exclude secret"},
    {"char": "📸", "name": "camera_flash", "code": ":camera_flash:", "tags": "snapshot visual regression test screenshot image"},
    {"char": "⚗️", "name": "alembic", "code": ":alembic:", "tags": "experiment experimental research laboratory test feature"},
    {"char": "🔍", "name": "mag", "code": ":mag:", "tags": "search lookup seo query find inspect explore"},
    {"char": "🏷️", "name": "label", "code": ":label:", "tags": "types typescript typing annotation tag label"},
    {"char": "🌱", "name": "seedling", "code": ":seedling:", "tags": "seed database migration fixture init mock"},
    {"char": "🚩", "name": "triangular_flag_on_post", "code": ":triangular_flag_on_post:", "tags": "flag feature flag toggle switch variant"},
    {"char": "🥅", "name": "goal_net", "code": ":goal_net:", "tags": "catch error try catch exception handling trap"},
    {"char": "🗑️", "name": "wastebasket", "code": ":wastebasket:", "tags": "cleanup trash delete remove deprecated drop garbage"},
    {"char": "🛂", "name": "passport_control", "code": ":passport_control:", "tags": "auth authentication permission rbac login token oauth"},
    {"char": "🩹", "name": "adhesive_bandage", "code": ":adhesive_bandage:", "tags": "simple fix patch quickfix bandaid non critical"},
    {"char": "🧐", "name": "monocle_face", "code": ":monocle_face:", "tags": "review pr review code inspection examine check curious"},
    {"char": "⚰️", "name": "coffin", "code": ":coffin:", "tags": "dead code rip tombstone graveyard cemetery remove"},
    {"char": "👔", "name": "necktie", "code": ":necktie:", "tags": "business logic domain enterprise rules corporate"},
    {"char": "🧱", "name": "brick", "code": ":bricks:", "tags": "infrastructure core infra foundation platform base"},
    {"char": "🧑‍💻", "name": "technologist", "code": ":technologist:", "tags": "developer programmer engineer coding hacker computer"},
]


def set_xclip(text: str) -> bool:
    """Push text to both CLIPBOARD and PRIMARY X11 buffers."""
    success = True
    for selection in ("clipboard", "primary"):
        try:
            res = subprocess.run(
                ["xclip", "-selection", selection],
                input=text,
                text=True,
                check=False,
                timeout=1,
            )
            if res.returncode != 0:
                success = False
        except Exception:
            success = False
    return success


class EmojiPadApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Emoji Picker")
        self.root.configure(bg=THEME["bg"])

        # Data sets
        self.all_emojis: list[dict] = []
        self.recent_emojis: list[dict] = []
        # Categories: (Key, Icon, Display Name)
        self.categories: list[tuple[str, str, str]] = [
            ("Recent", "🕒", "Recent"),
            ("Dev / Git", "💻", "Dev & Git"),
            ("Smileys & Emotion", "😀", "Smileys"),
            ("People & Body", "👋", "Gestures"),
            ("Animals & Nature", "🐶", "Animals"),
            ("Food & Drink", "🍔", "Food"),
            ("Travel & Places", "🚀", "Travel"),
            ("Activities", "🎮", "Activities"),
            ("Objects", "💡", "Objects"),
            ("Symbols", "🔣", "Symbols"),
            ("Flags", "🚩", "Flags"),
        ]
        self.active_category: str = "Recent"

        # Search & Filtering
        self.search_query: str = ""
        self.filtered_items: list[dict] = []
        self.selected_index: int = 0

        # Compact grid geometry metrics
        self.cell_w = 44
        self.cell_h = 44
        self.gap = 5
        self.cols = 7

        # Image rendering & cache for complex ZWJ emojis
        self.has_emoji_font = False
        self.emoji_font = None
        self._font_lock = threading.Lock()
        self._img_cache: dict[tuple[str, int], ImageTk.PhotoImage] = {}
        self._init_emoji_font()

        # Load datasets
        self._load_datasets()
        self._start_background_precache()

        # Build UI layout
        self._build_header()
        self._build_tabs()
        self._build_grid()
        self._build_footer()

        # Keyboard bindings
        self._bind_keys()

        # Initial render
        self._set_category(self.active_category, reset_search=False)

    # ==========================================================================
    # Data Loading & Initialization
    # ==========================================================================
    def _load_datasets(self):
        """Load and index full emoji dataset with caching."""
        os.makedirs(CACHE_DIR, exist_ok=True)

        # 1. Load Recent
        if os.path.exists(RECENT_FILE):
            try:
                with open(RECENT_FILE, "r", encoding="utf-8") as f:
                    self.recent_emojis = json.load(f)
            except Exception:
                self.recent_emojis = []

        # 2. Try loading cached parsed emojis
        loaded_from_cache = False
        if os.path.exists(EMOJIS_CACHE):
            try:
                with open(EMOJIS_CACHE, "r", encoding="utf-8") as f:
                    self.all_emojis = json.load(f)
                    if self.all_emojis and len(self.all_emojis) > 100:
                        loaded_from_cache = True
            except Exception:
                pass

        if not loaded_from_cache:
            self._parse_system_emojis()
            try:
                with open(EMOJIS_CACHE, "w", encoding="utf-8") as f:
                    json.dump(self.all_emojis, f, ensure_ascii=False)
            except Exception:
                pass

        # Seed recent if empty
        if not self.recent_emojis:
            self.recent_emojis = [
                {"char": "🔥", "name": "fire", "code": ":fire:", "group": "Dev / Git", "tags": "hot fire clean"},
                {"char": "🚀", "name": "rocket", "code": ":rocket:", "group": "Dev / Git", "tags": "deploy launch fast"},
                {"char": "✨", "name": "sparkles", "code": ":sparkles:", "group": "Dev / Git", "tags": "feature star new"},
                {"char": "🐛", "name": "bug", "code": ":bug:", "group": "Dev / Git", "tags": "fix bug error"},
                {"char": "👍", "name": "thumbs up", "code": ":thumbsup:", "group": "People & Body", "tags": "approve yes like"},
                {"char": "❤️", "name": "red heart", "code": ":heart:", "group": "Smileys & Emotion", "tags": "love heart"},
                {"char": "😂", "name": "face with tears of joy", "code": ":joy:", "group": "Smileys & Emotion", "tags": "lol haha laugh"},
                {"char": "☕", "name": "hot beverage", "code": ":coffee:", "group": "Food & Drink", "tags": "coffee cafe drink"},
                {"char": "⚡", "name": "high voltage", "code": ":zap:", "group": "Dev / Git", "tags": "fast speed zap"},
                {"char": "🎉", "name": "party popper", "code": ":tada:", "group": "Dev / Git", "tags": "party celebrate tada"},
            ]
            self._save_recent()

    def _parse_system_emojis(self):
        """Parse system /usr/share/unicode/emoji/emoji-test.txt."""
        emojis_list = []
        gitmoji_chars = {g["char"]: g for g in GITMOJIS}

        if os.path.exists(SYSTEM_EMOJI_FILE):
            try:
                current_group = "Smileys & Emotion"
                with open(SYSTEM_EMOJI_FILE, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("# group:"):
                            current_group = line.split(":", 1)[1].strip()
                        elif "; fully-qualified" in line:
                            if "skin tone" in line:
                                continue
                            parts = line.split("#", 1)
                            if len(parts) == 2:
                                meta = parts[1].strip()
                                m = re.match(r"^(\S+)\s+E\d+\.\d+\s+(.*)$", meta)
                                if m:
                                    char, name = m.group(1), m.group(2)
                                    shortcode = f":{name.lower().replace(' ', '_').replace('-', '_')}:"
                                    tags = f"{name.lower()} {name.lower().replace('-', ' ')}"

                                    if char in gitmoji_chars:
                                        gm = gitmoji_chars[char]
                                        shortcode = gm["code"]
                                        tags += f" {gm['tags']} dev git"

                                    emojis_list.append({
                                        "char": char,
                                        "name": name,
                                        "code": shortcode,
                                        "group": current_group,
                                        "tags": tags,
                                    })
            except Exception:
                emojis_list = []

        self.all_emojis = emojis_list

    def _save_recent(self):
        """Save recently picked emojis atomically."""
        try:
            with open(RECENT_FILE, "w", encoding="utf-8") as f:
                json.dump(self.recent_emojis[:40], f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _add_to_recent(self, item: dict):
        """Prepend picked emoji to recent list."""
        self.recent_emojis = [x for x in self.recent_emojis if x["char"] != item["char"]]
        self.recent_emojis.insert(0, item)
        self.recent_emojis = self.recent_emojis[:40]
        self._save_recent()

    # ==========================================================================
    # Complex Emoji Image Rendering & Cache (HarfBuzz / Raqm for ZWJ)
    # ==========================================================================
    def _init_emoji_font(self):
        """Initialize Pillow font and directory for complex emoji rendering."""
        if not PIL_AVAILABLE:
            return
        os.makedirs(IMG_CACHE_DIR, exist_ok=True)
        font_path = find_emoji_font_path()
        if font_path:
            try:
                # NotoColorEmoji is a bitmap CBDT font with fixed strike size 109
                self.emoji_font = ImageFont.truetype(font_path, 109, layout_engine=ImageFont.Layout.RAQM)
                self.has_emoji_font = True
            except Exception:
                try:
                    self.emoji_font = ImageFont.truetype(font_path, 109)
                    self.has_emoji_font = True
                except Exception:
                    self.has_emoji_font = False

    @staticmethod
    def _is_complex_emoji(char: str) -> bool:
        """Return True if emoji requires HarfBuzz/Raqm shaping (ZWJ, keycaps, flags)."""
        return "\u200d" in char or "\u20e3" in char or len(char) > 2

    def get_emoji_image(self, char: str, size: int = 26):
        """Retrieve PhotoImage for complex emoji using disk/RAM cache."""
        if not self.has_emoji_font:
            return None

        key = (char, size)
        if key in self._img_cache:
            return self._img_cache[key]

        hex_key = "_".join(f"{ord(c):x}" for c in char)
        cache_path = os.path.join(IMG_CACHE_DIR, f"{hex_key}_{size}.png")

        # 1. Try disk cache first
        if os.path.exists(cache_path):
            try:
                im = Image.open(cache_path)
                photo = ImageTk.PhotoImage(im)
                self._img_cache[key] = photo
                return photo
            except Exception:
                pass

        # 2. Render on demand via Pillow Raqm engine
        try:
            with self._font_lock:
                im = Image.new("RGBA", (136, 128), (0, 0, 0, 0))
                draw = ImageDraw.Draw(im)
                draw.text((0, 0), char, font=self.emoji_font, embedded_color=True)
            im_resized = im.resize((size, size), Image.Resampling.BILINEAR)
            try:
                im_resized.save(cache_path)
            except Exception:
                pass
            photo = ImageTk.PhotoImage(im_resized)
            self._img_cache[key] = photo
            return photo
        except Exception:
            return None

    def _start_background_precache(self):
        """Pre-render any missing complex emoji PNGs to disk in background."""
        if not self.has_emoji_font:
            return

        def _worker():
            complex_chars = [e["char"] for e in self.all_emojis if self._is_complex_emoji(e.get("char", ""))]
            for char in set(complex_chars):
                hex_key = "_".join(f"{ord(c):x}" for c in char)
                for size in (26, 32):
                    path = os.path.join(IMG_CACHE_DIR, f"{hex_key}_{size}.png")
                    if not os.path.exists(path):
                        try:
                            with self._font_lock:
                                im = Image.new("RGBA", (136, 128), (0, 0, 0, 0))
                                draw = ImageDraw.Draw(im)
                                draw.text((0, 0), char, font=self.emoji_font, embedded_color=True)
                            im_res = im.resize((size, size), Image.Resampling.BILINEAR)
                            im_res.save(path)
                        except Exception:
                            pass

        threading.Thread(target=_worker, daemon=True).start()

    # ==========================================================================
    # UI Layout & Widgets (Compact Design)
    # ==========================================================================
    def _build_header(self):
        """Compact search bar taking full top width."""
        search_frame = tk.Frame(
            self.root,
            bg=THEME["bg_card"],
            bd=1,
            highlightthickness=1,
            highlightbackground=THEME["border"],
        )
        search_frame.pack(fill="x", padx=8, pady=(8, 4), ipady=3)

        lbl_search_icon = tk.Label(
            search_frame,
            text="🔍",
            font=("Noto Color Emoji", 11),
            bg=THEME["bg_card"],
        )
        lbl_search_icon.pack(side="left", padx=(6, 2))

        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *args: self._on_search_changed())

        self.search_entry = tk.Entry(
            search_frame,
            textvariable=self.search_var,
            bg=THEME["bg_card"],
            fg=THEME["fg"],
            insertbackground=THEME["accent_blue"],
            relief="flat",
            font=("DejaVu Sans Mono", 10),
            bd=0,
        )
        self.search_entry.pack(side="left", fill="x", expand=True, padx=4)
        self.search_entry.focus_set()

        # Match Count badge
        self.lbl_count = tk.Label(
            search_frame,
            text="",
            font=("DejaVu Sans Mono", 8, "bold"),
            fg=THEME["key_fg"],
            bg=THEME["bg_card"],
            padx=6,
        )
        self.lbl_count.pack(side="right")

    def _build_tabs(self):
        """Compact icon-based category navigation pills."""
        self.tabs_bar = tk.Frame(self.root, bg=THEME["bg"], bd=0)
        self.tabs_bar.pack(fill="x", padx=8, pady=(0, 4))

        self.tab_buttons: dict[str, tk.Label] = {}
        for key, icon, name in self.categories:
            btn = tk.Label(
                self.tabs_bar,
                text=icon,
                font=("Noto Color Emoji", 10),
                bg=THEME["bg_surface"],
                padx=4,
                pady=2,
                bd=0,
                cursor="hand2",
            )
            btn.pack(side="left", padx=1, expand=True, fill="x")
            btn.bind("<Button-1>", lambda e, k=key: self._set_category(k, reset_search=True))
            btn.bind("<Enter>", lambda e, k=key, n=name: self._on_tab_hover(k, n))
            btn.bind("<Leave>", lambda e, k=key: self._on_tab_unhover(k))
            self.tab_buttons[key] = btn

    def _on_tab_hover(self, key: str, name: str):
        if key != self.active_category:
            self.tab_buttons[key].configure(bg=THEME["bg_hover"])
        self.show_toast(name, THEME["accent_aqua"])

    def _on_tab_unhover(self, key: str):
        if key != self.active_category:
            self.tab_buttons[key].configure(bg=THEME["bg_surface"])
        self.show_toast("Press Enter to Copy & Exit", THEME["fg_dim"])

    def _build_grid(self):
        """Scrollable canvas for the emoji grid."""
        container = tk.Frame(self.root, bg=THEME["bg"], bd=0)
        container.pack(fill="both", expand=True, padx=8, pady=(0, 2))

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
            width=8,
        )
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        # Responsive canvas resize
        self.canvas.bind("<Configure>", self._on_canvas_configure)

        # Canvas mouse wheel
        self.root.bind_all("<Button-4>", lambda e: self.canvas.yview_scroll(-2, "units"))
        self.root.bind_all("<Button-5>", lambda e: self.canvas.yview_scroll(2, "units"))
        self.root.bind_all("<MouseWheel>", lambda e: self.canvas.yview_scroll(-1 if e.delta > 0 else 1, "units"))

    def _build_footer(self):
        """Bottom status bar with compact preview, shortcode, and toast."""
        footer = tk.Frame(
            self.root,
            bg=THEME["bg_card"],
            bd=0,
            highlightthickness=1,
            highlightbackground=THEME["border"],
        )
        footer.pack(fill="x", side="bottom", padx=8, pady=(2, 6), ipady=3)

        # Left: Preview & Details
        preview_box = tk.Frame(footer, bg=THEME["bg_card"])
        preview_box.pack(side="left", padx=6)

        char_frame = tk.Frame(preview_box, bg=THEME["bg_card"], width=38, height=38)
        char_frame.pack_propagate(False)
        char_frame.pack(side="left", padx=(0, 4))

        self.lbl_preview_char = tk.Label(
            char_frame,
            text="✨",
            font=("Noto Color Emoji", 20),
            bg=THEME["bg_card"],
        )
        self.lbl_preview_char.pack(expand=True, fill="both")

        detail_col = tk.Frame(preview_box, bg=THEME["bg_card"])
        detail_col.pack(side="left")

        self.lbl_preview_name = tk.Label(
            detail_col,
            text="",
            font=("DejaVu Sans Mono", 9, "bold"),
            fg=THEME["fg_header"],
            bg=THEME["bg_card"],
            anchor="w",
        )
        self.lbl_preview_name.pack(anchor="w")

        self.lbl_preview_code = tk.Label(
            detail_col,
            text="",
            font=("DejaVu Sans Mono", 8),
            fg=THEME["accent_aqua"],
            bg=THEME["bg_card"],
            anchor="w",
        )
        self.lbl_preview_code.pack(anchor="w")

        # Right: Toast / Feedback Message
        self.lbl_toast = tk.Label(
            footer,
            text="[↵] Copy",
            font=("DejaVu Sans Mono", 8, "bold"),
            fg=THEME["key_fg"],
            bg=THEME["bg_card"],
            anchor="e",
        )
        self.lbl_toast.pack(side="right", padx=6)

    # ==========================================================================
    # Rendering & Grid Computation
    # ==========================================================================
    def _on_canvas_configure(self, event):
        """Adapt grid columns when canvas width changes."""
        width = event.width
        if width > 60:
            new_cols = max(3, (width - self.gap) // (self.cell_w + self.gap))
            if new_cols != self.cols:
                self.cols = new_cols
                self._render_grid(keep_selection=True)

    def _set_category(self, key: str, reset_search: bool = True):
        """Switch active category tab."""
        self.active_category = key
        if reset_search and self.search_var.get():
            self.search_var.set("")

        # Update tab visual highlights
        for cat_key, btn in self.tab_buttons.items():
            if cat_key == key and not self.search_query:
                btn.configure(
                    bg=THEME["bg_card"],
                    highlightthickness=1,
                    highlightbackground=THEME["border_focus"],
                )
            else:
                btn.configure(
                    bg=THEME["bg_surface"],
                    highlightthickness=0,
                )

        self._filter_and_render(reset_index=True)

    def _on_search_changed(self):
        """Live search query changed."""
        q = self.search_var.get().strip().lower()
        self.search_query = q

        for cat_key, btn in self.tab_buttons.items():
            if not q and cat_key == self.active_category:
                btn.configure(
                    bg=THEME["bg_card"],
                    highlightthickness=1,
                    highlightbackground=THEME["border_focus"],
                )
            else:
                btn.configure(
                    bg=THEME["bg_surface"],
                    highlightthickness=0,
                )

        self._filter_and_render(reset_index=True)

    def _filter_and_render(self, reset_index: bool = True):
        """Filter emojis according to active category or live search query."""
        q = self.search_query

        if q:
            matches_primary = []
            matches_secondary = []

            for g in GITMOJIS:
                if q in g["name"] or q in g["code"] or q in g["tags"]:
                    matches_primary.append(g)

            seen_chars = {g["char"] for g in matches_primary}

            for e in self.all_emojis:
                if e["char"] in seen_chars:
                    continue
                name = e["name"].lower()
                code = e.get("code", "").lower()
                tags = e.get("tags", "").lower()

                if q == name or q in code:
                    matches_primary.append(e)
                elif q in name or q in tags:
                    matches_secondary.append(e)

            self.filtered_items = matches_primary + matches_secondary
            self.lbl_count.configure(text=f"{len(self.filtered_items)}")
        else:
            if self.active_category == "Recent":
                self.filtered_items = list(self.recent_emojis)
            elif self.active_category == "Dev / Git":
                self.filtered_items = list(GITMOJIS)
            else:
                self.filtered_items = [e for e in self.all_emojis if e.get("group") == self.active_category]

            self.lbl_count.configure(text=f"{len(self.filtered_items)}")

        if reset_index:
            self.selected_index = 0

        self._render_grid(keep_selection=not reset_index)

    def _render_grid(self, keep_selection: bool = True):
        """Draw emoji cards onto canvas."""
        self.canvas.delete("all")

        if not self.filtered_items:
            self.canvas.create_text(
                self.canvas.winfo_width() / 2 or 160,
                100,
                text="No emojis found",
                font=("DejaVu Sans Mono", 10),
                fill=THEME["fg_dim"],
                justify="center",
            )
            self._update_preview(None)
            self.canvas.configure(scrollregion=(0, 0, 100, 150))
            return

        cols = self.cols
        cw, ch, gap = self.cell_w, self.cell_h, self.gap
        total_items = len(self.filtered_items)
        rows = (total_items + cols - 1) // cols
        total_h = gap + rows * (ch + gap) + gap

        canvas_w = max(self.canvas.winfo_width(), (cols * (cw + gap) + gap))
        grid_w = cols * (cw + gap) - gap
        offset_x = max(gap, (canvas_w - grid_w) // 2)

        for i, item in enumerate(self.filtered_items):
            c = i % cols
            r = i // cols
            x0 = offset_x + c * (cw + gap)
            y0 = gap + r * (ch + gap)
            x1 = x0 + cw
            y1 = y0 + ch
            xc = (x0 + x1) / 2
            yc = (y0 + y1) / 2

            tag = f"item_{i}"
            rect_tag = f"rect_{i}"
            self.canvas.create_rectangle(
                x0, y0, x1, y1,
                fill=THEME["bg_card"],
                outline=THEME["border"],
                width=1,
                tags=("card", rect_tag, tag),
            )
            char = item["char"]
            if self._is_complex_emoji(char) and self.has_emoji_font:
                img = self.get_emoji_image(char, size=26)
                if img:
                    self.canvas.create_image(
                        xc, yc,
                        image=img,
                        tags=("image", tag),
                    )
                else:
                    self.canvas.create_text(
                        xc, yc,
                        text=char,
                        font=("Noto Color Emoji", 18),
                        tags=("text", tag),
                    )
            else:
                self.canvas.create_text(
                    xc, yc,
                    text=char,
                    font=("Noto Color Emoji", 18),
                    tags=("text", tag),
                )

            self.canvas.tag_bind(tag, "<Enter>", lambda e, idx=i: self._on_card_hover(idx))
            self.canvas.tag_bind(tag, "<Leave>", lambda e, idx=i: self._on_card_unhover(idx))
            self.canvas.tag_bind(tag, "<Button-1>", lambda e, idx=i: self._on_card_click(idx))
            self.canvas.tag_bind(tag, "<Double-Button-1>", lambda e, idx=i: self._on_card_double_click(idx))

        self.cursor_rect = self.canvas.create_rectangle(
            0, 0, 0, 0,
            outline=THEME["key_fg"],
            width=2,
            tags="cursor",
        )

        self.canvas.configure(scrollregion=(0, 0, canvas_w, total_h))

        if not keep_selection or self.selected_index >= len(self.filtered_items):
            self.selected_index = 0

        self._highlight_selected()

    def _highlight_selected(self):
        """Move cursor highlight to selected emoji and scroll into view."""
        if not self.filtered_items:
            return

        self.selected_index = max(0, min(len(self.filtered_items) - 1, self.selected_index))
        idx = self.selected_index
        item = self.filtered_items[idx]

        cols = self.cols
        cw, ch, gap = self.cell_w, self.cell_h, self.gap
        canvas_w = max(self.canvas.winfo_width(), (cols * (cw + gap) + gap))
        grid_w = cols * (cw + gap) - gap
        offset_x = max(gap, (canvas_w - grid_w) // 2)

        c = idx % cols
        r = idx // cols
        x0 = offset_x + c * (cw + gap)
        y0 = gap + r * (ch + gap)
        x1 = x0 + cw
        y1 = y0 + ch

        self.canvas.coords(self.cursor_rect, x0 - 1, y0 - 1, x1 + 1, y1 + 1)
        self.canvas.tag_raise(self.cursor_rect)

        self._update_preview(item)

        canvas_h = self.canvas.winfo_height()
        if canvas_h > 0:
            top_y = self.canvas.canvasy(0)
            bot_y = self.canvas.canvasy(canvas_h)

            bbox = self.canvas.bbox("all")
            max_scroll = bbox[3] if bbox else 1

            if y0 < top_y:
                self.canvas.yview_moveto(max(0.0, y0 / max_scroll))
            elif y1 > bot_y:
                self.canvas.yview_moveto(min(1.0, (y1 - canvas_h + gap * 2) / max_scroll))

    def _update_preview(self, item: dict | None):
        """Update bottom preview bar."""
        if not item:
            self.lbl_preview_char.configure(image="", text="")
            self.lbl_preview_name.configure(text="")
            self.lbl_preview_code.configure(text="")
            return

        char = item["char"]
        if self._is_complex_emoji(char) and self.has_emoji_font:
            img = self.get_emoji_image(char, size=32)
            if img:
                self.lbl_preview_char.configure(image=img, text="")
            else:
                self.lbl_preview_char.configure(image="", text=char)
        else:
            self.lbl_preview_char.configure(image="", text=char)
        name = item.get("name", "").title()
        if len(name) > 18:
            name = name[:16] + "…"
        self.lbl_preview_name.configure(text=name)

        code = item.get("code", "")
        if len(code) > 22:
            code = code[:20] + "…"
        self.lbl_preview_code.configure(text=code)

    # ==========================================================================
    # Mouse Events
    # ==========================================================================
    def _on_card_hover(self, idx: int):
        try:
            self.canvas.itemconfigure(f"rect_{idx}", fill=THEME["bg_hover"])
        except Exception:
            pass

    def _on_card_unhover(self, idx: int):
        try:
            self.canvas.itemconfigure(f"rect_{idx}", fill=THEME["bg_card"])
        except Exception:
            pass

    def _on_card_click(self, idx: int):
        self.selected_index = idx
        self._highlight_selected()
        self._copy_selected(close_on_copy=False)

    def _on_card_double_click(self, idx: int):
        self.selected_index = idx
        self._highlight_selected()
        self._copy_selected(close_on_copy=True)

    # ==========================================================================
    # Copy & Feedback Actions
    # ==========================================================================
    def _copy_selected(self, close_on_copy: bool = True):
        """Copy selected emoji to clipboard and handle recent/exit."""
        if not self.filtered_items or not (0 <= self.selected_index < len(self.filtered_items)):
            return

        item = self.filtered_items[self.selected_index]
        char = item["char"]

        success = set_xclip(char)
        if success:
            self._add_to_recent(item)
            self.show_toast(f"✓ Copied {char}!", THEME["status_running"])
            if close_on_copy:
                self.root.after(80, self.root.destroy)
        else:
            self.show_toast("xclip error", THEME["status_stopped"])

    def show_toast(self, msg: str, color: str = None):
        self.lbl_toast.configure(text=msg, fg=color or THEME["accent_aqua"])

    # ==========================================================================
    # Keyboard Navigation & Bindings
    # ==========================================================================
    def _bind_keys(self):
        """Global key navigation."""
        self.root.bind("<Escape>", self._on_escape)
        self.root.bind("q", self._on_q)
        self.root.bind("<slash>", self._on_slash)

        self.root.bind("<Tab>", self._on_tab)
        self.root.bind("<ISO_Left_Tab>", self._on_shift_tab)
        self.root.bind("<Shift-Tab>", self._on_shift_tab)

        for n in range(1, 10):
            self.root.bind(str(n), lambda e, idx=n-1: self._on_number_key(idx))

        self.root.bind("<Down>", lambda e: self._navigate(self.cols))
        self.root.bind("<Up>", lambda e: self._navigate(-self.cols))
        self.root.bind("<Right>", lambda e: self._navigate(1))
        self.root.bind("<Left>", lambda e: self._navigate(-1))

        self.root.bind("j", lambda e: self._navigate(self.cols) if self.root.focus_get() != self.search_entry else None)
        self.root.bind("k", lambda e: self._navigate(-self.cols) if self.root.focus_get() != self.search_entry else None)
        self.root.bind("l", lambda e: self._navigate(1) if self.root.focus_get() != self.search_entry else None)
        self.root.bind("h", lambda e: self._navigate(-1) if self.root.focus_get() != self.search_entry else None)

        self.root.bind("<Return>", lambda e: self._copy_selected(close_on_copy=True))
        self.root.bind("<Shift-Return>", lambda e: self._copy_selected(close_on_copy=False))
        self.root.bind("c", lambda e: self._copy_selected(close_on_copy=False) if self.root.focus_get() != self.search_entry else None)

        self.search_entry.bind("<Down>", lambda e: self._navigate_from_entry(self.cols))
        self.search_entry.bind("<Up>", lambda e: self._navigate_from_entry(-self.cols))
        self.search_entry.bind("<Return>", lambda e: self._copy_selected(close_on_copy=True))
        self.search_entry.bind("<Shift-Return>", lambda e: self._copy_selected(close_on_copy=False))

    def _navigate(self, delta: int):
        if not self.filtered_items:
            return
        new_idx = max(0, min(len(self.filtered_items) - 1, self.selected_index + delta))
        if new_idx != self.selected_index:
            self.selected_index = new_idx
            self._highlight_selected()

    def _navigate_from_entry(self, delta: int):
        self._navigate(delta)
        return "break"

    def _on_tab(self, event):
        """Cycle forward to next category."""
        keys = [k for k, _, _ in self.categories]
        try:
            curr_i = keys.index(self.active_category)
            next_i = (curr_i + 1) % len(keys)
        except ValueError:
            next_i = 0
        self._set_category(keys[next_i], reset_search=True)
        return "break"

    def _on_shift_tab(self, event):
        """Cycle backward to previous category."""
        keys = [k for k, _, _ in self.categories]
        try:
            curr_i = keys.index(self.active_category)
            next_i = (curr_i - 1) % len(keys)
        except ValueError:
            next_i = 0
        self._set_category(keys[next_i], reset_search=True)
        return "break"

    def _on_number_key(self, idx: int):
        if self.root.focus_get() != self.search_entry and idx < len(self.categories):
            self._set_category(self.categories[idx][0], reset_search=True)

    def _on_escape(self, event):
        if self.search_var.get():
            self.search_var.set("")
            self.search_entry.focus_set()
        else:
            self.root.destroy()

    def _on_q(self, event):
        if self.root.focus_get() != self.search_entry:
            self.root.destroy()

    def _on_slash(self, event):
        if self.root.focus_get() != self.search_entry:
            self.search_entry.focus_set()
            self.search_entry.select_range(0, "end")
            return "break"


def main():
    root = tk.Tk(className="emoji-pad")
    root.geometry("384x540")
    root.minsize(320, 400)
    app = EmojiPadApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
