import sys

from .constants import APP_DISPLAY_NAME, APP_ID
from .environment import install_kwin_rule_if_needed
from .gtk import Gio, GLib, Gtk
from .window import VirtualKeyboard


class VboardApplication(Gtk.Application):
    def __init__(self):
        super().__init__(
            application_id=APP_ID,
            flags=Gio.ApplicationFlags.FLAGS_NONE,
        )
        self.window = None

    def do_startup(self):
        Gtk.Application.do_startup(self)
        GLib.set_prgname(APP_ID)
        GLib.set_application_name(APP_DISPLAY_NAME)

    def do_activate(self):
        if self.window is None:
            self.window = VirtualKeyboard(application=self)
            self.window.connect("destroy", lambda w: w.save_settings())
            self.window.connect("destroy", self.on_window_destroy)
            self.window.connect("configure-event", self.window.on_resize)
            if self.window.config_pos_x > 0 and self.window.config_pos_y > 0:
                self.window.move(self.window.config_pos_x, self.window.config_pos_y)
            self.window.show_all()
            self.window.change_visibility()
            return

        self.window.show_all()
        self.window.present()
        self.window.request_keep_above()
        self.window.update_tray_menu()

    def on_window_destroy(self, window):
        self.window = None
        self.quit()


def main(argv=None):
    install_kwin_rule_if_needed()
    app = VboardApplication()
    return app.run(argv or sys.argv)
