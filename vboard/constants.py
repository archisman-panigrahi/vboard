APP_DISPLAY_NAME = "Vboard"
APP_ID = "io.github.archisman-panigrahi.vboard"
VERSION = "2.7.1"

MODIFIER_KEYS = (
    "Shift_L",
    "Shift_R",
    "Ctrl_L",
    "Ctrl_R",
    "Alt_L",
    "Alt_R",
    "Super_L",
    "Super_R",
)

LAYOUT_SWITCH_KEY = "Layout"
SPACER_KEY_PREFIX = "Spacer:"
NAVIGATION_ROW_KEYS = ("Delete", "PageUp", "PageDown")

DEFAULT_KEYBOARD_LAYOUT = "en"

COMMAND_MODIFIER_KEYS = (
    "Ctrl_L",
    "Ctrl_R",
    "Alt_L",
    "Alt_R",
    "Super_L",
    "Super_R",
)

ONBOARD_BACKGROUND_PRESET = "__onboard__"
ENHANCED_BACKGROUND_PRESET = "__enhanced__"

COLOR_PRESETS = [
    ("Black", "0,0,0"),
    ("Red", "255,0,0"),
    ("Pink", "255,105,183"),
    ("White", "255,255,255"),
    ("Green", "0,255,0"),
    ("Blue", "0,0,110"),
    ("Gray", "128,128,128"),
    ("Dark Gray", "64,64,64"),
    ("Slate", "51,65,85"),
    ("Orange", "255,165,0"),
    ("Yellow", "255,255,0"),
    ("Purple", "128,0,128"),
    ("Cyan", "0,255,255"),
    ("Teal", "0,128,128"),
    ("Brown", "139,69,19"),
    ("Gold", "255,215,0"),
    ("Silver", "192,192,192"),
    ("Turquoise", "64,224,208"),
    ("Magenta", "255,0,255"),
    ("Olive", "128,128,0"),
    ("Maroon", "128,0,0"),
    ("Indigo", "75,0,130"),
    ("Beige", "245,245,220"),
    ("Lavender", "230,230,250"),
]

COLOR_CHOICES = [
    ("Onboard Droid Theme", ONBOARD_BACKGROUND_PRESET),
    *[
        (f"Enhanced {label}", (ENHANCED_BACKGROUND_PRESET, color))
        for label, color in COLOR_PRESETS
    ],
    *COLOR_PRESETS,
]

LIGHT_BACKGROUND_COLORS = {
    "255,255,255",
    "0,255,0",
    "255,255,0",
    "245,245,220",
    "230,230,250",
    "255,215,0",
}

KEY_WIDTHS = {
    "Space": 12,
    "CapsLock": 3,
    "Shift_R": 3,
    "Shift_L": 3,
    "Backspace": 5,
    "`": 1,
    "\\": 4,
    "Enter": 5,
    "<": 2,
    LAYOUT_SWITCH_KEY: 3,
}

SUPPORTED_WORD_CONNECTORS = {"'", "\u2019", "\u02bc", "-"}
SUGGESTION_LIMIT = 5
