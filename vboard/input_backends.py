"""Input backends for vboard.

Steam Deck / SteamOS note:
  python-uinput needs gcc (often missing). Prefer python-evdev UInput which
  ships with SteamOS and can open /dev/uinput when the user has access.
"""

from .constants import MODIFIER_KEYS

try:
    import uinput as pyuinput
except ImportError:
    pyuinput = None

try:
    from evdev import UInput as EvdevUInput
    from evdev import ecodes
except ImportError:
    EvdevUInput = None
    ecodes = None


class InputBackend:
    name = "unknown"

    def emit_key(self, key_label, modifiers):
        raise NotImplementedError


class NullInputBackend(InputBackend):
    name = "disabled"

    def __init__(self, reason=None):
        self.reason = reason
        if reason:
            print(f"Warning: {reason}")

    def emit_key(self, key_label, modifiers):
        return


# Coding-layout symbols that need Shift+base key in one tap
_SHIFT_CHORDS = {
    "{": "[",
    "}": "]",
    "(": "9",
    ")": "0",
    "<": ",",
    ">": ".",
    "+": "=",
    "_": "-",
    ":": ";",
    '"': "'",
    "|": "\\",
    "~": "`",
    "!": "1",
    "@": "2",
    "#": "3",
    "$": "4",
    "%": "5",
    "^": "6",
    "&": "7",
    "*": "8",
    "?": "/",
}


