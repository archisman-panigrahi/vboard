#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 3 ]]; then
  echo "Usage: $0 <prefix> <bindir> <datadir>" >&2
  exit 2
fi

PREFIX="$1"
BINDIR_OPT="$2"
DATADIR_OPT="$3"

resolve_dir() {
  local prefix="$1"
  local value="$2"
  if [[ "$value" = /* ]]; then
    printf '%s\n' "$value"
  else
    printf '%s\n' "$prefix/$value"
  fi
}

run_script() {
  local script_path="$1"
  shift

  if [[ ! -x "$script_path" ]]; then
    echo "vboard: skipping missing/non-executable script: $script_path"
    return 0
  fi

  if ! bash "$script_path" "$@"; then
    echo "vboard: warning: script failed: $script_path"
  fi
}

BINDIR="$(resolve_dir "$PREFIX" "$BINDIR_OPT")"
DATADIR="$(resolve_dir "$PREFIX" "$DATADIR_OPT")"
VBOARD_DATA_DIR="$DATADIR/vboard"
SCRIPTS_DIR="$VBOARD_DATA_DIR/scripts"

export VBOARD_PREFIX="$PREFIX"
export VBOARD_INSTALL_SCOPE="${VBOARD_INSTALL_SCOPE:-auto}"

# Undo user/system integration before removing the helper scripts themselves.
run_script "$SCRIPTS_DIR/uninstall-plasma-osk.sh" "--scope=auto"
run_script "$SCRIPTS_DIR/uninstall-kwin-rule.sh" "--scope=auto"

remove_file() {
  local path="$1"
  if [[ -e "$path" || -L "$path" ]]; then
    rm -f "$path"
    echo "removed: $path"
  fi
}

remove_file "$BINDIR/vboard"
remove_file "$DATADIR/applications/io.github.archisman-panigrahi.vboard.desktop"
remove_file "$DATADIR/icons/hicolor/scalable/apps/io.github.archisman-panigrahi.vboard.svg"
remove_file "$VBOARD_DATA_DIR/io.github.archisman-panigrahi.vboard.desktop"
remove_file "$VBOARD_DATA_DIR/uinput.md"
remove_file "$VBOARD_DATA_DIR/LICENSE"
remove_file "$SCRIPTS_DIR/install-plasma-osk.sh"
remove_file "$SCRIPTS_DIR/uninstall-plasma-osk.sh"
remove_file "$SCRIPTS_DIR/install-kwin-rule.sh"
remove_file "$SCRIPTS_DIR/uninstall-kwin-rule.sh"

# Prune empty directories we touched; ignore non-empty dirs.
rmdir "$SCRIPTS_DIR" 2>/dev/null || true
rmdir "$VBOARD_DATA_DIR" 2>/dev/null || true
rmdir "$DATADIR/applications" 2>/dev/null || true
rmdir "$DATADIR/icons/hicolor/scalable/apps" 2>/dev/null || true
rmdir "$DATADIR/icons/hicolor/scalable" 2>/dev/null || true
rmdir "$DATADIR/icons/hicolor" 2>/dev/null || true
rmdir "$DATADIR/icons" 2>/dev/null || true

update-desktop-database "$DATADIR/applications" >/dev/null 2>&1 || true
