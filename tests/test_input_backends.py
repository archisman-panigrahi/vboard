import unittest
from unittest import mock

from vboard import input_backends
from vboard.constants import FUNCTION_KEYS, MODIFIER_KEYS


class FakeDevice:
    def __init__(self, supported_keys):
        self.supported_keys = supported_keys
        self.events = []

    def emit(self, key, value):
        self.events.append((key, value))


class FakeUInput:
    def __init__(self):
        self.device = None

    def __getattr__(self, name):
        if name.startswith("KEY_"):
            return name
        raise AttributeError(name)

    def Device(self, supported_keys):
        self.device = FakeDevice(supported_keys)
        return self.device


class UInputFunctionKeysTest(unittest.TestCase):
    def setUp(self):
        self.fake_uinput = FakeUInput()
        self.uinput_patch = mock.patch.object(
            input_backends,
            "uinput",
            self.fake_uinput,
        )
        self.uinput_patch.start()
        self.addCleanup(self.uinput_patch.stop)

    def test_registers_all_function_keys(self):
        backend = input_backends.UInputBackend()

        self.assertEqual(FUNCTION_KEYS, tuple(f"F{number}" for number in range(1, 13)))
        for function_key in FUNCTION_KEYS:
            self.assertEqual(
                backend.key_map[function_key],
                f"KEY_{function_key}",
            )
            self.assertIn(f"KEY_{function_key}", self.fake_uinput.device.supported_keys)

    def test_emits_function_key_with_active_modifier(self):
        backend = input_backends.UInputBackend()
        modifiers = {modifier: False for modifier in MODIFIER_KEYS}
        modifiers["Ctrl_L"] = True

        backend.emit_key("F5", modifiers)

        self.assertEqual(
            self.fake_uinput.device.events,
            [
                ("KEY_LEFTCTRL", 1),
                ("KEY_F5", 1),
                ("KEY_F5", 0),
                ("KEY_LEFTCTRL", 0),
            ],
        )


if __name__ == "__main__":
    unittest.main()
