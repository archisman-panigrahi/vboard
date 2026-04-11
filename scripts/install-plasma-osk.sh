#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_SCOPE="${VBOARD_INSTALL_SCOPE:-auto}"
SCOPE="$DEFAULT_SCOPE"
SYSTEM_PREFIX="${VBOARD_PREFIX:-/usr/local}"

for arg in "$@"; do
  case "$arg" in
    --scope=user|--scope=system|--scope=auto)
      SCOPE="${arg#--scope=}"
      ;;
    *)
      echo "Unknown argument: $arg" >&2
      echo "Usage: $0 [--scope=user|system|auto]" >&2
      exit 1
      ;;
  esac
done

if [[ "$SCOPE" == "auto" ]]; then
  if [[ "$SYSTEM_PREFIX" == "$HOME"* ]]; then
    SCOPE="user"
  elif [[ "$EUID" -eq 0 ]]; then
    SCOPE="system"
  elif [[ -w "$SYSTEM_PREFIX/share/applications" || ! -e "$SYSTEM_PREFIX/share/applications" ]]; then
    SCOPE="system"
  else
    SCOPE="user"
  fi
fi

if [[ "$SCOPE" == "system" ]]; then
  DESKTOP_DIR="$SYSTEM_PREFIX/share/applications"
  SOURCE_DESKTOP_FILE="$SYSTEM_PREFIX/share/vboard/org.mdev.vboard.desktop"
else
  DESKTOP_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
  SOURCE_DESKTOP_FILE="$SCRIPT_DIR/../org.mdev.vboard.desktop"
fi

DESKTOP_FILE="$DESKTOP_DIR/org.mdev.vboard.desktop"

if [[ ! -f "$SOURCE_DESKTOP_FILE" ]]; then
  echo "Desktop file not found: $SOURCE_DESKTOP_FILE" >&2
  exit 1
fi

mkdir -p "$DESKTOP_DIR"
cp "$SOURCE_DESKTOP_FILE" "$DESKTOP_FILE"

update-desktop-database "$DESKTOP_DIR" >/dev/null 2>&1 || true

echo "Installed: $DESKTOP_FILE"
echo "Open System Settings > Input Devices > Virtual Keyboard and select Vboard."
