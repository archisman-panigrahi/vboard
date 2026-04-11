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

if [[ "$EUID" -ne 0 ]]; then
  echo "vboard: setup-uinput.sh must be run with sudo/root" >&2
  exit 1
fi

if [[ "$SCOPE" == "auto" ]]; then
  if [[ "$SYSTEM_PREFIX" == "$HOME"* ]]; then
    SCOPE="user"
  elif [[ "$EUID" -eq 0 ]]; then
    SCOPE="system"
  else
    SCOPE="user"
  fi
fi

echo "vboard: checking uinput availability"

if ! lsmod | grep -q '^uinput\b'; then
  modprobe uinput
  echo "vboard: loaded uinput kernel module"
else
  echo "vboard: uinput module already loaded"
fi

if [[ "$SCOPE" == "system" ]]; then
  modules_file="/etc/modules-load.d/uinput.conf"
  if [[ ! -f "$modules_file" ]] || ! grep -qx 'uinput' "$modules_file"; then
    echo 'uinput' > "$modules_file"
    echo "vboard: enabled uinput module at boot via $modules_file"
  fi
fi

if [[ -e /dev/uinput ]]; then
  if [[ -r /dev/uinput && -w /dev/uinput ]]; then
    echo "vboard: /dev/uinput is accessible"
  else
    echo "vboard: /dev/uinput exists but is permission-restricted" >&2
    exit 1
  fi
else
  echo "vboard: /dev/uinput not found; ensure kernel supports uinput and module is available" >&2
  exit 1
fi

echo "vboard: if uinput permissions are not effective yet, log out/log in or restart your computer."
