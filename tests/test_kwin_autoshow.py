import unittest

from vboard.kwin_autoshow import should_show_vboard


class KWinAutoShowPolicyTest(unittest.TestCase):
    def test_shows_for_active_text_field_without_native_panel(self):
        self.assertTrue(should_show_vboard(True, False))

    def test_hides_when_text_field_is_inactive(self):
        self.assertFalse(should_show_vboard(False, False))

    def test_secure_plasma_keyboard_takes_precedence(self):
        self.assertFalse(should_show_vboard(True, True))


if __name__ == "__main__":
    unittest.main()
