import unittest
from types import SimpleNamespace
from unittest import mock

from vboard.constants import MODIFIER_KEYS
from vboard.window import VirtualKeyboard


class FakeBackend:
    def __init__(self):
        self.events = []

    def press_key(self, key_event):
        self.events.append(("down", key_event))

    def release_key(self, key_event):
        self.events.append(("up", key_event))


class FakeGLib:
    def __init__(self):
        self.next_source = 1
        self.callbacks = {}
        self.removed = []

    def timeout_add(self, interval, callback, *args):
        source = self.next_source
        self.next_source += 1
        self.callbacks[source] = (interval, callback, args)
        return source

    def source_remove(self, source):
        self.removed.append(source)
        self.callbacks.pop(source, None)


class TouchInputTest(unittest.TestCase):
    def make_keyboard(self):
        keyboard = SimpleNamespace(
            active_touch_keys={},
            held_touch_modifiers={},
            modifiers={modifier: False for modifier in MODIFIER_KEYS},
            backend=FakeBackend(),
            gesture_controller=None,
            emitted=[],
            visual_resets=0,
            KEY_REPEAT_DELAY_MS=400,
            KEY_REPEAT_INTERVAL_MS=100,
        )
        keyboard.clear_key_button_visual_states = lambda except_button=None: None
        keyboard.clear_suggestion_override = lambda update=False: None
        keyboard.update_key_labels = lambda: None
        keyboard.update_modifier = lambda key, value: keyboard.modifiers.__setitem__(
            key,
            value,
        )
        keyboard.reset_modifiers = lambda: VirtualKeyboard.reset_modifiers(keyboard)
        keyboard.emit_key = lambda key: keyboard.emitted.append(key)
        keyboard.schedule_key_button_visual_reset = lambda: setattr(
            keyboard,
            "visual_resets",
            keyboard.visual_resets + 1,
        )
        keyboard.start_touch_repeat = lambda sequence: VirtualKeyboard.start_touch_repeat(
            keyboard,
            sequence,
        )
        keyboard.repeat_touch_key = lambda sequence: VirtualKeyboard.repeat_touch_key(
            keyboard,
            sequence,
        )
        return keyboard

    def setUp(self):
        self.fake_glib = FakeGLib()
        self.glib_patch = mock.patch("vboard.window.GLib", self.fake_glib)
        self.glib_patch.start()
        self.addCleanup(self.glib_patch.stop)

    def test_touch_modifier_is_held_until_its_sequence_ends(self):
        keyboard = self.make_keyboard()

        VirtualKeyboard.begin_touch_key(
            keyboard,
            1,
            object(),
            object(),
            "Ctrl_L",
        )
        self.assertTrue(keyboard.modifiers["Ctrl_L"])
        self.assertEqual(keyboard.backend.events, [("down", "Ctrl_L")])

        VirtualKeyboard.finish_touch_key(keyboard, 1)

        self.assertFalse(keyboard.modifiers["Ctrl_L"])
        self.assertEqual(
            keyboard.backend.events,
            [("down", "Ctrl_L"), ("up", "Ctrl_L")],
        )

    def test_each_touch_key_has_an_independent_repeat_timer(self):
        keyboard = self.make_keyboard()

        VirtualKeyboard.begin_touch_key(keyboard, 1, object(), object(), "A")
        VirtualKeyboard.begin_touch_key(keyboard, 2, object(), object(), "B")

        self.assertEqual(keyboard.emitted, ["A", "B"])
        self.assertEqual(len(self.fake_glib.callbacks), 2)

        VirtualKeyboard.start_touch_repeat(keyboard, 1)
        VirtualKeyboard.repeat_touch_key(keyboard, 1)
        VirtualKeyboard.finish_touch_key(keyboard, 1)

        self.assertEqual(keyboard.emitted, ["A", "B", "A"])
        self.assertIn(3, self.fake_glib.removed)
        self.assertIn(2, self.fake_glib.callbacks)

    def test_reset_modifiers_keeps_a_touch_held_modifier_active(self):
        keyboard = self.make_keyboard()
        keyboard.modifiers["Shift_L"] = True
        keyboard.modifiers["Alt_L"] = True
        keyboard.held_touch_modifiers["Shift_L"] = 1

        VirtualKeyboard.reset_modifiers(keyboard)

        self.assertTrue(keyboard.modifiers["Shift_L"])
        self.assertFalse(keyboard.modifiers["Alt_L"])

    def test_pointer_emulated_touch_events_are_not_processed_twice(self):
        event = SimpleNamespace(get_pointer_emulated=lambda: True)

        self.assertTrue(VirtualKeyboard.is_pointer_emulated_event(event))


if __name__ == "__main__":
    unittest.main()
