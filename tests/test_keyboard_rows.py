import unittest
from types import SimpleNamespace

from vboard.window import VirtualKeyboard


class NavigationColumnsTest(unittest.TestCase):
    def make_keyboard(self):
        keyboard = SimpleNamespace()
        keyboard.get_layout_config = lambda: {
            "rows": [
                ["A", "Backspace"],
                ["Tab", "B"],
                ["CapsLock", "C", "Enter"],
                ["Shift_L", "D", "Shift_R", "↑"],
                ["Ctrl_L", "Space", "Ctrl_R", "←", "↓", "→"],
            ]
        }
        keyboard.get_row_width = VirtualKeyboard.get_row_width
        keyboard.get_key_column = VirtualKeyboard.get_key_column
        keyboard.insert_spacer_before = VirtualKeyboard.insert_spacer_before
        keyboard.make_spacer_key = VirtualKeyboard.make_spacer_key
        return keyboard

    def test_adds_two_navigation_columns_to_the_first_three_rows(self):
        keyboard = self.make_keyboard()

        rows = VirtualKeyboard.get_active_key_rows(keyboard)

        self.assertEqual(rows[0][-2:], ["Delete", "Insert"])
        self.assertEqual(rows[1][-2:], ["PageUp", "Home"])
        self.assertEqual(rows[2][-2:], ["PageDown", "End"])

    def test_up_and_down_arrows_stay_in_the_same_column(self):
        keyboard = self.make_keyboard()

        rows = VirtualKeyboard.get_active_key_rows(keyboard)

        up_column = VirtualKeyboard.get_key_column(rows[3], "↑")
        down_column = VirtualKeyboard.get_key_column(rows[4], "↓")
        self.assertEqual(up_column, down_column)


if __name__ == "__main__":
    unittest.main()
