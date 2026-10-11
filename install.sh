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

    # Ensure vim cheatsheet is in Projects/qtile_bench
    if [ -f "$DOTFILES_DIR/scripts/vim_cheat.py" ]; then
        cp -a "$DOTFILES_DIR/scripts/vim_cheat.py" "$HOME/Projects/qtile_bench/"
        chmod +x "$HOME/Projects/qtile_bench/vim_cheat.py"
    fi

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

    if [ -f "$DOTFILES_DIR/scripts/vim_cheat.py" ]; then
        ln -sf "$DOTFILES_DIR/scripts/vim_cheat.py" "$HOME/Projects/qtile_bench/vim_cheat.py"
        chmod +x "$DOTFILES_DIR/scripts/vim_cheat.py"
    fi

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
