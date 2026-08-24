import json
import os

from .constants import DEFAULT_KEYBOARD_LAYOUT


SYSTEM_LAYOUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "layouts")
USER_LAYOUT_DIR = os.path.expanduser("~/.config/vboard/layouts")
REQUIRED_LAYOUT_FIELDS = ("id", "label", "rows")
LAYOUT_SHORT_LABELS = {
    "uk": "UA",
}


def get_layout_directories(user_layout_dir=USER_LAYOUT_DIR):
    return (SYSTEM_LAYOUT_DIR, user_layout_dir)


def load_keyboard_layouts(user_layout_dir=USER_LAYOUT_DIR):
    layouts = {}
    for layout_dir in get_layout_directories(user_layout_dir):
        if not os.path.isdir(layout_dir):
            continue

        for filename in sorted(os.listdir(layout_dir)):
            if not filename.endswith(".json"):
                continue

            path = os.path.join(layout_dir, filename)
            try:
                layout = load_keyboard_layout(path)
            except (OSError, ValueError) as exc:
                print(f"Warning: Could not load keyboard layout {path} ({exc}).")
                continue

            layouts[layout["id"]] = layout

    if not layouts:
        searched_dirs = ", ".join(get_layout_directories(user_layout_dir))
        raise RuntimeError(f"No keyboard layouts found. Checked: {searched_dirs}")

    return layouts


def load_keyboard_layout(path):
    with open(path, "r", encoding="utf-8") as layout_file:
        layout = json.load(layout_file)

    validate_keyboard_layout(layout, path)
    return {
        "id": layout["id"],
        "label": layout["label"],
        "order": layout.get("order"),
        "rows": layout["rows"],
        "labels": layout.get("labels", {}),
        "shifted": layout.get("shifted", {}),
    }


def validate_keyboard_layout(layout, path):
    if not isinstance(layout, dict):
        raise ValueError("layout must be a JSON object")

    for field in REQUIRED_LAYOUT_FIELDS:
        if field not in layout:
            raise ValueError(f"missing required field: {field}")

    if not isinstance(layout["id"], str) or not layout["id"]:
        raise ValueError("id must be a non-empty string")
    if not isinstance(layout["label"], str) or not layout["label"]:
        raise ValueError("label must be a non-empty string")
    if not isinstance(layout["rows"], list) or not layout["rows"]:
        raise ValueError("rows must be a non-empty list")
    if "order" in layout and not isinstance(layout["order"], int):
        raise ValueError("order must be an integer")

    for row in layout["rows"]:
        if not isinstance(row, list) or not row:
            raise ValueError("each row must be a non-empty list")
        for key in row:
            if not isinstance(key, str) or not key:
                raise ValueError("each key must be a non-empty string")

    for field in ("labels", "shifted"):
        if field not in layout:
            continue
        if not isinstance(layout[field], dict):
            raise ValueError(f"{field} must be an object")
        for key, value in layout[field].items():
            if not isinstance(key, str) or not isinstance(value, str):
                raise ValueError(f"{field} keys and values must be strings")


def get_layout_choices(layouts):
    choices = []
    for layout_id, layout in layouts.items():
        choices.append((layout_id, layout["label"], layout.get("order")))
    sorted_choices = sorted(choices, key=get_layout_choice_sort_key)
    return tuple((layout_id, label) for layout_id, label, _order in sorted_choices)


def get_layout_choice_sort_key(choice):
    layout_id, label, order = choice
    if isinstance(order, int):
        return (0, order, label.lower(), layout_id)
    if layout_id == DEFAULT_KEYBOARD_LAYOUT:
        return (1, 0, "", "")
    return (1, 1, label.lower(), layout_id)


def get_default_layout_key(layouts):
    if DEFAULT_KEYBOARD_LAYOUT in layouts:
        return DEFAULT_KEYBOARD_LAYOUT
    return next(iter(layouts))


def get_layout_short_label(layout_id):
    if layout_id in LAYOUT_SHORT_LABELS:
        return LAYOUT_SHORT_LABELS[layout_id]
    if layout_id.isascii() and layout_id.isalpha() and 2 <= len(layout_id) <= 3:
        return layout_id.upper()
    return None


def get_layout_switch_label(primary_layout, secondary_layout):
    primary_label = get_layout_short_label(primary_layout)
    secondary_label = get_layout_short_label(secondary_layout)
    if (
        primary_layout == secondary_layout
        or primary_label is None
        or secondary_label is None
    ):
        return "🌐"
    return f"{secondary_label}/{primary_label}"
