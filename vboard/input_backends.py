from .constants import MODIFIER_KEYS
from .libei import EISClient

import time

try:
    import uinput
except ImportError:
    uinput = None

UINPUT_KEY_MAP = {
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

class InputBackend:
    name = "unknown"

    def emit_key(self, key_label, modifiers):
        raise NotImplementedError
    
    def close(self):
        pass


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

        self.key_map = UINPUT_KEY_MAP
        self.modifier_order = list(MODIFIER_KEYS)
        self.device = uinput.Device(list(self.key_map.values()))

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


class KWinLibeiBackend(InputBackend):
    name = "kwin-libei"

    def __init__(self):
        self.key_map = UINPUT_KEY_MAP
        self.modifier_order = list(MODIFIER_KEYS)
        self.client = EISClient()

    def emit_key(self, key_label, modifiers):
        key_event = self.key_map.get(key_label)
        if key_event is None:
            return

        for mod_key in self.modifier_order:
            if modifiers.get(mod_key, False):
                self.client.keyboard_key(self.key_map[mod_key][1], 1)

        self.client.keyboard_key(key_event[1], 1)
        self.client.keyboard_key(key_event[1], 0)

        for mod_key in self.modifier_order:
            if modifiers.get(mod_key, False):
                self.client.keyboard_key(self.key_map[mod_key][1], 0)

    def close(self):
        self.client.close()
