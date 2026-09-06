import unittest
from types import SimpleNamespace

from vboard.dock import configure_dock_window, effective_window_opacity
from vboard.window import VirtualKeyboard


class FakeLayerShell:
    Layer = SimpleNamespace(TOP="top")
    Edge = SimpleNamespace(LEFT="left", RIGHT="right", BOTTOM="bottom")
    KeyboardMode = SimpleNamespace(NONE="none")

    def __init__(self):
        self.calls = []

    def init_for_window(self, window):
        self.calls.append(("init", window))

    def set_layer(self, window, layer):
        self.calls.append(("layer", layer))

    def set_anchor(self, window, edge, enabled):
        self.calls.append(("anchor", edge, enabled))

    def set_keyboard_mode(self, window, mode):
        self.calls.append(("keyboard", mode))

    def set_namespace(self, window, namespace):
        self.calls.append(("namespace", namespace))

    def auto_exclusive_zone_enable(self, window):
        self.calls.append(("exclusive", window))


class DockModeTest(unittest.TestCase):
    def test_docked_header_is_part_of_window_content(self):
        calls = []
        window = SimpleNamespace(
            dock_active=True,
            header="header",
            set_titlebar=lambda header: calls.append(("titlebar", header)),
        )
        content = SimpleNamespace(
            pack_start=lambda *args: calls.append(("content", *args))
        )

        VirtualKeyboard.attach_header(window, content)

        self.assertEqual(calls, [("content", "header", False, False, 0)])

    def test_floating_header_remains_a_titlebar(self):
        calls = []
        window = SimpleNamespace(
            dock_active=False,
            header="header",
            set_titlebar=lambda header: calls.append(("titlebar", header)),
        )
        content = SimpleNamespace(
            pack_start=lambda *args: calls.append(("content", *args))
        )

        VirtualKeyboard.attach_header(window, content)

        self.assertEqual(calls, [("titlebar", "header")])

    def test_docked_window_is_always_opaque(self):
        self.assertEqual(effective_window_opacity("0.42", True), 1.0)

    def test_floating_window_keeps_configured_opacity(self):
        self.assertEqual(effective_window_opacity("0.42", False), 0.42)

    def test_configures_bottom_dock_and_exclusive_zone(self):
        window = object()
        layer_shell = FakeLayerShell()

        self.assertTrue(configure_dock_window(window, True, layer_shell))

        self.assertIn(("layer", "top"), layer_shell.calls)
        self.assertIn(("anchor", "left", True), layer_shell.calls)
        self.assertIn(("anchor", "right", True), layer_shell.calls)
        self.assertIn(("anchor", "bottom", True), layer_shell.calls)
        self.assertIn(("keyboard", "none"), layer_shell.calls)
        self.assertIn(("exclusive", window), layer_shell.calls)

    def test_disabled_mode_does_not_touch_window(self):
        layer_shell = FakeLayerShell()

        self.assertFalse(configure_dock_window(object(), False, layer_shell))
        self.assertEqual(layer_shell.calls, [])


if __name__ == "__main__":
    unittest.main()
