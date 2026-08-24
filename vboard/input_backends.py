from .constants import FUNCTION_KEYS, MODIFIER_KEYS

try:
    import uinput
except ImportError:
    uinput = None


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


class UInputBackend(InputBackend):
    name = "uinput"

    def __init__(self):
        if uinput is None:
            raise RuntimeError("python-uinput is not installed")

        less_key = self._uinput_key("KEY_LESS", "KEY_102ND", required=False)
        self.key_map = {
            "Esc": uinput.KEY_ESC,
            "1": uinput.KEY_1,
            "2": uinput.KEY_2,
            "3": uinput.KEY_3,
            "4": uinput.KEY_4,
            "5": uinput.KEY_5,
            "6": uinput.KEY_6,
            "7": uinput.KEY_7,
            "8": uinput.KEY_8,
            "9": uinput.KEY_9,
            "0": uinput.KEY_0,
            "-": uinput.KEY_MINUS,
            "=": uinput.KEY_EQUAL,
            "Backspace": uinput.KEY_BACKSPACE,
            "Delete": uinput.KEY_DELETE,
            "Insert": uinput.KEY_INSERT,
            "PageUp": uinput.KEY_PAGEUP,
            "PageDown": uinput.KEY_PAGEDOWN,
            "Home": uinput.KEY_HOME,
            "End": uinput.KEY_END,
            "Tab": uinput.KEY_TAB,
            "Q": uinput.KEY_Q,
            "W": uinput.KEY_W,
            "E": uinput.KEY_E,
            "R": uinput.KEY_R,
            "T": uinput.KEY_T,
            "Y": uinput.KEY_Y,
            "U": uinput.KEY_U,
            "I": uinput.KEY_I,
            "O": uinput.KEY_O,
            "P": uinput.KEY_P,
            "[": uinput.KEY_LEFTBRACE,
            "]": uinput.KEY_RIGHTBRACE,
            "Enter": uinput.KEY_ENTER,
            "Ctrl_L": uinput.KEY_LEFTCTRL,
            "Ctrl_R": uinput.KEY_RIGHTCTRL,
            "A": uinput.KEY_A,
            "S": uinput.KEY_S,
            "D": uinput.KEY_D,
            "F": uinput.KEY_F,
            "G": uinput.KEY_G,
            "H": uinput.KEY_H,
            "J": uinput.KEY_J,
            "K": uinput.KEY_K,
            "L": uinput.KEY_L,
            ";": uinput.KEY_SEMICOLON,
            "'": uinput.KEY_APOSTROPHE,
            "`": uinput.KEY_GRAVE,
            "Shift_L": uinput.KEY_LEFTSHIFT,
            "Shift_R": uinput.KEY_RIGHTSHIFT,
            "\\": uinput.KEY_BACKSLASH,
            "Z": uinput.KEY_Z,
            "X": uinput.KEY_X,
            "C": uinput.KEY_C,
            "V": uinput.KEY_V,
            "B": uinput.KEY_B,
            "N": uinput.KEY_N,
            "M": uinput.KEY_M,
            ",": uinput.KEY_COMMA,
            ".": uinput.KEY_DOT,
            "/": uinput.KEY_SLASH,
            "Alt_L": uinput.KEY_LEFTALT,
            "Alt_R": uinput.KEY_RIGHTALT,
            "Space": uinput.KEY_SPACE,
            "CapsLock": uinput.KEY_CAPSLOCK,
            "→": uinput.KEY_RIGHT,
            "←": uinput.KEY_LEFT,
            "↓": uinput.KEY_DOWN,
            "↑": uinput.KEY_UP,
            "Super_L": uinput.KEY_LEFTMETA,
            "Super_R": uinput.KEY_RIGHTMETA,
        }
        self.key_map.update(
            {
                function_key: self._uinput_key(f"KEY_{function_key}")
                for function_key in FUNCTION_KEYS
            }
        )
        if less_key is not None:
            self.key_map["<"] = less_key
        self.modifier_order = list(MODIFIER_KEYS)
        self.device = uinput.Device(list(self.key_map.values()))

    @staticmethod
    def _uinput_key(*names, required=True):
        for name in names:
            key = getattr(uinput, name, None)
            if key is not None:
                return key
        if required:
            raise RuntimeError(
                "python-uinput is missing required key constant(s): "
                + ", ".join(names)
            )
        return None

    def emit_key(self, key_label, modifiers):
        key_event = self.key_map.get(key_label)
        if key_event is None:
            return

        for mod_key in self.modifier_order:
            if modifiers.get(mod_key, False):
                self.device.emit(self.key_map[mod_key], 1)

        self.device.emit(key_event, 1)
        self.device.emit(key_event, 0)

        for mod_key in self.modifier_order:
            if modifiers.get(mod_key, False):
                self.device.emit(self.key_map[mod_key], 0)
