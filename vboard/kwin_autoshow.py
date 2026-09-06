"""Observe KWin text-input state without implementing an input-method protocol."""

KWIN_BUS_NAME = "org.kde.KWin"
KWIN_OBJECT_PATH = "/VirtualKeyboard"
KWIN_INTERFACE = "org.kde.kwin.VirtualKeyboard"
DBUS_PROPERTIES_INTERFACE = "org.freedesktop.DBus.Properties"
SCREENSAVER_BUS_NAME = "org.freedesktop.ScreenSaver"
SCREENSAVER_OBJECT_PATH = "/ScreenSaver"
SCREENSAVER_INTERFACE = "org.freedesktop.ScreenSaver"
KDE_SCREENSAVER_BUS_NAME = "org.kde.screensaver"
KDE_SCREENSAVER_INTERFACE = "org.kde.screensaver"


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
            self.proxy.connect("g-signal", self._on_dbus_signal)
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
        if names.intersection({"activeClientSupportsTextInput", "visible"}):
            self._queue_update()

    def _on_dbus_signal(self, proxy, sender_name, signal_name, parameters):
        if signal_name in (
            "activeClientSupportsTextInputChanged",
            "visibleChanged",
        ):
            self._queue_update()

    def _queue_update(self):
        if self._timer_id is not None:
            self.glib.source_remove(self._timer_id)
        self._timer_id = self.glib.timeout_add(self.delay_ms, self._emit_update)

    def _get_bool(self, name):
        try:
            result = self.proxy.call_sync(
                f"{DBUS_PROPERTIES_INTERFACE}.Get",
                self.glib.Variant("(ss)", (KWIN_INTERFACE, name)),
                self.gio.DBusCallFlags.NONE,
                -1,
                None,
            )
            return bool(result.unpack()[0]) if result is not None else False
        except (self.glib.Error, OSError, RuntimeError):
            return False

    def _emit_update(self):
        self._timer_id = None
        if self.proxy is None:
            return False
        value = should_show_vboard(
            self._get_bool("activeClientSupportsTextInput"),
            self._get_bool("visible"),
        )
        if value != self._last_value:
            self._last_value = value
            self.callback(value)
        return False


