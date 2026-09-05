#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: configure-plasma-keyboard.sh [--session] [--sddm]

  --session  Select the Vboard-wrapped Plasma Keyboard for the current user.
  --sddm     Configure the SDDM Wayland greeter (must run as root).

With no option, --session is used.
EOF
}

ENABLE_SESSION=0
ENABLE_SDDM=0
if [[ $# -eq 0 ]]; then
  ENABLE_SESSION=1
fi
while [[ $# -gt 0 ]]; do
  case "$1" in
    --session) ENABLE_SESSION=1 ;;
    --sddm) ENABLE_SDDM=1 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
  shift
done

find_desktop_entry() {
  local candidate
  for candidate in \
    "${XDG_DATA_HOME:-${HOME}/.local/share}/applications/io.github.archisman-panigrahi.vboard-plasma-keyboard.desktop" \
    /usr/local/share/applications/io.github.archisman-panigrahi.vboard-plasma-keyboard.desktop \
    /usr/share/applications/io.github.archisman-panigrahi.vboard-plasma-keyboard.desktop; do
    if [[ -f "$candidate" ]]; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done
  return 1
}

find_system_wrapper() {
  local candidate
  for candidate in \
    /usr/local/libexec/vboard-plasma-keyboard \
    /usr/libexec/vboard-plasma-keyboard; do
    if [[ -x "$candidate" ]]; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done
  return 1
}

if [[ "$ENABLE_SESSION" -eq 1 ]]; then
  DESKTOP_ENTRY="$(find_desktop_entry || true)"
  if [[ -z "$DESKTOP_ENTRY" ]]; then
    echo "Vboard Plasma Keyboard desktop entry is not installed." >&2
    exit 1
  fi
  KWRITECONFIG="$(command -v kwriteconfig6 || command -v kwriteconfig5 || true)"
  if [[ -z "$KWRITECONFIG" ]]; then
    echo "kwriteconfig was not found; cannot configure the Plasma session." >&2
    exit 1
  fi
  "$KWRITECONFIG" --file kwinrc --group Wayland --key InputMethod "$DESKTOP_ENTRY"
  "$KWRITECONFIG" --file kwinrc --group Wayland --key VirtualKeyboardEnabled true
  if command -v qdbus6 >/dev/null 2>&1; then
    qdbus6 org.kde.KWin /KWin reconfigure >/dev/null 2>&1 || true
  fi
  echo "Selected Vboard Plasma Keyboard for the current Plasma session."
fi

if [[ "$ENABLE_SDDM" -eq 1 ]]; then
  if [[ "$EUID" -ne 0 ]]; then
    echo "--sddm must be run as root." >&2
    exit 1
  fi
  WRAPPER="$(find_system_wrapper || true)"
  if [[ -z "$WRAPPER" ]]; then
    echo "A system-wide vboard-plasma-keyboard wrapper is required for SDDM." >&2
    exit 1
  fi
  CONFIG_DIR=/etc/sddm.conf.d
  CONFIG_FILE="$CONFIG_DIR/zzzzz-vboard-plasma-keyboard.conf"
  mkdir -p "$CONFIG_DIR"
  printf '%s\n' \
    '[Wayland]' \
    "CompositorCommand=kwin_wayland --no-global-shortcuts --no-lockscreen --inputmethod $WRAPPER --locale1" \
    >"$CONFIG_FILE"
  chmod 0644 "$CONFIG_FILE"
  echo "Configured Vboard Plasma Keyboard wrapper for SDDM: $CONFIG_FILE"
  echo "The change takes effect on the next SDDM start; no restart was performed."
fi
