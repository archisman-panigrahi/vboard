import unittest
from types import SimpleNamespace

from vboard.kwin_autoshow import should_show_vboard
from vboard.window import VirtualKeyboard


class KWinAutoShowPolicyTest(unittest.TestCase):
    def test_shows_for_active_text_field_without_native_panel(self):
        self.assertTrue(should_show_vboard(True, False))

    def test_hides_when_text_field_is_inactive(self):
        self.assertFalse(should_show_vboard(False, False))

    def test_secure_plasma_keyboard_takes_precedence(self):
        self.assertFalse(should_show_vboard(True, True))

    def test_initial_inactive_event_does_not_hide_recreated_window(self):
        calls = []
        window = SimpleNamespace(
            auto_show_on_text_fields=True,
            _suppress_next_auto_hide=True,
            set_header_controls_visible=lambda visible: calls.append(
                ("header", visible)
            ),
            hide=lambda: calls.append("hide"),
            update_tray_menu=lambda: calls.append("tray"),
        )

        VirtualKeyboard.on_text_input_visibility_changed(window, False)

        self.assertFalse(window._suppress_next_auto_hide)
        self.assertEqual(calls, [])

    def test_later_inactive_event_still_hides_recreated_window(self):
        calls = []
        window = SimpleNamespace(
            auto_show_on_text_fields=True,
            _suppress_next_auto_hide=False,
            set_header_controls_visible=lambda visible: calls.append(
                ("header", visible)
            ),
            hide=lambda: calls.append("hide"),
            update_tray_menu=lambda: calls.append("tray"),
        )

        VirtualKeyboard.on_text_input_visibility_changed(window, False)

        self.assertEqual(calls, [("header", False), "hide", "tray"])


if __name__ == "__main__":
    unittest.main()
