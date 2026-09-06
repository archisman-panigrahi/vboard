import unittest
from unittest import mock

from vboard import input_backends
from vboard.constants import FUNCTION_KEYS, MODIFIER_KEYS, NAVIGATION_KEYS


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

    def test_held_modifier_is_not_released_by_an_emitted_key(self):
        backend = input_backends.UInputBackend()
        modifiers = {modifier: False for modifier in MODIFIER_KEYS}
        modifiers["Ctrl_L"] = True

        backend.press_key("Ctrl_L")
        backend.emit_key("C", modifiers)
        backend.release_key("Ctrl_L")

        self.assertEqual(
            self.fake_uinput.device.events,
            [
                ("KEY_LEFTCTRL", 1),
                ("KEY_C", 1),
                ("KEY_C", 0),
                ("KEY_LEFTCTRL", 0),
            ],
        )

    def test_duplicate_press_and_release_are_ignored(self):
        backend = input_backends.UInputBackend()

        backend.press_key("Shift_L")
        backend.press_key("Shift_L")
        backend.release_key("Shift_L")
        backend.release_key("Shift_L")

        self.assertEqual(
            self.fake_uinput.device.events,
            [("KEY_LEFTSHIFT", 1), ("KEY_LEFTSHIFT", 0)],
        )

    def test_registers_navigation_keys(self):
        backend = input_backends.UInputBackend()

        expected_events = {
            "Delete": "KEY_DELETE",
            "Insert": "KEY_INSERT",
            "PageUp": "KEY_PAGEUP",
            "PageDown": "KEY_PAGEDOWN",
            "Home": "KEY_HOME",
            "End": "KEY_END",
        }
        self.assertEqual(set(NAVIGATION_KEYS), set(expected_events))
        for key_event, expected_event in expected_events.items():
            self.assertEqual(backend.key_map[key_event], expected_event)


if __name__ == "__main__":
    unittest.main()
