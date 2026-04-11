#!/usr/bin/env bash
set -euo pipefail

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
else
  DESKTOP_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
fi

DESKTOP_FILE="$DESKTOP_DIR/io.github.archisman-panigrahi.vboard.desktop"

if [[ -f "$DESKTOP_FILE" ]]; then
  rm -f "$DESKTOP_FILE"
  echo "Removed: $DESKTOP_FILE"
else
  echo "No file to remove: $DESKTOP_FILE"
fi

update-desktop-database "$DESKTOP_DIR" >/dev/null 2>&1 || true
