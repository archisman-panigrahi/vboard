APP_DISPLAY_NAME = "Vboard"
APP_ID = "io.github.archisman-panigrahi.vboard"
VERSION = "1.3"

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

COMMAND_MODIFIER_KEYS = (
    "Ctrl_L",
    "Ctrl_R",
    "Alt_L",
    "Alt_R",
    "Super_L",
    "Super_R",
)

KEY_ROWS = [
    ["`", "1", "2", "3", "4", "5", "6", "7", "8", "9", "0", "-", "=", "Backspace"],
    ["Tab", "Q", "W", "E", "R", "T", "Y", "U", "I", "O", "P", "[", "]", "\\"],
    ["CapsLock", "A", "S", "D", "F", "G", "H", "J", "K", "L", ";", "'", "Enter"],
    ["Shift_L", "Z", "X", "C", "V", "B", "N", "M", ",", ".", "/", "Shift_R", "↑"],
    ["Ctrl_L", "Super_L", "Alt_L", "Space", "Alt_R", "Super_R", "Ctrl_R", "←", "↓", "→"],
]

SHIFTED_KEY_MAP = {
    "`": "~",
    "1": "!",
    "2": "@",
    "3": "#",
    "4": "$",
    "5": "%",
    "6": "^",
    "7": "&",
    "8": "*",
    "9": "(",
    "0": ")",
    "-": "_",
    "=": "+",
    "[": "{",
    "]": "}",
    "\\": "|",
    ";": ":",
    "'": '"',
    ",": "<",
    ".": ">",
    "/": "?",
}

SHIFTED_CHAR_TO_KEY_EVENT = {value: key for key, value in SHIFTED_KEY_MAP.items()}

COLOR_CHOICES = [
    ("Black", "0,0,0"),
    ("Red", "255,0,0"),
    ("Pink", "255,105,183"),
    ("White", "255,255,255"),
    ("Green", "0,255,0"),
    ("Blue", "0,0,110"),
    ("Gray", "128,128,128"),
    ("Dark Gray", "64,64,64"),
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
    "Shift_R": 2,
    "Shift_L": 4,
    "Backspace": 5,
    "`": 1,
    "\\": 4,
    "Enter": 5,
}

SHIFTED_BUTTON_LABELS = [
    (0, ("`", "~")),
    (1, ("1", "!")),
    (2, ("2", "@")),
    (3, ("3", "#")),
    (4, ("4", "$")),
    (5, ("5", "%")),
    (6, ("6", "^")),
    (7, ("7", "&")),
    (8, ("8", "*")),
    (9, ("9", "(")),
    (10, ("0", ")")),
    (11, ("-", "_")),
    (12, ("=", "+")),
    (25, ("[", "{")),
    (26, ("]", "}")),
    (27, ("\\", "|")),
    (38, (";", ":")),
    (39, ("'", '"')),
    (49, (",", "<")),
    (50, (".", ">")),
    (51, ("/", "?")),
]

SUPPORTED_WORD_CHARS = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'-")
SUGGESTION_LIMIT = 5
