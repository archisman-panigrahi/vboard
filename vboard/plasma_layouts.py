from .gtk import Gio, GLib


PLASMA_LAYOUT_SERVICE = "org.kde.keyboard"
PLASMA_LAYOUT_PATH = "/Layouts"
PLASMA_LAYOUT_INTERFACE = "org.kde.KeyboardLayouts"

VBOARD_TO_XKB_LAYOUT = {
    "de": "de",
    "en": "us",
    "fr": "fr",
    "ru": "ru",
    "sv": "se",
    "uk": "ua",
}
XKB_TO_VBOARD_LAYOUT = {
    xkb_layout: vboard_layout
    for vboard_layout, xkb_layout in VBOARD_TO_XKB_LAYOUT.items()
}

def get_next_quick_layout(current_layout, available_layouts):
    available = tuple(dict.fromkeys(available_layouts))
    if len(available) < 2:
        return None
    if current_layout not in available:
        return available[0]
    current_index = available.index(current_layout)
    return available[(current_index + 1) % len(available)]


class PlasmaLayoutController:
    def __init__(self, on_layout_changed=None):
        self.on_layout_changed = on_layout_changed
        self.proxy = Gio.DBusProxy.new_for_bus_sync(
            Gio.BusType.SESSION,
            Gio.DBusProxyFlags.NONE,
            None,
            PLASMA_LAYOUT_SERVICE,
            PLASMA_LAYOUT_PATH,
            PLASMA_LAYOUT_INTERFACE,
            None,
        )
        self.layouts = []
        self.refresh_layouts()
        self.signal_handler_id = self.proxy.connect("g-signal", self.on_dbus_signal)

    def call(self, method, parameters=None):
        return self.proxy.call_sync(
            method,
            parameters,
            Gio.DBusCallFlags.NONE,
            2000,
            None,
        )

    def refresh_layouts(self):
        result = self.call("getLayoutsList")
        self.layouts = list(result.unpack()[0])
        return self.layouts

    def get_available_vboard_layouts(self):
        return tuple(
            vboard_layout
            for xkb_layout, _variant, _description in self.layouts
            if (vboard_layout := XKB_TO_VBOARD_LAYOUT.get(xkb_layout)) is not None
        )

    def get_current_vboard_layout(self):
        result = self.call("getLayout")
        layout_index = result.unpack()[0]
        return self.vboard_layout_for_index(layout_index)

    def vboard_layout_for_index(self, layout_index):
        if layout_index < 0 or layout_index >= len(self.layouts):
            return None
        xkb_layout = self.layouts[layout_index][0]
        return XKB_TO_VBOARD_LAYOUT.get(xkb_layout)

    def set_vboard_layout(self, vboard_layout):
        xkb_layout = VBOARD_TO_XKB_LAYOUT.get(vboard_layout)
        if xkb_layout is None:
            return False

        for layout_index, (layout, _variant, _description) in enumerate(self.layouts):
            if layout != xkb_layout:
                continue
            result = self.call("setLayout", GLib.Variant("(u)", (layout_index,)))
            return bool(result.unpack()[0])
        return False

    def on_dbus_signal(self, proxy, sender_name, signal_name, parameters):
        if signal_name == "layoutListChanged":
            self.refresh_layouts()
            self.notify_current_layout()
            return

        if signal_name == "layoutChanged":
            layout_index = parameters.unpack()[0]
            self.notify_layout(self.vboard_layout_for_index(layout_index))

    def notify_current_layout(self):
        self.notify_layout(self.get_current_vboard_layout())

    def notify_layout(self, vboard_layout):
        if vboard_layout is not None and self.on_layout_changed is not None:
            self.on_layout_changed(vboard_layout)

    def close(self):
        if self.signal_handler_id is not None:
            self.proxy.disconnect(self.signal_handler_id)
            self.signal_handler_id = None