class KWinVirtualKeyboardSuppressor:
    """Temporarily deactivate KWin's native input panel while Vboard is shown."""

    def __init__(self, gio, glib):
        self.gio = gio
        self.glib = glib
        self.proxy = None
        self.screen_saver_proxy = None
        self.kde_screen_saver_proxy = None
        self.vboard_visible = False
        self.screen_locked = False
        self.suppression_active = False
        self._restore_active = False
        self._enforce_timer_id = None

    def _new_proxy(self, bus_name, object_path, interface):
        return self.gio.DBusProxy.new_for_bus_sync(
            self.gio.BusType.SESSION,
            self.gio.DBusProxyFlags.NONE,
            None,
            bus_name,
            object_path,
            interface,
            None,
        )

    def start(self):
        if self.proxy is not None:
            return True
        try:
            self.proxy = self._new_proxy(
                KWIN_BUS_NAME,
                KWIN_OBJECT_PATH,
                KWIN_INTERFACE,
            )
            self.proxy.connect("g-properties-changed", self._on_properties_changed)
            self.proxy.connect("g-signal", self._on_kwin_signal)
        except (self.glib.Error, OSError, RuntimeError) as exc:
            self.proxy = None
            print(f"Warning: Could not control KWin's virtual keyboard ({exc}).")
            return False

        self._start_screen_lock_monitors()
        return True

    def _start_screen_lock_monitors(self):
        try:
            self.screen_saver_proxy = self._new_proxy(
                SCREENSAVER_BUS_NAME,
                SCREENSAVER_OBJECT_PATH,
                SCREENSAVER_INTERFACE,
            )
            self.screen_saver_proxy.connect("g-signal", self._on_screen_saver_signal)
            result = self.screen_saver_proxy.call_sync(
                "GetActive",
                None,
                self.gio.DBusCallFlags.NONE,
                -1,
                None,
            )
            if result is not None:
                self.screen_locked = bool(result.unpack()[0])
        except (self.glib.Error, OSError, RuntimeError):
            self.screen_saver_proxy = None

        try:
            self.kde_screen_saver_proxy = self._new_proxy(
                KDE_SCREENSAVER_BUS_NAME,
                SCREENSAVER_OBJECT_PATH,
                KDE_SCREENSAVER_INTERFACE,
            )
            self.kde_screen_saver_proxy.connect(
                "g-signal",
                self._on_kde_screen_saver_signal,
            )
        except (self.glib.Error, OSError, RuntimeError):
            self.kde_screen_saver_proxy = None

    def _get_bool(self, name):
        if self.proxy is None:
            return False
        try:
            result = self.proxy.call_sync(
                f"{DBUS_PROPERTIES_INTERFACE}.Get",
                self.glib.Variant("(ss)", (KWIN_INTERFACE, name)),
                self.gio.DBusCallFlags.NONE,
                -1,
                None,
            )
            return bool(result.unpack()[0]) if result is not None else False
        except (self.glib.Error, OSError, RuntimeError):
            return False

    def _set_active(self, active):
        if self.proxy is None:
            return False
        try:
            self.proxy.call_sync(
                f"{DBUS_PROPERTIES_INTERFACE}.Set",
                self.glib.Variant(
                    "(ssv)",
                    (
                        KWIN_INTERFACE,
                        "active",
                        self.glib.Variant("b", bool(active)),
                    ),
                ),
                self.gio.DBusCallFlags.NONE,
                -1,
                None,
            )
            return True
        except (self.glib.Error, OSError, RuntimeError) as exc:
            print(f"Warning: Could not update KWin's virtual keyboard ({exc}).")
            return False

    def set_vboard_visible(self, visible):
        self.vboard_visible = bool(visible)
        self._apply_requested_state()

    def _apply_requested_state(self):
        should_suppress = self.vboard_visible and not self.screen_locked
        if should_suppress and not self.suppression_active:
            self._restore_active = self._get_bool("active")
            self.suppression_active = True
            self._set_active(False)
        elif not should_suppress and self.suppression_active:
            self._release_suppression()

    def _release_suppression(self):
        restore_active = self._restore_active
        self.suppression_active = False
        self._restore_active = False
        if restore_active:
            self._set_active(True)

    def _on_properties_changed(self, proxy, changed, invalidated):
        names = set(changed.unpack()) | set(invalidated)
        if (
            self.suppression_active
            and "active" in names
            and self._get_bool("active")
        ):
            self._restore_active = True
            self._queue_enforcement()

    def _on_kwin_signal(self, proxy, sender_name, signal_name, parameters):
        if (
            signal_name == "activeChanged"
            and self.suppression_active
            and self._get_bool("active")
        ):
            self._restore_active = True
            self._queue_enforcement()

    def _queue_enforcement(self):
        if self._enforce_timer_id is None:
            self._enforce_timer_id = self.glib.idle_add(self._enforce_suppression)

    def _enforce_suppression(self):
        self._enforce_timer_id = None
        if (
            self.suppression_active
            and self.vboard_visible
            and not self.screen_locked
            and self._get_bool("active")
        ):
            self._set_active(False)
        return False

    def _set_screen_locked(self, locked):
        locked = bool(locked)
        if locked == self.screen_locked:
            return
        self.screen_locked = locked
        self._apply_requested_state()

    def _on_screen_saver_signal(self, proxy, sender_name, signal_name, parameters):
        if signal_name == "ActiveChanged":
            self._set_screen_locked(parameters.unpack()[0])

    def _on_kde_screen_saver_signal(
        self,
        proxy,
        sender_name,
        signal_name,
        parameters,
    ):
        if signal_name == "AboutToLock":
            self._set_screen_locked(True)

    def stop(self):
        if self._enforce_timer_id is not None:
            self.glib.source_remove(self._enforce_timer_id)
            self._enforce_timer_id = None
        self.vboard_visible = False
        if self.suppression_active:
            self._release_suppression()
        self.proxy = None
        self.screen_saver_proxy = None
        self.kde_screen_saver_proxy = None
