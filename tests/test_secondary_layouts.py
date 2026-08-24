import unittest
from types import SimpleNamespace

from vboard.window import VirtualKeyboard


class FakePlasmaLayoutController:
    def __init__(self, available_layouts):
        self.available_layouts = available_layouts

    def get_available_vboard_layouts(self):
        return self.available_layouts


class SecondaryLayoutSelectionTest(unittest.TestCase):
    def make_keyboard(self, available_layouts=None):
        keyboard = SimpleNamespace(
            keyboard_layouts={
                "en": {},
                "uk": {},
                "ru": {},
            },
            keyboard_layout_choices=(
                ("en", "English (US)"),
                ("uk", "Ukrainian"),
                ("ru", "Russian"),
            ),
            primary_keyboard_layout="en",
            plasma_layout_controller=(
                FakePlasmaLayoutController(available_layouts)
                if available_layouts is not None
                else None
            ),
        )
        keyboard.get_available_keyboard_layout_keys = lambda: (
            VirtualKeyboard.get_available_keyboard_layout_keys(keyboard)
        )
        keyboard.get_default_secondary_keyboard_layout = lambda: (
            VirtualKeyboard.get_default_secondary_keyboard_layout(keyboard)
        )
        return keyboard

    def test_non_kde_defaults_to_ukrainian(self):
        keyboard = self.make_keyboard()

        self.assertEqual(
            VirtualKeyboard.get_default_secondary_keyboard_layout(keyboard),
            "uk",
        )

    def test_only_lists_layouts_enabled_in_plasma(self):
        keyboard = self.make_keyboard(("en", "ru"))

        self.assertEqual(
            VirtualKeyboard.get_secondary_keyboard_layout_choices(keyboard),
            (("ru", "Russian"),),
        )

    def test_falls_back_to_an_available_secondary_layout(self):
        keyboard = self.make_keyboard(("en", "ru"))

        self.assertEqual(
            VirtualKeyboard.normalize_secondary_keyboard_layout(keyboard, "uk"),
            "ru",
        )

    def test_returns_no_secondary_choice_when_plasma_has_only_primary(self):
        keyboard = self.make_keyboard(("en",))

        self.assertEqual(
            VirtualKeyboard.get_secondary_keyboard_layout_choices(keyboard),
            (),
        )
        self.assertEqual(
            VirtualKeyboard.get_default_secondary_keyboard_layout(keyboard),
            "en",
        )


if __name__ == "__main__":
    unittest.main()
