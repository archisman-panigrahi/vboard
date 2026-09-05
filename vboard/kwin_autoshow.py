"""Observe KWin text-input state without implementing an input-method protocol."""

KWIN_BUS_NAME = "org.kde.KWin"
KWIN_OBJECT_PATH = "/VirtualKeyboard"
KWIN_INTERFACE = "org.kde.kwin.VirtualKeyboard"


def should_show_vboard(text_input_active, plasma_keyboard_visible):
    """Let Plasma Keyboard win whenever its secure input panel is visible."""

    return bool(text_input_active) and not bool(plasma_keyboard_visible)


class KWinTextInputMonitor:
    """Report whether Vboard should follow the focused Wayland text field."""

    def __init__(self, gio, glib, callback, delay_ms=120):
        self.gio = gio
        self.glib = glib
        self.callback = callback
        self.delay_ms = delay_ms
        self.proxy = None
        self._timer_id = None
        self._last_value = None

    def start(self):
        if self.proxy is not None:
            return True
        try:
            self.proxy = self.gio.DBusProxy.new_for_bus_sync(
                self.gio.BusType.SESSION,
                self.gio.DBusProxyFlags.NONE,
                None,
                KWIN_BUS_NAME,
                KWIN_OBJECT_PATH,
                KWIN_INTERFACE,
                None,
            )
            self.proxy.connect("g-properties-changed", self._on_properties_changed)
            self._queue_update()
            return True
        except (self.glib.Error, OSError, RuntimeError) as exc:
            self.proxy = None
            print(f"Warning: KWin text-field auto-show is unavailable ({exc}).")
            return False

    def stop(self):
        if self._timer_id is not None:
            self.glib.source_remove(self._timer_id)
            self._timer_id = None
        self.proxy = None
        self._last_value = None

    def _on_properties_changed(self, proxy, changed, invalidated):
        names = set(changed.unpack()) | set(invalidated)
        if names.intersection({"active", "visible"}):
            self._queue_update()

    def _queue_update(self):
        if self._timer_id is not None:
            self.glib.source_remove(self._timer_id)
        self._timer_id = self.glib.timeout_add(self.delay_ms, self._emit_update)

    def _get_bool(self, name):
        value = self.proxy.get_cached_property(name)
        return bool(value.unpack()) if value is not None else False

    def _emit_update(self):
        self._timer_id = None
        if self.proxy is None:
            return False
        value = should_show_vboard(
            self._get_bool("active"),
            self._get_bool("visible"),
        )
        if value != self._last_value:
            self._last_value = value
            self.callback(value)
        return False
