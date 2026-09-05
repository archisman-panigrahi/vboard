import unittest
from types import SimpleNamespace

from vboard.app import VboardApplication


class FakeWindow:
    def __init__(self, start_minimized=False, has_tray=True):
        self.start_minimized = start_minimized
        self.dock_active = False
        self.tray_icon = object() if has_tray else None
        self.calls = []

    def show_all(self):
        self.calls.append("show")

    def set_header_controls_visible(self, visible):
        self.calls.append(("header", visible))

    def present(self):
        self.calls.append("present")

    def request_keep_above(self):
        self.calls.append("keep-above")

    def update_tray_menu(self):
        self.calls.append("update-tray")

    def hide(self):
        self.calls.append("hide")

    def toggle_visibility(self):
        self.calls.append("toggle")

    def destroy(self):
        self.calls.append("destroy")


class FakeCommandLine:
    def __init__(self, *args):
        self.args = ["vboard", *args]

    def get_arguments(self):
        return self.args


class StartupVisibilityTest(unittest.TestCase):
    def make_application(self, window):
        application = SimpleNamespace(window=None)

        def ensure_window():
            application.window = window
            return window

        application.ensure_window = ensure_window
        application.show_window = lambda target: VboardApplication.show_window(
            application,
            target,
        )
        return application

    def test_initial_activation_stays_hidden_when_configured(self):
        window = FakeWindow(start_minimized=True)
        application = self.make_application(window)

        VboardApplication.do_activate(application)

        self.assertNotIn("show", window.calls)
        self.assertEqual(window.calls, ["hide", "update-tray"])

    def test_initial_activation_shows_when_tray_is_unavailable(self):
        window = FakeWindow(start_minimized=True, has_tray=False)
        application = self.make_application(window)

        VboardApplication.do_activate(application)

        self.assertIn("show", window.calls)
        self.assertIn("present", window.calls)

    def test_widget_toggle_shows_a_new_window_despite_start_minimized(self):
        window = FakeWindow(start_minimized=True)
        application = self.make_application(window)

        result = VboardApplication.do_command_line(
            application,
            FakeCommandLine("--toggle"),
        )

        self.assertEqual(result, 0)
        self.assertIn("show", window.calls)
        self.assertIn("present", window.calls)
        self.assertNotIn("hide", window.calls)

    def test_widget_toggle_toggles_an_existing_window(self):
        window = FakeWindow(start_minimized=True)
        application = self.make_application(window)
        application.window = window

        VboardApplication.do_command_line(
            application,
            FakeCommandLine("--toggle"),
        )

        self.assertEqual(window.calls, ["toggle"])

    def test_dock_change_recreates_the_window(self):
        window = FakeWindow()
        application = SimpleNamespace(
            window=window,
            _recreating_window=False,
            calls=[],
        )
        application.hold = lambda: application.calls.append("hold")

        result = VboardApplication.recreate_window(application)

        self.assertFalse(result)
        self.assertTrue(application._recreating_window)
        self.assertEqual(application.calls, ["hold"])
        self.assertEqual(window.calls, ["destroy"])


if __name__ == "__main__":
    unittest.main()
