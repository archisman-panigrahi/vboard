#!/usr/bin/env bash
set -euo pipefail

SCRIPTS_DIR="${1:-}"
INSTALL_PREFIX="${2:-/usr/local}"

if [[ -z "$SCRIPTS_DIR" ]]; then
  echo "vboard: missing scripts directory argument; skipping KDE post-install hooks"
  exit 0
fi

# Do not mutate user config during staged package builds.
if [[ -n "${DESTDIR:-}" ]]; then
  echo "vboard: DESTDIR is set; skipping KDE post-install hooks"
  exit 0
fi

run_script() {
  local script_path="$1"
  shift
  if [[ ! -x "$script_path" ]]; then
    echo "vboard: not executable or missing: $script_path"
    return 0
  fi

  if ! bash "$script_path" "$@"; then
    echo "vboard: warning: script failed: $script_path"
  fi
}

scope="system"
if [[ "$INSTALL_PREFIX" == "$HOME"* ]]; then
  scope="user"
fi

export VBOARD_PREFIX="$INSTALL_PREFIX"
export VBOARD_INSTALL_SCOPE="$scope"

if [[ ! -x "$SCRIPTS_DIR/setup-uinput.sh" ]]; then
  echo "vboard: missing required script: $SCRIPTS_DIR/setup-uinput.sh" >&2
  exit 1
fi

if [[ "$EUID" -eq 0 ]]; then
  bash "$SCRIPTS_DIR/setup-uinput.sh" "--scope=$scope"
else
  echo "vboard: non-root install detected; skipping uinput setup"
fi

session_hint="${XDG_CURRENT_DESKTOP:-} ${DESKTOP_SESSION:-} ${KDE_FULL_SESSION:-}"
session_lc="$(printf '%s' "$session_hint" | tr '[:upper:]' '[:lower:]')"

if [[ "$session_lc" != *kde* && "$session_lc" != *plasma* ]]; then
  echo "vboard: KDE/Plasma session not detected; skipping OSK and KWin setup"
  exit 0
fi

run_script "$SCRIPTS_DIR/install-plasma-osk.sh" "--scope=$scope"
run_script "$SCRIPTS_DIR/install-kwin-rule.sh" "--scope=$scope"
