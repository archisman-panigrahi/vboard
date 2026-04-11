#!/usr/bin/env bash
set -euo pipefail

RULE_NAME="vboard"
DEFAULT_SCOPE="${VBOARD_INSTALL_SCOPE:-auto}"
SCOPE="$DEFAULT_SCOPE"
SYSTEM_PREFIX="${VBOARD_PREFIX:-/usr/local}"
SYSTEM_CONFIG_FILE="/etc/xdg/kwinrulesrc"

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
    elif [[ -e "$SYSTEM_CONFIG_FILE" && -w "$SYSTEM_CONFIG_FILE" ]]; then
        SCOPE="system"
    elif [[ -w "$(dirname "$SYSTEM_CONFIG_FILE")" ]]; then
        SCOPE="system"
    else
        SCOPE="user"
    fi
fi

if [[ "$SCOPE" == "system" ]]; then
    CONFIG_FILE="$SYSTEM_CONFIG_FILE"
else
    CONFIG_FILE="${XDG_CONFIG_HOME:-$HOME/.config}/kwinrulesrc"
fi

python3 - "$CONFIG_FILE" "$RULE_NAME" <<'PY'
import configparser
import os
import sys

config_file = sys.argv[1]
rule_name = sys.argv[2]

if not os.path.exists(config_file):
    raise SystemExit(0)

config = configparser.ConfigParser(interpolation=None)
config.optionxform = str
config.read(config_file)
if config.has_section("General"):
    rules = [item.strip() for item in config.get("General", "rules", fallback="").split(",") if item.strip()]
    rules = [item for item in rules if item != rule_name]
    config.set("General", "rules", ",".join(rules))
    config.set("General", "count", str(len(rules)))
if config.remove_section(rule_name):
    remaining_sections = [section for section in config.sections() if section != "General"]
    general_rules = [item.strip() for item in config.get("General", "rules", fallback="").split(",") if item.strip()] if config.has_section("General") else []
    general_count = config.getint("General", "count", fallback=0) if config.has_section("General") else 0
    if not remaining_sections and not general_rules and general_count == 0:
        os.remove(config_file)
        raise SystemExit(0)
    with open(config_file, "w", encoding="utf-8") as handle:
        config.write(handle)
elif config.has_section("General"):
    remaining_sections = [section for section in config.sections() if section != "General"]
    general_rules = [item.strip() for item in config.get("General", "rules", fallback="").split(",") if item.strip()]
    general_count = config.getint("General", "count", fallback=0)
    if not remaining_sections and not general_rules and general_count == 0:
        os.remove(config_file)
        raise SystemExit(0)
    with open(config_file, "w", encoding="utf-8") as handle:
        config.write(handle)
PY

qdbus6 org.kde.KWin /KWin reconfigure >/dev/null 2>&1 || true

echo "Removed KWin rule from: $CONFIG_FILE [$RULE_NAME]"
