import unittest
from types import SimpleNamespace
from unittest import mock

from vboard.plasma_layouts import get_next_quick_layout
from vboard.window import VirtualKeyboard


class QuickLayoutSelectionTest(unittest.TestCase):
    def test_switches_between_english_and_ukrainian(self):
        self.assertEqual(get_next_quick_layout("en", ("en", "uk")), "uk")
        self.assertEqual(get_next_quick_layout("uk", ("en", "uk")), "en")

    def test_preserves_the_configured_pair_order(self):
        available = (layout for layout in ("uk", "en"))

        self.assertEqual(get_next_quick_layout("en", available), "uk")

    def test_uses_the_first_quick_layout_for_an_unrelated_current_layout(self):
        self.assertEqual(get_next_quick_layout("de", ("en", "uk")), "en")

    def test_returns_none_without_a_complete_pair(self):
        self.assertIsNone(get_next_quick_layout("en", ("en",)))


class PlasmaLayoutFallbackTest(unittest.TestCase):
    def test_switches_vboard_when_layout_is_unavailable_in_plasma(self):
        plasma_controller = mock.Mock()
        plasma_controller.set_vboard_layout.return_value = False
        keyboard = SimpleNamespace(
            keyboard_layout="en",
            plasma_layout_controller=plasma_controller,
            suggestion_engine=mock.Mock(),
            gesture_controller=None,
            text_prediction_enabled=False,
            current_word="old word",
            normalize_keyboard_layout=lambda layout_key: layout_key,
            refresh_layout_character_lookup=mock.Mock(),
            rebuild_keyboard_grid=mock.Mock(),
            clear_suggestion_override=mock.Mock(),
            update_suggestions=mock.Mock(),
            sync_tray_items=mock.Mock(),
            save_settings=mock.Mock(),
        )

        with mock.patch("builtins.print") as print_mock:
            VirtualKeyboard.set_keyboard_layout(keyboard, "uk")

        self.assertEqual(keyboard.keyboard_layout, "uk")
        plasma_controller.set_vboard_layout.assert_called_once_with("uk")
        keyboard.suggestion_engine.set_layout.assert_called_once_with("uk")
        keyboard.rebuild_keyboard_grid.assert_called_once_with()
        keyboard.save_settings.assert_called_once_with()
        print_mock.assert_called_once_with(
            "Warning: Layout is not available in Plasma; "
            "switching Vboard without system layout synchronization: uk"
        )


if __name__ == "__main__":
    unittest.main()
