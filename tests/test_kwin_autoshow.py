import unittest
from types import SimpleNamespace

from vboard.kwin_autoshow import KWinVirtualKeyboardSuppressor, should_show_vboard
from vboard.window import VirtualKeyboard


class FakeVariant:
    def __init__(self, signature, value=None):
        if value is None:
            value = signature
        self.value = value

    def unpack(self):
        return self.value


class FakeGLib:
    Error = RuntimeError
    Variant = FakeVariant

    def __init__(self):
        self.callbacks = []

    def idle_add(self, callback):
        self.callbacks.append(callback)
        return len(self.callbacks)

    def source_remove(self, timer_id):
        return True

    def flush(self):
        callbacks, self.callbacks = self.callbacks, []
        for callback in callbacks:
            callback()


class FakeGio:
    class DBusCallFlags:
        NONE = 0


class FakeProxy:
    def __init__(self, active):
        self.active = active
        self.calls = []

    def get_cached_property(self, name):
        if name == "active":
            return FakeVariant(self.active)
        return FakeVariant(False)

    def call_sync(self, method, parameters, flags, timeout, cancellable):
        if method.endswith(".Get"):
            interface, property_name = parameters.unpack()
            self.assert_property_call(interface, property_name)
            return FakeVariant((self.active,))
        interface, property_name, value = parameters.unpack()
        self.assert_property_call(interface, property_name)
        self.active = value.unpack()
        self.calls.append(self.active)

    @staticmethod
    def assert_property_call(interface, property_name):
        if interface != "org.kde.kwin.VirtualKeyboard" or property_name != "active":
            raise AssertionError((interface, property_name))


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

    def test_ignores_auto_show_changes_while_screen_is_locked(self):
        calls = []
        suppressor = SimpleNamespace(screen_locked=True)
        application = SimpleNamespace(system_keyboard_suppressor=suppressor)
        window = SimpleNamespace(
            auto_show_on_text_fields=True,
            get_application=lambda: application,
            hide=lambda: calls.append("hide"),
        )

        VirtualKeyboard.on_text_input_visibility_changed(window, False)

        self.assertEqual(calls, [])


class KWinVirtualKeyboardSuppressorTest(unittest.TestCase):
    def make_suppressor(self, active):
        glib = FakeGLib()
        suppressor = KWinVirtualKeyboardSuppressor(FakeGio, glib)
        suppressor.proxy = FakeProxy(active)
        return suppressor, glib

    def test_deactivates_and_restores_an_active_system_keyboard(self):
        suppressor, glib = self.make_suppressor(True)

        suppressor.set_vboard_visible(True)
        suppressor.set_vboard_visible(False)

        self.assertEqual(suppressor.proxy.calls, [False, True])
        self.assertFalse(suppressor.suppression_active)

    def test_does_not_activate_a_system_keyboard_that_was_inactive(self):
        suppressor, glib = self.make_suppressor(False)

        suppressor.set_vboard_visible(True)
        suppressor.set_vboard_visible(False)

        self.assertEqual(suppressor.proxy.calls, [False])

    def test_represses_kwin_reactivation_and_restores_it_later(self):
        suppressor, glib = self.make_suppressor(False)
        suppressor.set_vboard_visible(True)
        suppressor.proxy.active = True

        suppressor._on_kwin_signal(
            suppressor.proxy,
            None,
            "activeChanged",
            FakeVariant(()),
        )
        glib.flush()
        suppressor.set_vboard_visible(False)

        self.assertEqual(suppressor.proxy.calls, [False, False, True])

    def test_releases_for_lock_screen_and_resuppresses_after_unlock(self):
        suppressor, glib = self.make_suppressor(True)
        suppressor.set_vboard_visible(True)

        suppressor._set_screen_locked(True)
        suppressor._set_screen_locked(False)

        self.assertEqual(suppressor.proxy.calls, [False, True, False])
        self.assertTrue(suppressor.suppression_active)


if __name__ == "__main__":
    unittest.main()
