import sys

from .constants import APP_DISPLAY_NAME, APP_ID
from .environment import (
    install_kwin_rule_if_needed,
    is_kde_environment,
    is_wayland_session,
)
from .gtk import Gio, GLib, Gtk
from .kwin_autoshow import KWinVirtualKeyboardSuppressor
from .window import BUG_REPORT_URL, VirtualKeyboard


USAGE = f"""Usage: vboard [OPTION]

Options:
  --toggle    Toggle the vboard window show/hide status
  --help      Show this help message

Report bugs: {BUG_REPORT_URL}
"""


class VboardApplication(Gtk.Application):
    def __init__(self):
        super().__init__(
            application_id=APP_ID,
            flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE,
        )
        self.window = None
        self._recreating_window = False
        self.system_keyboard_suppressor = None

    def do_startup(self):
        Gtk.Application.do_startup(self)
        GLib.set_prgname(APP_ID)
        GLib.set_application_name(APP_DISPLAY_NAME)
        if is_kde_environment() and is_wayland_session():
            suppressor = KWinVirtualKeyboardSuppressor(Gio, GLib)
            if suppressor.start():
                self.system_keyboard_suppressor = suppressor

    def ensure_window(self):
        if self.window is None:
            self.window = VirtualKeyboard(application=self)
            self.window.connect("destroy", lambda w: w.save_settings())
            self.window.connect("destroy", self.on_window_destroy)
            self.window.connect("configure-event", self.window.on_resize)
            self.window.connect("notify::visible", self.on_window_visibility_changed)
            if (
                not self.window.dock_active
                and self.window.config_pos_x > 0
                and self.window.config_pos_y > 0
            ):
                self.window.move(self.window.config_pos_x, self.window.config_pos_y)
            self.window.set_header_controls_visible(False)
            self.window.update_tray_menu()
        return self.window

    def show_window(self, window):
        VboardApplication.update_system_keyboard_suppression(self, True)
        window.show_all()
        window.set_header_controls_visible(False)
        window.present()
        window.request_keep_above()
        window.update_tray_menu()

    def do_activate(self):
        is_initial_activation = self.window is None
        window = self.ensure_window()
        if (
            is_initial_activation
            and window.start_minimized
            and window.tray_icon is not None
        ):
            window.hide()
            window.update_tray_menu()
            return

        self.show_window(window)

    def do_command_line(self, command_line):
        args = command_line.get_arguments()[1:]
        if args in (["--help"], ["-h"]):
            command_line.print_literal(USAGE)
            return 0

        if args == ["--toggle"]:
            if self.window is None:
                window = self.ensure_window()
                self.show_window(window)
            else:
                self.window.toggle_visibility()
            return 0

        if not args:
            self.activate()
            return 0

        command_line.printerr_literal(USAGE)
        return 1

    def on_window_destroy(self, window):
        self.window = None
        if self._recreating_window:
            GLib.idle_add(self.finish_window_recreation)
            return
        VboardApplication.update_system_keyboard_suppression(self, False)
        self.quit()

    def on_window_visibility_changed(self, window, parameter=None):
        visible = bool(window.get_visible()) or self._recreating_window
        self.update_system_keyboard_suppression(visible)

    def update_system_keyboard_suppression(self, vboard_visible):
        suppressor = getattr(self, "system_keyboard_suppressor", None)
        if suppressor is not None:
            suppressor.set_vboard_visible(vboard_visible)

    def do_shutdown(self):
        if self.system_keyboard_suppressor is not None:
            self.system_keyboard_suppressor.stop()
            self.system_keyboard_suppressor = None
        Gtk.Application.do_shutdown(self)

    def recreate_window(self):
        """Recreate the window so pre-map layer-shell options can change."""

        if self.window is None or self._recreating_window:
            return False
        self._recreating_window = True
        self.hold()
        self.window.destroy()
        return False

    def finish_window_recreation(self):
        try:
            window = self.ensure_window()
            window.preserve_visibility_during_recreation()
            self.show_window(window)
        finally:
            self._recreating_window = False
            self.release()
        return False


def main(argv=None):
    install_kwin_rule_if_needed()
    app = VboardApplication()
    return app.run(argv or sys.argv)
