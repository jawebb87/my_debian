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
├── qtile/              # .config/qtile/ (config.py, autostart.sh)
├── kitty/              # .config/kitty/ (kitty.conf)
├── picom/              # .config/picom/ (picom.conf)
├── dunst/              # .config/dunst/ (dunstrc)
├── rofi/               # .config/rofi/ (config.rasi)
├── micro/              # .config/micro/ (bindings.json)
├── gtk/                # .config/gtk-3.0/, .config/gtk-4.0/
├── power/              # .config/ (power-limits.service, power-limits-sleep.sh)
├── bin/                # .local/bin/ (qtile-screenshot, apply-power-limits.sh)
└── scripts/            # Custom utility scripts (vim_cheat.py)
```

---

## Replication & Installation

A helper installer script is included to restore dotfiles and software packages on fresh installations:

```bash
chmod +x install.sh
./install.sh
```

### Manual Installation Commands:

1. **Restore all dotfiles via `cp`**:
   ```bash
   for dir in dotfiles/*; do
     [ -d "$dir" ] && [ "$(basename "$dir")" != "scripts" ] && cp -a "$dir"/. "$HOME"/
   done
   cp -a dotfiles/scripts/vim_cheat.py "$HOME/Projects/qtile_bench/"
   ```

2. **Or Symlink via GNU Stow**:
   ```bash
   sudo apt install stow
   for dir in dotfiles/*; do
     [ -d "$dir" ] && [ "$(basename "$dir")" != "scripts" ] && stow -d dotfiles -t ~ "$(basename "$dir")"
   done
   ```

3. **Restore manually installed packages**:
   ```bash
   sudo apt update && grep -vE '^\s*(#|$)' installed_packages.txt | sudo xargs apt install -y
   ```

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

### 4. Custom Qtile Scratchpads (`Super + v` & `Super + t`)
* **`Super + v`**: Toggles custom Python/Tkinter Vim cheatsheet (`~/Projects/qtile_bench/vim_cheat.py`) dropping down flush from the 26px top bar.
* **`Super + t`**: Toggles `btop` system monitor dropdown.
