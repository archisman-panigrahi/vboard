"""Input backends for vboard.

Keys are injected through Linux `uinput`, so applications see an ordinary
physical keyboard. Two Python bindings can drive it:

* ``python-uinput`` — the existing backend, unchanged and still preferred.
* ``python-evdev`` — used only when ``python-uinput`` is unavailable.
  ``python-uinput`` is a C extension, so it has to be compiled; on a
  distribution that ships a read-only root without a toolchain (SteamOS is
  the case this was written for) it cannot be installed at all, while
  ``python-evdev`` is already present. Both open the same ``/dev/uinput``.

Both bindings expose the Linux key constants under the same names, so the
label-to-key table below is shared and each backend resolves the names
against its own module.
"""

import time

from .constants import MODIFIER_KEYS

try:
    import uinput
except ImportError:
    uinput = None

try:
    from evdev import UInput as EvdevUInput
    from evdev import ecodes
except ImportError:
    EvdevUInput = None
    ecodes = None


# Key label -> Linux key constant name. A tuple lists alternatives, tried in
# order; a label in OPTIONAL_KEYS may resolve to none of them and is dropped.
KEY_NAMES = {
    "Esc": "KEY_ESC",
    "1": "KEY_1",
    "2": "KEY_2",
    "3": "KEY_3",
    "4": "KEY_4",
    "5": "KEY_5",
    "6": "KEY_6",
    "7": "KEY_7",
    "8": "KEY_8",
    "9": "KEY_9",
    "0": "KEY_0",
    "-": "KEY_MINUS",
    "=": "KEY_EQUAL",
    "Backspace": "KEY_BACKSPACE",
    "Tab": "KEY_TAB",
    "Q": "KEY_Q",
    "W": "KEY_W",
    "E": "KEY_E",
    "R": "KEY_R",
    "T": "KEY_T",
    "Y": "KEY_Y",
    "U": "KEY_U",
    "I": "KEY_I",
    "O": "KEY_O",
    "P": "KEY_P",
    "[": "KEY_LEFTBRACE",
    "]": "KEY_RIGHTBRACE",
    "Enter": "KEY_ENTER",
    "Ctrl_L": "KEY_LEFTCTRL",
    "Ctrl_R": "KEY_RIGHTCTRL",
    "A": "KEY_A",
    "S": "KEY_S",
    "D": "KEY_D",
    "F": "KEY_F",
    "G": "KEY_G",
    "H": "KEY_H",
    "J": "KEY_J",
    "K": "KEY_K",
    "L": "KEY_L",
    ";": "KEY_SEMICOLON",
    "'": "KEY_APOSTROPHE",
    "`": "KEY_GRAVE",
    "Shift_L": "KEY_LEFTSHIFT",
    "Shift_R": "KEY_RIGHTSHIFT",
    "\\": "KEY_BACKSLASH",
    "Z": "KEY_Z",
    "X": "KEY_X",
    "C": "KEY_C",
    "V": "KEY_V",
    "B": "KEY_B",
    "N": "KEY_N",
    "M": "KEY_M",
    ",": "KEY_COMMA",
    ".": "KEY_DOT",
    "/": "KEY_SLASH",
    "Alt_L": "KEY_LEFTALT",
    "Alt_R": "KEY_RIGHTALT",
    "Space": "KEY_SPACE",
    "CapsLock": "KEY_CAPSLOCK",
    "→": "KEY_RIGHT",
    "←": "KEY_LEFT",
    "↓": "KEY_DOWN",
    "↑": "KEY_UP",
    "Super_L": "KEY_LEFTMETA",
    "Super_R": "KEY_RIGHTMETA",
    "<": ("KEY_LESS", "KEY_102ND"),
}

OPTIONAL_KEYS = {"<"}


def _build_key_map(module):
    """Resolve KEY_NAMES against a binding module (uinput or evdev.ecodes)."""
    key_map = {}
    for label, names in KEY_NAMES.items():
        if isinstance(names, str):
            names = (names,)
        for name in names:
            value = getattr(module, name, None)
            if value is not None:
                key_map[label] = value
                break
        else:
            if label not in OPTIONAL_KEYS:
                raise RuntimeError(
                    f"{module.__name__} is missing required key constant(s): "
                    + ", ".join(names)
                )
    return key_map


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

        self.key_map = _build_key_map(uinput)
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


class EvdevUInputBackend(InputBackend):
    """Same /dev/uinput, driven by python-evdev instead of python-uinput."""

    name = "evdev-uinput"

    # A press that goes down and up in the same event batch was intermittently
    # missed under KWin/Wayland — Backspace most visibly. Holding briefly makes
    # it look like a real keystroke.
    KEY_HOLD_SECONDS = 0.012

    def __init__(self):
        if EvdevUInput is None or ecodes is None:
            raise RuntimeError("python-evdev is not installed")

        self.key_map = _build_key_map(ecodes)
        self.modifier_order = list(MODIFIER_KEYS)
        self.device = EvdevUInput(
            events={ecodes.EV_KEY: self._advertised_keys()},
            name="vboard-keyboard",
            bustype=ecodes.BUS_USB,
        )

    def _advertised_keys(self):
        """Codes the virtual device claims to have.

        Deliberately the whole standard AT keyboard range rather than only the
        keys vboard maps: compositors classify an input device from the
        capabilities it advertises, and with a narrow set KWin decided this was
        not a keyboard and dropped Backspace and the brace keys.
        """
        codes = set(range(ecodes.KEY_ESC, ecodes.KEY_COMPOSE + 1))
        codes.update(self.key_map.values())
        return sorted(codes)

    def _write(self, code, value):
        self.device.write(ecodes.EV_KEY, code, value)

    def emit_key(self, key_label, modifiers):
        key_code = self.key_map.get(key_label)
        if key_code is None:
            return

        for mod_key in self.modifier_order:
            if modifiers.get(mod_key, False):
                self._write(self.key_map[mod_key], 1)
        self.device.syn()

        self._write(key_code, 1)
        self.device.syn()
        time.sleep(self.KEY_HOLD_SECONDS)
        self._write(key_code, 0)
        self.device.syn()

        for mod_key in reversed(self.modifier_order):
            if modifiers.get(mod_key, False):
                self._write(self.key_map[mod_key], 0)
        self.device.syn()


def create_input_backend():
    """First backend that can open /dev/uinput.

    python-uinput stays first, so a working installation keeps exactly the
    behaviour it had; python-evdev is only reached where python-uinput is
    missing or cannot be built.
    """
    errors = []
    for backend in (UInputBackend, EvdevUInputBackend):
        try:
            return backend()
        except Exception as exc:
            errors.append(f"{backend.name}: {exc}")
    return NullInputBackend(
        "Could not initialize uinput backend ("
        + "; ".join(errors)
        + "); key output is disabled"
    )
