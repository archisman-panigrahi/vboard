#!/usr/bin/env bash
set -euo pipefail

SCRIPTS_DIR="${1:-}"
INSTALL_PREFIX="${2:-/usr/local}"
APPLICATIONS_DIR="${3:-$INSTALL_PREFIX/share/applications}"

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

refresh_desktop_database() {
  local applications_dir="$1"
  if [[ -z "$applications_dir" ]]; then
    return 0
  fi

  mkdir -p "$applications_dir"
  update-desktop-database "$applications_dir" >/dev/null 2>&1 || true
}

refresh_plasma_cache() {
  local sycoca_cmd=""

  for candidate in kbuildsycoca6 kbuildsycoca5 kbuildsycoca; do
    if command -v "$candidate" >/dev/null 2>&1; then
      sycoca_cmd="$candidate"
      break
    fi
  done

  if [[ -z "$sycoca_cmd" ]]; then
    echo "vboard: kbuildsycoca not found; Plasma cache will refresh later"
    return 0
  fi

  if [[ "$EUID" -eq 0 && "$scope" == "system" ]]; then
    echo "vboard: root install detected; skipping per-user Plasma cache refresh"
    return 0
  fi

  if ! "$sycoca_cmd" --noincremental >/dev/null 2>&1; then
    echo "vboard: warning: failed to refresh Plasma cache with $sycoca_cmd"
  fi
}

scope="system"
if [[ "$INSTALL_PREFIX" == "$HOME"* ]]; then
  scope="user"
fi

export VBOARD_PREFIX="$INSTALL_PREFIX"
export VBOARD_INSTALL_SCOPE="$scope"

refresh_desktop_database "$APPLICATIONS_DIR"

if [[ ! -x "$SCRIPTS_DIR/setup-uinput.sh" ]]; then
  echo "vboard: missing required script: $SCRIPTS_DIR/setup-uinput.sh" >&2
  exit 1
fi

if [[ "$EUID" -eq 0 ]]; then
  bash "$SCRIPTS_DIR/setup-uinput.sh" "--scope=$scope"
else
  echo "vboard: non-root install detected; skipping uinput setup"
fi

run_script "$SCRIPTS_DIR/install-kwin-rule.sh" "--scope=$scope"

session_hint="${XDG_CURRENT_DESKTOP:-} ${DESKTOP_SESSION:-} ${KDE_FULL_SESSION:-}"
session_lc="$(printf '%s' "$session_hint" | tr '[:upper:]' '[:lower:]')"

if [[ "$session_lc" != *kde* && "$session_lc" != *plasma* ]]; then
  echo "vboard: KDE/Plasma session not detected; skipping Plasma cache refresh"
  exit 0
fi

refresh_plasma_cache
echo "Open System Settings > Input Devices > Virtual Keyboard and select Vboard."
