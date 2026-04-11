#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: scripts/meson-install.sh [OPTIONS]

Quick Meson install helper for local development.

Options:
  --builddir <dir>   Meson build directory (default: builddir)
  --prefix <path>    Install prefix (default: ~/.local)
  --system           Shortcut for --prefix /usr/local
  --sudo             Use sudo for the install step
  -h, --help         Show this help
EOF
}

BUILD_DIR="builddir"
PREFIX="${HOME}/.local"
USE_SUDO=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --builddir)
      BUILD_DIR="${2:-}"
      shift 2
      ;;
    --prefix)
      PREFIX="${2:-}"
      shift 2
      ;;
    --system)
      PREFIX="/usr/local"
      shift
      ;;
    --sudo)
      USE_SUDO=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ -z "$BUILD_DIR" || -z "$PREFIX" ]]; then
  echo "builddir and prefix must be non-empty" >&2
  exit 2
fi

if [[ -d "$BUILD_DIR" ]]; then
  meson setup "$BUILD_DIR" --prefix "$PREFIX" --reconfigure
else
  meson setup "$BUILD_DIR" --prefix "$PREFIX"
fi

meson compile -C "$BUILD_DIR"

if [[ "$USE_SUDO" -eq 1 ]]; then
  sudo meson install -C "$BUILD_DIR"
else
  meson install -C "$BUILD_DIR"
fi

echo "Installed vboard to prefix: $PREFIX"
echo "Uninstall with: meson compile -C $BUILD_DIR uninstall-local"
