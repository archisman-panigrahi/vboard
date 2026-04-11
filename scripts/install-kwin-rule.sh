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

config = configparser.ConfigParser(interpolation=None)
config.optionxform = str
if os.path.exists(config_file):
    config.read(config_file)

if not config.has_section("General"):
    config.add_section("General")

if not config.has_section(rule_name):
    config.add_section(rule_name)

values = {
    "Description": "vboard always on top, no focus, remember position",
    "Enabled": "true",
    "title": "Vboard|Virtual Keyboard|vboard\\.py",
    "titlematch": "3",
    "position": "0,0",
    "positionrule": "4",
    "above": "true",
    "aboverule": "2",
    "acceptfocus": "false",
    "acceptfocusrule": "2",
    "skiptaskbar": "true",
    "skiptaskbarrule": "2",
    "skippager": "true",
    "skippagerrule": "2",
}

for key, value in values.items():
    config.set(rule_name, key, value)

rules = [item.strip() for item in config.get("General", "rules", fallback="").split(",") if item.strip()]
if rule_name not in rules:
    rules.append(rule_name)
config.set("General", "rules", ",".join(rules))
config.set("General", "count", str(len(rules)))

with open(config_file, "w", encoding="utf-8") as handle:
    config.write(handle)
PY

qdbus6 org.kde.KWin /KWin reconfigure >/dev/null 2>&1 || true

echo "Installed KWin rule in: $CONFIG_FILE [$RULE_NAME]"