class EvdevUInputBackend(InputBackend):
    """uinput via python-evdev (preferred on Steam Deck)."""

    name = "evdev-uinput"

    def __init__(self):
        if EvdevUInput is None or ecodes is None:
            raise RuntimeError("python-evdev is not installed")

        self.key_map = {
            "Esc": ecodes.KEY_ESC,
            "1": ecodes.KEY_1,
            "2": ecodes.KEY_2,
            "3": ecodes.KEY_3,
            "4": ecodes.KEY_4,
            "5": ecodes.KEY_5,
            "6": ecodes.KEY_6,
            "7": ecodes.KEY_7,
            "8": ecodes.KEY_8,
            "9": ecodes.KEY_9,
            "0": ecodes.KEY_0,
            "-": ecodes.KEY_MINUS,
            "=": ecodes.KEY_EQUAL,
            "Backspace": ecodes.KEY_BACKSPACE,
            "Tab": ecodes.KEY_TAB,
            "Q": ecodes.KEY_Q,
            "W": ecodes.KEY_W,
            "E": ecodes.KEY_E,
            "R": ecodes.KEY_R,
            "T": ecodes.KEY_T,
            "Y": ecodes.KEY_Y,
            "U": ecodes.KEY_U,
            "I": ecodes.KEY_I,
            "O": ecodes.KEY_O,
            "P": ecodes.KEY_P,
            "[": ecodes.KEY_LEFTBRACE,
            "]": ecodes.KEY_RIGHTBRACE,
            "Enter": ecodes.KEY_ENTER,
            "Ctrl_L": ecodes.KEY_LEFTCTRL,
            "Ctrl_R": ecodes.KEY_RIGHTCTRL,
            "A": ecodes.KEY_A,
            "S": ecodes.KEY_S,
            "D": ecodes.KEY_D,
            "F": ecodes.KEY_F,
            "G": ecodes.KEY_G,
            "H": ecodes.KEY_H,
            "J": ecodes.KEY_J,
            "K": ecodes.KEY_K,
            "L": ecodes.KEY_L,
            ";": ecodes.KEY_SEMICOLON,
            "'": ecodes.KEY_APOSTROPHE,
            "`": ecodes.KEY_GRAVE,
            "Shift_L": ecodes.KEY_LEFTSHIFT,
            "Shift_R": ecodes.KEY_RIGHTSHIFT,
            "\\": ecodes.KEY_BACKSLASH,
            "Z": ecodes.KEY_Z,
            "X": ecodes.KEY_X,
            "C": ecodes.KEY_C,
            "V": ecodes.KEY_V,
            "B": ecodes.KEY_B,
            "N": ecodes.KEY_N,
            "M": ecodes.KEY_M,
            ",": ecodes.KEY_COMMA,
            ".": ecodes.KEY_DOT,
            "/": ecodes.KEY_SLASH,
            "Alt_L": ecodes.KEY_LEFTALT,
            "Alt_R": ecodes.KEY_RIGHTALT,
            "Space": ecodes.KEY_SPACE,
            "CapsLock": ecodes.KEY_CAPSLOCK,
            "→": ecodes.KEY_RIGHT,
            "←": ecodes.KEY_LEFT,
            "↓": ecodes.KEY_DOWN,
            "↑": ecodes.KEY_UP,
            "Super_L": ecodes.KEY_LEFTMETA,
            "Super_R": ecodes.KEY_RIGHTMETA,
            # Aliases used by some layouts / UI labels
            "Bksp": ecodes.KEY_BACKSPACE,
            "Delete": ecodes.KEY_DELETE,
            "Del": ecodes.KEY_DELETE,
        }
        # 102nd key / less-than on ISO boards
        if hasattr(ecodes, "KEY_102ND"):
            self.key_map["<"] = ecodes.KEY_102ND

        # Advertise a wide key set so KWin never drops Backspace / braces
        key_codes = set(self.key_map.values())
        # KEY_RESERVED=0 .. KEY_MAX common range used by full keyboards
        for code in range(1, 256):
            key_codes.add(code)
        events = {ecodes.EV_KEY: sorted(key_codes)}
        self.device = EvdevUInput(
            events=events,
            name="vboard-keyboard",
            bustype=0x03,  # BUS_USB — treated as real keyboard by more stacks
        )
        self.modifier_order = list(MODIFIER_KEYS)

    def _press_release(self, code, down):
        self.device.write(ecodes.EV_KEY, code, 1 if down else 0)

    def emit_key(self, key_label, modifiers):
        import time

        mods = dict(modifiers or {})
        label = key_label

        # One-tap coding symbols: Shift + base key
        if label in _SHIFT_CHORDS:
            label = _SHIFT_CHORDS[label]
            mods["Shift_L"] = True

        key_code = self.key_map.get(label)
        if key_code is None:
            print(f"vboard: unknown key {key_label!r}")
            return

        for mod_key in self.modifier_order:
            if mods.get(mod_key, False) and mod_key in self.key_map:
                self._press_release(self.key_map[mod_key], True)
        self.device.syn()

        # Hold briefly so apps / compositors register the press (esp. Backspace)
        self._press_release(key_code, True)
        self.device.syn()
        time.sleep(0.012)
        self._press_release(key_code, False)
        self.device.syn()

        for mod_key in reversed(self.modifier_order):
            if mods.get(mod_key, False) and mod_key in self.key_map:
                self._press_release(self.key_map[mod_key], False)
        self.device.syn()


