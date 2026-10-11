#!/usr/bin/env bash
# ==============================================================================
# My Debian Setup & Dotfiles Installer
# ==============================================================================
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOTFILES_DIR="$REPO_DIR/dotfiles"

echo "============================================="
echo "   My Debian System & Dotfiles Installer"
echo "============================================="
echo ""
echo "Choose an action:"
echo "  1) Copy dotfiles to ~ (Standard cp)"
echo "  2) Symlink dotfiles to ~ (via GNU Stow)"
echo "  3) Install packages from installed_packages.txt"
echo "  4) Everything (Packages + Copy Dotfiles)"
echo "  q) Quit"
echo ""
read -rp "Enter choice [1-4, q]: " choice

copy_dotfiles() {
    echo "==> Copying dotfiles to $HOME..."
    mkdir -p "$HOME/.config" "$HOME/.local/bin" "$HOME/Projects/qtile_bench"

    # Copy all component folders into home directory
    for dir in "$DOTFILES_DIR"/*; do
        if [ -d "$dir" ] && [ "$(basename "$dir")" != "scripts" ]; then
            echo "    -> Installing $(basename "$dir")..."
            cp -a "$dir"/. "$HOME"/
        fi
    done

    # Ensure scratchpad scripts are in Projects/qtile_bench
    for script in vim_cheat.py docker_pad.py clip_pad.py; do
        if [ -f "$DOTFILES_DIR/scripts/$script" ]; then
            cp -a "$DOTFILES_DIR/scripts/$script" "$HOME/Projects/qtile_bench/"
            chmod +x "$HOME/Projects/qtile_bench/$script"
        fi
    done

    # Ensure local bin scripts are executable
    chmod +x "$HOME/.local/bin/"* 2>/dev/null || true
    echo "✓ Dotfiles copied successfully!"
}

stow_dotfiles() {
    if ! command -v stow &>/dev/null; then
        echo "GNU Stow is not installed. Installing stow..."
        sudo apt update && sudo apt install -y stow
    fi

    echo "==> Symlinking dotfiles via GNU Stow..."
    mkdir -p "$HOME/.config" "$HOME/.local/bin" "$HOME/Projects/qtile_bench"

    for dir in "$DOTFILES_DIR"/*; do
        if [ -d "$dir" ] && [ "$(basename "$dir")" != "scripts" ]; then
            pkg=$(basename "$dir")
            echo "    -> Stowing $pkg..."
            stow -d "$DOTFILES_DIR" -t "$HOME" "$pkg"
        fi
    done

    for script in vim_cheat.py docker_pad.py clip_pad.py; do
        if [ -f "$DOTFILES_DIR/scripts/$script" ]; then
            ln -sf "$DOTFILES_DIR/scripts/$script" "$HOME/Projects/qtile_bench/$script"
            chmod +x "$DOTFILES_DIR/scripts/$script"
        fi
    done

    echo "✓ Dotfiles symlinked successfully via Stow!"
}

install_packages() {
    local pkg_file="$REPO_DIR/installed_packages.txt"
    if [ ! -f "$pkg_file" ]; then
        echo "Error: $pkg_file not found."
        return 1
    fi
    sudo apt update
    grep -vE '^\s*(#|$)' "$pkg_file" | sudo xargs apt install -y
    echo "✓ Packages installed successfully!"
}

case "$choice" in
    1)
        copy_dotfiles
        ;;
    2)
        stow_dotfiles
        ;;
    3)
        install_packages
        ;;
    4)
        install_packages
        copy_dotfiles
        ;;
    q|Q)
        echo "Exiting."
        exit 0
        ;;
    *)
        echo "Invalid choice."
        exit 1
        ;;
esac
