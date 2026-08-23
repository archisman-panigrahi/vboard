import unittest

from vboard.plasma_layouts import get_next_quick_layout


class QuickLayoutSelectionTest(unittest.TestCase):
    def test_switches_between_english_and_ukrainian(self):
        self.assertEqual(get_next_quick_layout("en", ("en", "uk")), "uk")
        self.assertEqual(get_next_quick_layout("uk", ("en", "uk")), "en")

    def test_accepts_a_generator_in_any_order(self):
        available = (layout for layout in ("uk", "en"))

        self.assertEqual(get_next_quick_layout("en", available), "uk")

    def test_uses_the_first_quick_layout_for_an_unrelated_current_layout(self):
        self.assertEqual(get_next_quick_layout("de", ("de", "uk")), "uk")

    def test_returns_none_when_no_quick_layout_is_available(self):
        self.assertIsNone(get_next_quick_layout("de", ("de", "fr")))


if __name__ == "__main__":
    unittest.main()
