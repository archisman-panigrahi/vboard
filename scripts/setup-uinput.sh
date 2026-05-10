#!/usr/bin/env bash
set -euo pipefail

DEFAULT_SCOPE="${VBOARD_INSTALL_SCOPE:-auto}"
SCOPE="$DEFAULT_SCOPE"
SYSTEM_PREFIX="${VBOARD_PREFIX:-/usr/local}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UDEV_RULE_SOURCE="$SCRIPT_DIR/../udev/70-vboard-uinput.rules"
UDEV_RULE_DEST="/etc/udev/rules.d/70-vboard-uinput.rules"

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

reload_udev_rules() {
  if ! command -v udevadm >/dev/null 2>&1; then
    echo "vboard: udevadm not found; reload udev rules manually if permissions do not update"
    return 0
  fi

  udevadm control --reload-rules >/dev/null 2>&1 || true

  if [[ -e /dev/uinput ]]; then
    udevadm trigger --subsystem-match=misc --sysname-match=uinput >/dev/null 2>&1 || true
  fi
}

install_udev_rule() {
  if [[ "$SCOPE" != "system" ]]; then
    echo "vboard: user-scope install detected; skipping system udev rule installation"
    return 0
  fi

  if [[ ! -f "$UDEV_RULE_SOURCE" ]]; then
    echo "vboard: missing udev rule source: $UDEV_RULE_SOURCE" >&2
    exit 1
  fi

  install -Dm644 "$UDEV_RULE_SOURCE" "$UDEV_RULE_DEST"
  echo "vboard: installed udev rule at $UDEV_RULE_DEST"
  reload_udev_rules
}

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

install_udev_rule

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