class UInputBackend(InputBackend):
    """Legacy python-uinput backend (needs gcc on SteamOS — often unavailable)."""

    name = "uinput"

    def __init__(self):
        if pyuinput is None:
            raise RuntimeError("python-uinput is not installed")

        less_key = self._uinput_key("KEY_LESS", "KEY_102ND", required=False)
        self.key_map = {
            "Esc": pyuinput.KEY_ESC,
            "1": pyuinput.KEY_1,
            "2": pyuinput.KEY_2,
            "3": pyuinput.KEY_3,
            "4": pyuinput.KEY_4,
            "5": pyuinput.KEY_5,
            "6": pyuinput.KEY_6,
            "7": pyuinput.KEY_7,
            "8": pyuinput.KEY_8,
            "9": pyuinput.KEY_9,
            "0": pyuinput.KEY_0,
            "-": pyuinput.KEY_MINUS,
            "=": pyuinput.KEY_EQUAL,
            "Backspace": pyuinput.KEY_BACKSPACE,
            "Tab": pyuinput.KEY_TAB,
            "Q": pyuinput.KEY_Q,
            "W": pyuinput.KEY_W,
            "E": pyuinput.KEY_E,
            "R": pyuinput.KEY_R,
            "T": pyuinput.KEY_T,
            "Y": pyuinput.KEY_Y,
            "U": pyuinput.KEY_U,
            "I": pyuinput.KEY_I,
            "O": pyuinput.KEY_O,
            "P": pyuinput.KEY_P,
            "[": pyuinput.KEY_LEFTBRACE,
            "]": pyuinput.KEY_RIGHTBRACE,
            "Enter": pyuinput.KEY_ENTER,
            "Ctrl_L": pyuinput.KEY_LEFTCTRL,
            "Ctrl_R": pyuinput.KEY_RIGHTCTRL,
            "A": pyuinput.KEY_A,
            "S": pyuinput.KEY_S,
            "D": pyuinput.KEY_D,
            "F": pyuinput.KEY_F,
            "G": pyuinput.KEY_G,
            "H": pyuinput.KEY_H,
            "J": pyuinput.KEY_J,
            "K": pyuinput.KEY_K,
            "L": pyuinput.KEY_L,
            ";": pyuinput.KEY_SEMICOLON,
            "'": pyuinput.KEY_APOSTROPHE,
            "`": pyuinput.KEY_GRAVE,
            "Shift_L": pyuinput.KEY_LEFTSHIFT,
            "Shift_R": pyuinput.KEY_RIGHTSHIFT,
            "\\": pyuinput.KEY_BACKSLASH,
            "Z": pyuinput.KEY_Z,
            "X": pyuinput.KEY_X,
            "C": pyuinput.KEY_C,
            "V": pyuinput.KEY_V,
            "B": pyuinput.KEY_B,
            "N": pyuinput.KEY_N,
            "M": pyuinput.KEY_M,
            ",": pyuinput.KEY_COMMA,
            ".": pyuinput.KEY_DOT,
            "/": pyuinput.KEY_SLASH,
            "Alt_L": pyuinput.KEY_LEFTALT,
            "Alt_R": pyuinput.KEY_RIGHTALT,
            "Space": pyuinput.KEY_SPACE,
            "CapsLock": pyuinput.KEY_CAPSLOCK,
            "→": pyuinput.KEY_RIGHT,
            "←": pyuinput.KEY_LEFT,
            "↓": pyuinput.KEY_DOWN,
            "↑": pyuinput.KEY_UP,
            "Super_L": pyuinput.KEY_LEFTMETA,
            "Super_R": pyuinput.KEY_RIGHTMETA,
        }
        if less_key is not None:
            self.key_map["<"] = less_key
        self.modifier_order = list(MODIFIER_KEYS)
        self.device = pyuinput.Device(list(self.key_map.values()))

    @staticmethod
    def _uinput_key(*names, required=True):
        for name in names:
            key = getattr(pyuinput, name, None)
            if key is not None:
                return key
        if required:
            raise RuntimeError(
                "python-uinput is missing required key constant(s): "
                + ", ".join(names)
            )
        return None

    def emit_key(self, key_label, modifiers):
        mods = dict(modifiers or {})
        label = key_label
        if label in _SHIFT_CHORDS:
            label = _SHIFT_CHORDS[label]
            mods["Shift_L"] = True

        key_event = self.key_map.get(label)
        if key_event is None:
            return

        for mod_key in self.modifier_order:
            if mods.get(mod_key, False):
                self.device.emit(self.key_map[mod_key], 1)

        self.device.emit(key_event, 1)
        self.device.emit(key_event, 0)

        for mod_key in self.modifier_order:
            if mods.get(mod_key, False):
                self.device.emit(self.key_map[mod_key], 0)


def create_input_backend():
    """Pick the best available backend."""
    errors = []
    try:
        return EvdevUInputBackend()
    except Exception as exc:
        errors.append(f"evdev-uinput: {exc}")
    try:
        return UInputBackend()
    except Exception as exc:
        errors.append(f"python-uinput: {exc}")
    reason = "Could not initialize uinput backend (" + "; ".join(errors) + ")"
    return NullInputBackend(reason=reason)
