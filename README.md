# My Debian Install

For a long time I've been using arch derivatives for my OS. Recently I've begun to realize that I didn't need nor want all my software to live on the bleeding edge. Add into that the fact that I am exploring the idea of a career change into sysadmin, I decided that I should move my daily driver over to debian and familiarize myself with the system at a base level so when I find work, I'm not struggling to remember two different architecture designs. This repo will be a log of installed software and any problems/solutions I run into as well as a repo for my dotfiles.

## The Hardware

- **CPU** : AMD Ryzen 5 3550H
- **GPU** : AMD Radeon RX 560X (Discrete) + Vega 8 (Integrated)
- **RAM** : 8GB DDR4 2400 MHz (todo: upgrade to 32GB)
- **Storage** : Samsung 970 EVO (500 GB NVMe)

## The OS

- **OS** : Debian GNU/Linux (Trixie)
- **WM** : Qtile (Python-based dynamic tiling window manager)
- **Compositor** : Picom
- **DM** : LightDM
- **Terminal** : Kitty (Gruvbox Dark theme)
- **Shell** : Bash (enhanced with `ble.sh` & `liquidprompt`)
- **FM** : Dolphin
- **Editor** : Vim / Kate / Micro
- **CLI Browser** : w3m

---

## Dotfiles Structure

Configs are organized into modular, GNU Stow-compatible component directories under `dotfiles/`:

```
dotfiles/
├── bash/               # .bashrc, .bash_aliases, .inputrc (prefix search)
├── bin/                # .local/bin/ (dots, qtile-fzf, qtile-notes, apply-power-limits.sh, play, termplay, etc.)
├── btop/               # .config/btop/ (btop.conf)
├── dunst/              # .config/dunst/ (dunstrc)
├── gtk/                # .config/gtk-3.0/, .config/gtk-4.0/ (settings.ini)
├── kitty/              # .config/kitty/ (kitty.conf, gruvbox-dark.conf, gruvbox-light.conf)
├── micro/              # .config/micro/ (bindings.json)
├── mpv/                # .config/mpv/ (mpv.conf with kitty vo & yt-dlp)
├── picom/              # .config/picom/ (picom.conf)
├── power/              # .config/ (power-limits.service, power-limits-sleep.sh)
├── qtile/              # .config/qtile/ (config.py, autostart.sh, theme.py)
├── rofi/               # .config/rofi/ (config.rasi)
├── scripts/            # Qtile bench dropdowns (linked to ~/Projects/qtile_bench/)
└── yt-dlp/             # .config/yt-dlp/ (config)
```

---

## Automated Dotfiles Management (`dots` CLI)

All dotfiles in `$HOME` and utility scripts in `~/Projects/qtile_bench` are managed via GNU Stow symlinks pointing directly into this repository. A global CLI utility `dots` (or `./manage.sh`) is provided for seamless sync and git workflows:

```bash
# Check symlink health and pending git changes
dots status

# View diff of any modified configuration files
dots diff

# Commit and push changes directly to GitHub
dots push "feat(qtile): add new keybindings"

# Restow or repair any symlinks (with automatic pre-stow backups)
dots stow

# Pull latest changes from git and restow
dots pull

# Adopt an existing configuration file into stow
dots add ~/.config/app/config [package_name]
```

### Convenient Shell Aliases:
- `dots` -> runs `dots status`
- `dotstatus` -> quick symlink and git status
- `dotdiff` -> colored git diff of dotfile modifications
- `dotpush` -> stage, commit, and push changes
- `dotstow` -> restow all packages

---

## Replication & Installation

A helper installer script is included to restore dotfiles and software packages on fresh installations:

```bash
chmod +x install.sh
./install.sh
```

### Installation Options:

1. **Option 1: Standard Copy (`cp`)**: Copies files directly to `$HOME` and `~/Projects/qtile_bench/`.
2. **Option 2: Symlink via GNU Stow (`dots stow`)**: Installs GNU Stow if needed, backs up any conflicting regular files to `~/.dotfiles_backup/`, and creates live symlinks.
3. **Option 3: Restore APT packages**: Installs all software listed in `installed_packages.txt`.
4. **Option 4: Everything**: Full package install + automated dotfile stow.

---

## Key Hardware & Software Tweaks

### 1. ASUS TUF FX505 Fan Control
* **Issue**: The ASUS EC BIOS firmware enforces a ~2700 RPM fan floor in "Balanced" mode, even when idle at ~36°C.
* **Fix**: Switch the Linux ACPI platform profile to `quiet` mode:
  ```bash
  echo quiet | sudo tee /sys/firmware/acpi/platform_profile
  ```
  *(Or cycle with the `Fn + F5` fan hotkey).*

### 2. Unicode & Emoji Rendering (No Tofu Boxes)
* Debian minimal installs lack color emoji fonts by default.
* Installed Google Noto Color Emoji:
  ```bash
  sudo apt install fonts-noto-color-emoji
  fc-cache -f -v
  ```
* In Kitty, reload fonts live with `Ctrl + Shift + F5`.

### 3. Fish-like Bash Line Editing
* **`ble.sh`**: Provides Fish-style syntax highlighting, ghost-text autosuggestions, and tab pager inside pure Bash.
* **`~/.inputrc`**: Adds prefix history search with `Up` / `Down` arrows.
* **`bind Space:magic-space`**: Automatically expands aliases like Fish abbreviations.

### 4. Custom Qtile Scratchpads & Launchers
* **`Super + v`**: Toggles custom Python/Tkinter Vim cheatsheet (`~/Projects/qtile_bench/vim_cheat.py`) dropping down flush from the 26px top bar.
* **`Super + d`**: Toggles custom Python/Tkinter Docker services dashboard (`~/Projects/qtile_bench/docker_pad.py`) with live status, restart/stop/start hotkeys, and container log inspection.
* **`Super + x`**: Toggles custom Python/Tkinter Clipboard history scratchpad (`~/Projects/qtile_bench/clip_pad.py`) with live sync, format detection, and quick copy/delete.
* **`Super + y`**: Raise or run Limusic YouTube Music player AppImage (`~/.local/bin/limusic.AppImage`).
* **`Super + t`**: Toggles `btop` system monitor dropdown.

### 5. Terminal Video Player (`termplay` / `play`)
Stream web videos (YouTube, Twitch, etc.) or local files directly inside any Kitty terminal pane using Kitty Graphics Protocol:
* `play <URL>`: Stream video directly in terminal pane.
* `play <search query>`: Search YouTube and stream matching result.
* `play`: Auto-detects URL from clipboard or prompts.
* `play -a <URL>`: Audio-only stream.
* In-player controls: `Space` (pause), `Left`/`Right` (seek 5s), `9`/`0` (volume), `q` (quit).
