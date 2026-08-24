import unittest

from vboard.plasma_layouts import get_next_quick_layout


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


if __name__ == "__main__":
    unittest.main()
