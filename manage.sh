#!/usr/bin/env bash
# ==============================================================================
# manage.sh - Automated GNU Stow & Git Workflow for my_debian Dotfiles
# ==============================================================================
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOTFILES_DIR="$REPO_DIR/dotfiles"
TARGET_HOME="$HOME"
TARGET_BENCH="$HOME/Projects/qtile_bench"
BACKUP_BASE="$HOME/.dotfiles_backup"

# ANSI Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Helper functions
msg_info() { echo -e "${CYAN}==>${NC} ${BOLD}$1${NC}"; }
msg_ok()   { echo -e "${GREEN}✓${NC} $1"; }
msg_warn() { echo -e "${YELLOW}▲${NC} $1"; }
msg_err()  { echo -e "${RED}✗${NC} $1"; }

check_stow_installed() {
    if ! command -v stow &>/dev/null; then
        msg_warn "GNU Stow is not installed."
        read -rp "Install stow now via sudo apt? [Y/n]: " ans
        if [[ "$ans" =~ ^[Nn] ]]; then
            msg_err "GNU Stow is required to proceed."
            exit 1
        fi
        sudo apt update && sudo apt install -y stow
    fi
}

get_packages() {
    local pkgs=()
    for d in "$DOTFILES_DIR"/*; do
        if [ -d "$d" ]; then
            local b
            b=$(basename "$d")
            if [ "$b" != "scripts" ]; then
                pkgs+=("$b")
            fi
        fi
    done
    echo "${pkgs[@]}"
}

# Resolve conflicts by safely backing up regular files before stowing
backup_conflicts_for_package() {
    local pkg="$1"
    local target_dir="$2"
    local pkg_dir="$DOTFILES_DIR/$pkg"
    local backup_dir="$3"

    cd "$pkg_dir"
    while IFS= read -r -d '' rel_file; do
        rel_file="${rel_file#./}"
        local dest_file="$target_dir/$rel_file"
        
        # If target exists and is a regular file (NOT a symlink)
        if [ -e "$dest_file" ] && [ ! -L "$dest_file" ]; then
            mkdir -p "$backup_dir/$(dirname "$rel_file")"
            msg_warn "Backing up existing regular file: $dest_file"
            mv "$dest_file" "$backup_dir/$rel_file"
        elif [ -L "$dest_file" ] && [ ! -e "$dest_file" ]; then
            # Broken symlink
            rm -f "$dest_file"
        fi
    done < <(find . -type f -print0 -o -type l -print0)
    cd "$REPO_DIR"
}

cmd_stow() {
    check_stow_installed
    msg_info "Stowing all dotfile packages..."

    local timestamp
    timestamp=$(date +%Y%m%d_%H%M%S)
    local backup_dir="$BACKUP_BASE/stow_backup_$timestamp"

    # Ensure required parent target directories exist
    mkdir -p "$TARGET_HOME/.config" "$TARGET_HOME/.local/bin" "$TARGET_BENCH"

    local packages
    packages=$(get_packages)

    for pkg in $packages; do
        echo -e "  -> Preparing ${BOLD}$pkg${NC}..."
        backup_conflicts_for_package "$pkg" "$TARGET_HOME" "$backup_dir"
        stow -R -d "$DOTFILES_DIR" -t "$TARGET_HOME" "$pkg"
    done

    # Handle scripts targeting qtile_bench
    if [ -d "$DOTFILES_DIR/scripts" ]; then
        echo -e "  -> Preparing ${BOLD}scripts${NC} (targeting $TARGET_BENCH)..."
        backup_conflicts_for_package "scripts" "$TARGET_BENCH" "$backup_dir"
        stow -R -d "$DOTFILES_DIR" -t "$TARGET_BENCH" scripts
        # Ensure qtile_bench has theme.py pointing to active qtile theme
        ln -sf "$TARGET_HOME/.config/qtile/theme.py" "$TARGET_BENCH/theme.py"
    fi

    # Clean up empty backup directory if nothing was backed up
    if [ -d "$backup_dir" ] && [ -z "$(ls -A "$backup_dir")" ]; then
        rm -rf "$backup_dir"
    elif [ -d "$backup_dir" ]; then
        msg_ok "Pre-existing files backed up to: $backup_dir"
    fi

    # Ensure executables retain permissions
    chmod +x "$DOTFILES_DIR"/bin/.local/bin/* 2>/dev/null || true
    chmod +x "$DOTFILES_DIR"/scripts/* 2>/dev/null || true
    chmod +x "$REPO_DIR/manage.sh" "$REPO_DIR/install.sh" 2>/dev/null || true

    msg_ok "All dotfiles successfully stowed and symlinked!"
}

cmd_unstow() {
    check_stow_installed
    msg_warn "Unstowing all dotfile packages..."

    local packages
    packages=$(get_packages)

    for pkg in $packages; do
        echo -e "  -> Unstowing ${BOLD}$pkg${NC}..."
        stow -D -d "$DOTFILES_DIR" -t "$TARGET_HOME" "$pkg"
    done

    if [ -d "$DOTFILES_DIR/scripts" ]; then
        echo -e "  -> Unstowing ${BOLD}scripts${NC}..."
        stow -D -d "$DOTFILES_DIR" -t "$TARGET_BENCH" scripts
    fi

    msg_ok "All packages unstowed."
}

cmd_status() {
    echo -e "${BOLD}======================================================${NC}"
    echo -e "${BOLD}        GNU Stow & Dotfiles Status Report             ${NC}"
    echo -e "${BOLD}======================================================${NC}"

    local packages
    packages=$(get_packages)
    local all_ok=true

    echo -e "\n${BOLD}[1] Symlink Health:${NC}"
    for pkg in $packages; do
        local pkg_ok=true
        local count=0
        while IFS= read -r -d '' rel_file; do
            rel_file="${rel_file#./}"
            local dest_file="$TARGET_HOME/$rel_file"
            count=$((count + 1))
            if [ ! -L "$dest_file" ]; then
                pkg_ok=false
                all_ok=false
                echo -e "  ${RED}✗${NC} $pkg: $dest_file is NOT a symlink"
            fi
        done < <(cd "$DOTFILES_DIR/$pkg" && find . -type f -print0 -o -type l -print0)
        if [ "$pkg_ok" = true ]; then
            echo -e "  ${GREEN}✓${NC} ${BOLD}$pkg${NC} ($count files linked)"
        fi
    done

    # Check scripts
    if [ -d "$DOTFILES_DIR/scripts" ]; then
        local scripts_ok=true
        local count=0
        while IFS= read -r -d '' rel_file; do
            rel_file="${rel_file#./}"
            local dest_file="$TARGET_BENCH/$rel_file"
            count=$((count + 1))
            if [ ! -L "$dest_file" ]; then
                scripts_ok=false
                all_ok=false
                echo -e "  ${RED}✗${NC} scripts: $dest_file is NOT a symlink"
            fi
        done < <(cd "$DOTFILES_DIR/scripts" && find . -type f -print0 -o -type l -print0)
        if [ "$scripts_ok" = true ]; then
            echo -e "  ${GREEN}✓${NC} ${BOLD}scripts${NC} ($count scripts linked to qtile_bench)"
        fi
    fi

    echo -e "\n${BOLD}[2] Git Repository Status (my_debian):${NC}"
    cd "$REPO_DIR"
    local git_stat
    git_stat=$(git status -s)
    if [ -z "$git_stat" ]; then
        echo -e "  ${GREEN}✓ Working tree clean.${NC} No pending changes."
    else
        echo -e "  ${YELLOW}Pending changes in dotfiles:${NC}"
        git status -s | sed 's/^/    /'
    fi

    local unpushed
    unpushed=$(git log origin/main..HEAD --oneline 2>/dev/null || true)
    if [ -n "$unpushed" ]; then
        echo -e "\n  ${YELLOW}Unpushed commits:${NC}"
        echo "$unpushed" | sed 's/^/    /'
    fi
    echo ""
}

cmd_diff() {
    cd "$REPO_DIR"
    git diff "$@"
}

cmd_push() {
    cd "$REPO_DIR"
    local stat
    stat=$(git status -s)
    local unpushed
    unpushed=$(git log origin/main..HEAD --oneline 2>/dev/null || true)

    if [ -z "$stat" ] && [ -z "$unpushed" ]; then
        msg_ok "Working tree clean and all commits already pushed to origin/main."
        return 0
    fi

    if [ -n "$stat" ]; then
        echo -e "${YELLOW}Modified dotfiles:${NC}"
        git status -s | sed 's/^/  /'
        echo ""

        local commit_msg="${1:-}"
        if [ -z "$commit_msg" ]; then
            read -rp "Enter commit message (or press enter for default): " commit_msg
        fi

        if [ -z "$commit_msg" ]; then
            commit_msg="chore(dotfiles): update system configs ($(date +'%Y-%m-%d %H:%M'))"
        fi

        msg_info "Staging all changes..."
        git add -A

        msg_info "Committing with message: '$commit_msg'..."
        git commit -m "$commit_msg"
    fi

    msg_info "Pushing to origin main..."
    git push origin main
    msg_ok "Successfully pushed dotfiles to GitHub!"
}

cmd_pull() {
    cd "$REPO_DIR"
    msg_info "Pulling latest changes from origin main..."
    git pull --rebase origin main
    msg_info "Restowing packages..."
    cmd_stow
}

cmd_add() {
    local target_path="${1:-}"
    local custom_pkg="${2:-}"

    if [ -z "$target_path" ]; then
        msg_err "Usage: manage.sh add <file-path> [package-name]"
        exit 1
    fi

    # Expand to absolute path
    local abs_path
    abs_path=$(realpath "$target_path")

    if [ ! -e "$abs_path" ]; then
        msg_err "File does not exist: $abs_path"
        exit 1
    fi

    if [[ "$abs_path" != "$TARGET_HOME"* ]]; then
        msg_err "File must reside within \$HOME: $abs_path"
        exit 1
    fi

    local rel_path="${abs_path#$TARGET_HOME/}"

    # Determine package name if not provided
    local pkg="$custom_pkg"
    if [ -z "$pkg" ]; then
        if [[ "$rel_path" == .config/* ]]; then
            pkg=$(echo "$rel_path" | cut -d'/' -f2)
        elif [[ "$rel_path" == .local/bin/* ]]; then
            pkg="bin"
        elif [[ "$rel_path" == .* ]]; then
            pkg="bash"
        else
            read -rp "Enter package name for this file: " pkg
        fi
    fi

    local dest_in_pkg="$DOTFILES_DIR/$pkg/$rel_path"
    mkdir -p "$(dirname "$dest_in_pkg")"

    msg_info "Adopting $rel_path into package '$pkg'..."
    mv "$abs_path" "$dest_in_pkg"
    stow -R -d "$DOTFILES_DIR" -t "$TARGET_HOME" "$pkg"
    msg_ok "File $rel_path stowed under package $pkg!"
}

cmd_help() {
    echo -e "${BOLD}my_debian Dotfiles & GNU Stow Automation Tool${NC}"
    echo ""
    echo "Usage: dots [command] [options]  (or ./manage.sh [command])"
    echo ""
    echo "Commands:"
    echo "  stow, link, sync    Stow all dotfile packages to ~ and scripts to qtile_bench"
    echo "  unstow, unlink      Remove all stow symlinks"
    echo "  status              Display symlink health and pending git changes"
    echo "  diff [args]         Show git diff of your modified config files"
    echo "  push [message]      Stage, commit, and push changes to remote GitHub repo"
    echo "  pull                Pull latest changes and restow all packages"
    echo "  add <file> [pkg]    Adopt an existing file into a stow package"
    echo "  help                Show this help message"
    echo ""
}

# Main routing
action="${1:-status}"
shift || true

case "$action" in
    stow|link|sync|restow)
        cmd_stow
        ;;
    unstow|unlink)
        cmd_unstow
        ;;
    status)
        cmd_status
        ;;
    diff)
        cmd_diff "$@"
        ;;
    push)
        cmd_push "$@"
        ;;
    pull)
        cmd_pull
        ;;
    add)
        cmd_add "$@"
        ;;
    help|--help|-h)
        cmd_help
        ;;
    *)
        msg_err "Unknown action: $action"
        cmd_help
        exit 1
        ;;
esac
