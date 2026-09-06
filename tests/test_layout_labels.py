import unittest

from vboard.layouts import get_layout_short_label, get_layout_switch_label


class LayoutSwitchLabelTest(unittest.TestCase):
    def test_uses_ukrainian_xkb_code(self):
        self.assertEqual(get_layout_switch_label("en", "uk"), "UA/EN")

    def test_redraws_for_a_russian_secondary_layout(self):
        self.assertEqual(get_layout_switch_label("en", "ru"), "RU/EN")

    def test_uses_uppercase_short_layout_ids(self):
        self.assertEqual(get_layout_short_label("de"), "DE")

    def test_falls_back_to_a_globe_for_an_unknown_long_id(self):
        self.assertEqual(get_layout_switch_label("en", "custom"), "🌐")


if __name__ == "__main__":
    unittest.main()
