import configparser
import importlib
import os
import sys

from .constants import (
    APP_DISPLAY_NAME,
    COMMAND_MODIFIER_KEYS,
    COLOR_CHOICES,
    DEFAULT_KEYBOARD_LAYOUT,
    ENHANCED_BACKGROUND_PRESET,
    FUNCTION_KEYS,
    KEY_WIDTHS,
    LAYOUT_SWITCH_KEY,
    LIGHT_BACKGROUND_COLORS,
    MODIFIER_KEYS,
    NAVIGATION_KEYS,
    NAVIGATION_ROW_KEYS,
    ONBOARD_BACKGROUND_PRESET,
    SPACER_KEY_PREFIX,
    SUGGESTION_LIMIT,
    SUPPORTED_WORD_CONNECTORS,
    VERSION,
)
from .environment import DESKTOP_ENV, is_kde_environment
from .gtk import (
    APPINDICATOR_AVAILABLE,
    APPINDICATOR_BACKEND,
    AppIndicator3,
    Gdk,
    Gio,
    GLib,
    Gtk,
)
from .input_backends import NullInputBackend, UInputBackend
from .layouts import get_default_layout_key, get_layout_choices, load_keyboard_layouts
from .plasma_layouts import PlasmaLayoutController, get_next_quick_layout
from .suggestions import HunspellSuggestionEngine


BUG_REPORT_URL = "https://github.com/archisman-panigrahi/vboard/issues/"

STATUS_NOTIFIER_ITEM_XML = """
<node>
  <interface name="org.kde.StatusNotifierItem">
    <property name="Category" type="s" access="read"/>
    <property name="Id" type="s" access="read"/>
    <property name="Title" type="s" access="read"/>
    <property name="Status" type="s" access="read"/>
    <property name="WindowId" type="i" access="read"/>
    <property name="IconName" type="s" access="read"/>
    <property name="IconThemePath" type="s" access="read"/>
    <property name="IconPixmap" type="a(iiay)" access="read"/>
    <property name="OverlayIconName" type="s" access="read"/>
    <property name="OverlayIconPixmap" type="a(iiay)" access="read"/>
    <property name="AttentionIconName" type="s" access="read"/>
    <property name="AttentionIconPixmap" type="a(iiay)" access="read"/>
    <property name="AttentionMovieName" type="s" access="read"/>
    <property name="ToolTip" type="(sa(iiay)ss)" access="read"/>
    <property name="ItemIsMenu" type="b" access="read"/>
    <property name="Menu" type="o" access="read"/>
    <method name="ContextMenu">
      <arg name="x" type="i" direction="in"/>
      <arg name="y" type="i" direction="in"/>
    </method>
    <method name="Activate">
      <arg name="x" type="i" direction="in"/>
      <arg name="y" type="i" direction="in"/>
    </method>
    <method name="SecondaryActivate">
      <arg name="x" type="i" direction="in"/>
      <arg name="y" type="i" direction="in"/>
    </method>
    <method name="Scroll">
      <arg name="delta" type="i" direction="in"/>
      <arg name="orientation" type="s" direction="in"/>
    </method>
  </interface>
</node>
"""

DBUS_MENU_XML = """
<node>
  <interface name="com.canonical.dbusmenu">
    <property name="Version" type="u" access="read"/>
    <property name="TextDirection" type="s" access="read"/>
    <property name="Status" type="s" access="read"/>
    <property name="IconThemePath" type="as" access="read"/>
    <method name="GetLayout">
      <arg name="parentId" type="i" direction="in"/>
      <arg name="recursionDepth" type="i" direction="in"/>
      <arg name="propertyNames" type="as" direction="in"/>
      <arg name="revision" type="u" direction="out"/>
      <arg name="layout" type="(ia{sv}av)" direction="out"/>
    </method>
    <method name="GetGroupProperties">
      <arg name="ids" type="ai" direction="in"/>
      <arg name="propertyNames" type="as" direction="in"/>
      <arg name="properties" type="a(ia{sv})" direction="out"/>
    </method>
    <method name="GetProperty">
      <arg name="id" type="i" direction="in"/>
      <arg name="name" type="s" direction="in"/>
      <arg name="value" type="v" direction="out"/>
    </method>
    <method name="Event">
      <arg name="id" type="i" direction="in"/>
      <arg name="eventId" type="s" direction="in"/>
      <arg name="data" type="v" direction="in"/>
      <arg name="timestamp" type="u" direction="in"/>
    </method>
    <method name="EventGroup">
      <arg name="events" type="a(isvu)" direction="in"/>
      <arg name="idErrors" type="ai" direction="out"/>
    </method>
    <method name="AboutToShow">
      <arg name="id" type="i" direction="in"/>
      <arg name="needUpdate" type="b" direction="out"/>
    </method>
    <method name="AboutToShowGroup">
      <arg name="ids" type="ai" direction="in"/>
      <arg name="updatesNeeded" type="ai" direction="out"/>
      <arg name="idErrors" type="ai" direction="out"/>
    </method>
    <signal name="ItemsPropertiesUpdated">
      <arg name="updatedProps" type="a(ia{sv})"/>
      <arg name="removedProps" type="a(ias)"/>
    </signal>
    <signal name="LayoutUpdated">
      <arg name="revision" type="u"/>
      <arg name="parent" type="i"/>
    </signal>
  </interface>
</node>
"""


class StatusNotifierTrayIcon:
    OBJECT_PATH = "/StatusNotifierItem"
    MENU_PATH = "/StatusNotifierItem/Menu"
    INTERFACE_NAME = "org.kde.StatusNotifierItem"
    MENU_INTERFACE_NAME = "com.canonical.dbusmenu"
    WATCHER_NAME = "org.kde.StatusNotifierWatcher"
    WATCHER_PATH = "/StatusNotifierWatcher"
    DBUS_NAME = "org.freedesktop.DBus"
    DBUS_PATH = "/org/freedesktop/DBus"
    MENU_SEPARATOR_ID = 5
    MENU_LAYOUT_ID = 6
    MENU_SECOND_SEPARATOR_ID = 100
    MENU_LAYOUT_ID_OFFSET = 1000

    def __init__(self, window, icon_name):
        self.window = window
        self.icon_name = icon_name
        self.connection = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        self.bus_name = f"org.freedesktop.StatusNotifierItem-{os.getpid()}-1"
        self.registration_id = None
        self.menu_registration_id = None
        self.menu_revision = 1
        self.name_acquired = False
        try:
            request_result = self.connection.call_sync(
                self.DBUS_NAME,
                self.DBUS_PATH,
                self.DBUS_NAME,
                "RequestName",
                GLib.Variant("(su)", (self.bus_name, 0)),
                GLib.VariantType.new("(u)"),
                Gio.DBusCallFlags.NONE,
                1000,
                None,
            )
            request_reply = request_result.unpack()[0]
            if request_reply not in (1, 4):
                raise RuntimeError(f"Could not acquire D-Bus name {self.bus_name}")
            self.name_acquired = True

            self.node_info = Gio.DBusNodeInfo.new_for_xml(STATUS_NOTIFIER_ITEM_XML)
            self.interface_info = self.node_info.interfaces[0]
            self.menu_node_info = Gio.DBusNodeInfo.new_for_xml(DBUS_MENU_XML)
            self.menu_interface_info = self.menu_node_info.interfaces[0]
            self.menu_registration_id = self.connection.register_object(
                self.MENU_PATH,
                self.menu_interface_info,
                self.on_menu_method_call,
                self.on_menu_get_property,
                None,
            )
            self.registration_id = self.connection.register_object(
                self.OBJECT_PATH,
                self.interface_info,
                self.on_method_call,
                self.on_get_property,
                None,
            )
            self.connection.call_sync(
                self.WATCHER_NAME,
                self.WATCHER_PATH,
                self.WATCHER_NAME,
                "RegisterStatusNotifierItem",
                GLib.Variant("(s)", (self.bus_name,)),
                None,
                Gio.DBusCallFlags.NONE,
                1000,
                None,
            )
        except Exception:
            self.unregister()
            raise

    def on_method_call(
        self,
        connection,
        sender,
        object_path,
        interface_name,
        method_name,
        parameters,
        invocation,
    ):
        if method_name == "Activate":
            GLib.idle_add(self.window.on_tray_activate, None)
            invocation.return_value(None)
            return

        if method_name == "ContextMenu":
            x, y = parameters.unpack()
            GLib.idle_add(self.window.popup_tray_menu_at_coordinates, x, y)
            invocation.return_value(None)
            return

        if method_name == "SecondaryActivate":
            invocation.return_value(None)
            return

        if method_name == "Scroll":
            invocation.return_value(None)
            return

        invocation.return_dbus_error(
            "org.kde.StatusNotifierItem.Error.NotSupported",
            f"Unsupported tray method: {method_name}",
        )

    def on_get_property(
        self,
        connection,
        sender,
        object_path,
        interface_name,
        property_name,
    ):
        property_values = {
            "Category": GLib.Variant("s", "ApplicationStatus"),
            "Id": GLib.Variant("s", "vboard"),
            "Title": GLib.Variant("s", APP_DISPLAY_NAME),
            "Status": GLib.Variant("s", "Active"),
            "WindowId": GLib.Variant("i", 0),
            "IconName": GLib.Variant("s", self.icon_name),
            "IconThemePath": GLib.Variant("s", ""),
            "IconPixmap": GLib.Variant("a(iiay)", []),
            "OverlayIconName": GLib.Variant("s", ""),
            "OverlayIconPixmap": GLib.Variant("a(iiay)", []),
            "AttentionIconName": GLib.Variant("s", ""),
            "AttentionIconPixmap": GLib.Variant("a(iiay)", []),
            "AttentionMovieName": GLib.Variant("s", ""),
            "ToolTip": GLib.Variant(
                "(sa(iiay)ss)",
                (self.icon_name, [], APP_DISPLAY_NAME, "Virtual Keyboard"),
            ),
            "ItemIsMenu": GLib.Variant("b", False),
            "Menu": GLib.Variant("o", self.MENU_PATH),
        }
        return property_values.get(property_name)

    def on_menu_method_call(
        self,
        connection,
        sender,
        object_path,
        interface_name,
        method_name,
        parameters,
        invocation,
    ):
        if method_name == "GetLayout":
            invocation.return_value(
                GLib.Variant(
                    "(u(ia{sv}av))",
                    (self.menu_revision, self.get_menu_layout()),
                )
            )
            return

        if method_name == "GetGroupProperties":
            ids, property_names = parameters.unpack()
            invocation.return_value(
                GLib.Variant(
                    "(a(ia{sv}))",
                    ([self.get_menu_properties(item_id) for item_id in ids],),
                )
            )
            return

        if method_name == "GetProperty":
            item_id, property_name = parameters.unpack()
            value = self.get_menu_properties(item_id).get(
                property_name,
                GLib.Variant("s", ""),
            )
            invocation.return_value(GLib.Variant("(v)", (value,)))
            return

        if method_name == "Event":
            item_id, event_id, data, timestamp = parameters.unpack()
            self.handle_menu_event(item_id, event_id)
            invocation.return_value(None)
            return

        if method_name == "EventGroup":
            for item_id, event_id, data, timestamp in parameters.unpack()[0]:
                self.handle_menu_event(item_id, event_id)
            invocation.return_value(GLib.Variant("(ai)", ([],)))
            return

        if method_name == "AboutToShow":
            invocation.return_value(GLib.Variant("(b)", (False,)))
            return

        if method_name == "AboutToShowGroup":
            invocation.return_value(GLib.Variant("(aiai)", ([], [])))
            return

        invocation.return_dbus_error(
            "com.canonical.dbusmenu.Error.NotSupported",
            f"Unsupported menu method: {method_name}",
        )

    def on_menu_get_property(
        self,
        connection,
        sender,
        object_path,
        interface_name,
        property_name,
    ):
        property_values = {
            "Version": GLib.Variant("u", 3),
            "TextDirection": GLib.Variant("s", "ltr"),
            "Status": GLib.Variant("s", "normal"),
            "IconThemePath": GLib.Variant("as", []),
        }
        return property_values.get(property_name)

    def menu_rows(self):
        rows = [
            (1, {"label": "Hide" if self.window.get_visible() else "Show"}),
            (
                2,
                {
                    "label": "Text Prediction",
                    "toggle-type": "checkmark",
                    "toggle-state": int(self.window.text_prediction_enabled),
                },
            ),
            (
                3,
                {
                    "label": "Touch Typing (requires app restart)",
                    "toggle-type": "checkmark",
                    "toggle-state": int(self.window.gesture_enabled),
                },
            ),
            (
                4,
                {
                    "label": "Visual Feedback",
                    "enabled": self.window.gesture_enabled,
                    "toggle-type": "checkmark",
                    "toggle-state": int(
                        self.window.gesture_visual_feedback_enabled
                    ),
                },
            ),
            (
                self.MENU_SEPARATOR_ID,
                {"type": "separator", "enabled": False},
            ),
            (
                self.MENU_LAYOUT_ID,
                {
                    "label": "Keyboard Layout",
                    "children-display": "submenu",
                },
            ),
            (
                self.MENU_SECOND_SEPARATOR_ID,
                {"type": "separator", "enabled": False},
            ),
            (8, {"label": "About"}),
            (10, {"label": "Report bugs"}),
            (9, {"label": "Quit"}),
        ]
        return rows

    def layout_item_id(self, index):
        return self.MENU_LAYOUT_ID_OFFSET + index

    def get_menu_properties(self, item_id):
        properties = {"enabled": True, "visible": True}
        for row_id, row_properties in self.menu_rows():
            if row_id == item_id:
                properties.update(row_properties)
                break
        else:
            for index, (layout_key, layout_label) in enumerate(
                self.window.keyboard_layout_choices
            ):
                if self.layout_item_id(index) == item_id:
                    properties.update(
                        {
                            "label": layout_label,
                            "toggle-type": "radio",
                            "toggle-state": int(
                                layout_key == self.window.keyboard_layout
                            ),
                        }
                    )
                    break

        return {
            name: self.menu_property_variant(value)
            for name, value in properties.items()
        }

    def menu_property_variant(self, value):
        if isinstance(value, bool):
            return GLib.Variant("b", value)
        if isinstance(value, int):
            return GLib.Variant("i", value)
        return GLib.Variant("s", value)

    def menu_layout_item(self, item_id, children=None):
        return GLib.Variant(
            "(ia{sv}av)",
            (item_id, self.get_menu_properties(item_id), children or []),
        )

    def get_menu_layout(self):
        layout_children = [
            self.menu_layout_item(self.layout_item_id(index))
            for index, _choice in enumerate(self.window.keyboard_layout_choices)
        ]
        children = []
        for item_id, _properties in self.menu_rows():
            if item_id == self.MENU_LAYOUT_ID:
                children.append(self.menu_layout_item(item_id, layout_children))
            else:
                children.append(self.menu_layout_item(item_id))
        return (0, {}, children)

    def handle_menu_event(self, item_id, event_id):
        if event_id not in ("clicked", "opened"):
            return
        if event_id == "opened":
            self.emit_menu_updated()
            return

        actions = {
            1: lambda: self.window.on_tray_activate(None),
            2: lambda: self.window.set_text_prediction_enabled(
                not self.window.text_prediction_enabled
            ),
            3: self.toggle_gesture_typing,
            4: lambda: self.window.set_gesture_visual_feedback_enabled(
                not self.window.gesture_visual_feedback_enabled
            ),
            8: lambda: self.window.on_tray_about(None),
            9: lambda: self.window.on_tray_quit(None),
            10: lambda: self.window.open_bug_report_url(),
        }
        if item_id in actions:
            GLib.idle_add(actions[item_id])
            return

        layout_index = item_id - self.MENU_LAYOUT_ID_OFFSET
        if 0 <= layout_index < len(self.window.keyboard_layout_choices):
            layout_key = self.window.keyboard_layout_choices[layout_index][0]
            GLib.idle_add(self.window.set_keyboard_layout, layout_key)

    def toggle_gesture_typing(self):
        if self.window.gesture_enabled:
            self.window.disable_gesture_typing()
        else:
            self.window.enable_gesture_typing()

    def emit_menu_updated(self):
        if self.menu_registration_id is None:
            return
        self.menu_revision += 1
        self.connection.emit_signal(
            None,
            self.MENU_PATH,
            self.MENU_INTERFACE_NAME,
            "LayoutUpdated",
            GLib.Variant("(ui)", (self.menu_revision, 0)),
        )

    def unregister(self):
        if self.menu_registration_id is not None:
            self.connection.unregister_object(self.menu_registration_id)
            self.menu_registration_id = None
        if self.registration_id is not None:
            self.connection.unregister_object(self.registration_id)
            self.registration_id = None
        if self.name_acquired:
            try:
                self.connection.call_sync(
                    self.DBUS_NAME,
                    self.DBUS_PATH,
                    self.DBUS_NAME,
                    "ReleaseName",
                    GLib.Variant("(s)", (self.bus_name,)),
                    GLib.VariantType.new("(u)"),
                    Gio.DBusCallFlags.NONE,
                    1000,
                    None,
                )
            except Exception:
                pass
            self.name_acquired = False


class VirtualKeyboard(Gtk.Window):
    BASE_KEY_HEIGHT = 52
    BASE_SUGGESTION_HEIGHT = 34
    BASE_SUGGESTION_FONT_SIZE = 15
    BASE_SUGGESTION_SPACING = 4
    BASE_SUGGESTION_MARGIN = 3
    BASE_SUGGESTION_MARGIN_BOTTOM = 1

    def __init__(self, application=None):
        super().__init__(title=APP_DISPLAY_NAME, name="toplevel")
        if application is not None:
            self.set_application(application)

        self.exiting = False
        self.set_border_width(0)
        self.set_resizable(True)
        self.set_keep_above(True)
        self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True)
        self.stick()
        self.set_modal(False)
        self.set_focus_on_map(False)
        self.set_can_focus(False)
        self.set_accept_focus(False)
        self.set_deletable(True)
        self.set_type_hint(Gdk.WindowTypeHint.DIALOG)

        self.connect("delete-event", self.on_delete_event)
        self.connect("map-event", self.on_map_keep_above)
        self.connect("window-state-event", self.on_window_state_changed)
        self.add_events(Gdk.EventMask.BUTTON_RELEASE_MASK | Gdk.EventMask.LEAVE_NOTIFY_MASK)
        self.connect("button-release-event", self.on_window_button_release_event)
        self.connect("leave-notify-event", self.on_window_leave_notify_event)
        self._keep_above_retries = 0
        self._keep_above_timer_id = None
        self.width = 0
        self.height = 0
        self.pos_x = 0
        self.pos_y = 0
        self.config_pos_x = 0
        self.config_pos_y = 0
        self.set_position(Gtk.WindowPosition.NONE)

        self.CONFIG_DIR = os.path.expanduser("~/.config/vboard")
        self.CONFIG_FILE = os.path.join(self.CONFIG_DIR, "settings.conf")
        self.config = configparser.ConfigParser()
        self.keyboard_layouts = load_keyboard_layouts(
            os.path.join(self.CONFIG_DIR, "layouts")
        )
        self.keyboard_layout_choices = get_layout_choices(self.keyboard_layouts)

        self.bg_color = "0,0,0"
        self.opacity = "0.90"
        self.text_color = "white"
        self.style_variant = "onboard"
        self.text_prediction_enabled = True
        self.gesture_enabled = True
        self.gesture_visual_feedback_enabled = True
        self.start_minimized = False
        self.keyboard_layout = DEFAULT_KEYBOARD_LAYOUT
        self.plasma_layout_controller = None
        self.read_settings()
        self.initialize_plasma_layout_sync()

        self.modifiers = {mod_key: False for mod_key in MODIFIER_KEYS}
        self.color_map = dict(COLOR_CHOICES)
        if self.width != 0:
            self.set_default_size(self.width, self.height)

        self.header = Gtk.HeaderBar()
        self.header.set_title("")
        self.header.set_has_subtitle(False)
        self.header.set_show_close_button(False)
        self.buttons = []
        self.header_buttons = []
        self.header_controls_visible = False
        self.key_buttons = {}
        self.modifier_buttons = {}
        self.current_word = ""
        self.suggestion_engine = HunspellSuggestionEngine(
            self.normalize_keyboard_layout(self.keyboard_layout)
        )
        self.suggestion_buttons = []
        self.suggestion_override = None
        self.color_combobox = Gtk.ComboBoxText()
        self.tray_icon = None
        self.tray_menu = None
        self.tray_toggle_item = None
        self.tray_prediction_item = None
        self.tray_gesture_item = None
        self.tray_visual_feedback_item = None
        self.tray_start_minimized_item = None
        self.tray_layout_items = {}
        self.settings_dialog = None
        self.settings_gesture_check = None
        self.settings_visual_feedback_check = None
        self.css_provider = Gtk.CssProvider()
        self._css_provider_registered = False
        self._last_suggestion_scale = None
        self.caps_lock_active = False
        self._syncing_tray_items = False
        self.layout_character_lookup = {}
        self.suggestion_font_size = self.BASE_SUGGESTION_FONT_SIZE
        self.gesture_controller = None
        self.set_titlebar(self.header)
        self.set_name("vboard-main")
        self.set_default_icon_name(self.get_app_icon_name())

        self.create_settings()
        self.create_tray_icon()
        try:
            self.backend = UInputBackend()
        except Exception as exc:
            self.backend = NullInputBackend(
                f"Could not initialize uinput backend ({exc}); key output is disabled"
            )

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.add(content)

        self.suggestion_revealer = Gtk.Revealer()
        self.suggestion_revealer.set_transition_type(Gtk.RevealerTransitionType.SLIDE_DOWN)
        self.suggestion_revealer.set_no_show_all(True)
        self.suggestion_revealer.set_reveal_child(self.text_prediction_enabled)

        self.suggestion_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self.suggestion_bar.set_name("suggestion-bar")
        self.suggestion_bar.set_margin_start(3)
        self.suggestion_bar.set_margin_end(3)
        self.suggestion_bar.set_margin_top(3)
        self.suggestion_bar.set_margin_bottom(1)
        self.suggestion_revealer.add(self.suggestion_bar)
        self.create_suggestion_buttons()

        grid_overlay = Gtk.Overlay()
        self.grid_overlay = grid_overlay
        content.pack_start(self.suggestion_revealer, False, False, 0)
        self.update_suggestion_bar_visibility()
        content.pack_start(grid_overlay, True, True, 0)

        grid = Gtk.Grid()
        grid.set_row_homogeneous(True)
        grid.set_column_homogeneous(True)
        grid.set_margin_start(3)
        grid.set_margin_end(3)
        grid.set_name("grid")
        grid.connect("size-allocate", self.on_grid_size_allocate)
        self.grid = grid
        grid_overlay.add(grid)
        self.apply_css()
        if self.text_prediction_enabled:
            GLib.idle_add(self.preload_suggestions)
            GLib.idle_add(self.update_suggestion_bar_scale)

        self.keyboard_layout = self.normalize_keyboard_layout(self.keyboard_layout)
        self.refresh_layout_character_lookup()

        for row_index, keys in enumerate(self.get_active_key_rows()):
            self.create_row(grid, row_index, keys)

        if self.gesture_enabled:
            self.enable_gesture_typing(sync_controls=False, save=False)

        self.sync_caps_lock_from_system(connect=True)

    def get_app_icon_name(self):
        icon_theme = Gtk.IconTheme.get_default()
        preferred_icon = "io.github.archisman-panigrahi.vboard"
        fallback_icon = "preferences-desktop-keyboard"
        if icon_theme and icon_theme.has_icon(preferred_icon):
            return preferred_icon
        return fallback_icon

    def create_tray_icon(self):
        icon_name = self.get_app_icon_name()
        if self.create_status_notifier_tray_icon(icon_name):
            return

        if APPINDICATOR_AVAILABLE:
            if APPINDICATOR_BACKEND == "ayatana":
                GLib.log_set_handler(
                    "libayatana-appindicator",
                    GLib.LogLevelFlags.LEVEL_WARNING,
                    lambda domain, level, message, user_data: None,
                    None,
                )

            self.tray_icon = AppIndicator3.Indicator.new(
                "vboard",
                icon_name,
                AppIndicator3.IndicatorCategory.APPLICATION_STATUS,
            )
            self.tray_icon.set_status(AppIndicator3.IndicatorStatus.ACTIVE)
            self.tray_menu = self.build_tray_menu()
            self.tray_icon.set_menu(self.tray_menu)
            return

        if self.create_status_tray_icon(icon_name):
            return

        self.clear_tray_icon(
            "Warning: Could not create tray icon. Tray disabled."
        )

    def create_status_notifier_tray_icon(self, icon_name):
        try:
            self.tray_icon = StatusNotifierTrayIcon(self, icon_name)
            self.tray_menu = self.build_tray_menu()
            print("Using native StatusNotifierItem for system tray.")
            return True
        except Exception as exc:
            self.clear_tray_icon(
                f"Warning: Could not create native StatusNotifierItem tray icon ({exc})."
            )
            return False

    def create_status_tray_icon(self, icon_name):
        try:
            self.tray_icon = Gtk.StatusIcon()
            self.tray_icon.set_from_icon_name(icon_name)
            self.tray_icon.set_tooltip_text("Vboard - Virtual Keyboard")
            self.tray_icon.connect("activate", self.on_statusicon_activate)
            self.tray_icon.connect("popup-menu", self.on_statusicon_popup_menu)
            self.tray_menu = self.build_tray_menu()
            print("Using Gtk.StatusIcon for system tray.")
            return True
        except Exception as exc:
            self.clear_tray_icon(
                f"Warning: Could not create Gtk.StatusIcon tray icon ({exc})."
            )
            return False

    def clear_tray_icon(self, warning=None):
        if self.tray_icon is not None and hasattr(self.tray_icon, "unregister"):
            self.tray_icon.unregister()
        self.tray_icon = None
        self.tray_menu = None
        self.tray_toggle_item = None
        self.tray_prediction_item = None
        self.tray_gesture_item = None
        self.tray_visual_feedback_item = None
        self.tray_start_minimized_item = None
        self.tray_layout_items = {}
        if warning:
            print(warning)

    def build_tray_menu(self):
        tray_menu = Gtk.Menu()
        self.tray_toggle_item = Gtk.MenuItem(label="Hide")
        self.tray_toggle_item.connect("activate", self.on_tray_toggle)
        tray_menu.append(self.tray_toggle_item)

        self.tray_prediction_item = Gtk.CheckMenuItem(label="Text Prediction")
        self.tray_prediction_item.connect("toggled", self.on_tray_prediction_toggled)
        tray_menu.append(self.tray_prediction_item)

        self.tray_gesture_item = Gtk.CheckMenuItem(
            label="Touch Typing (requires app restart)"
        )
        self.tray_gesture_item.connect("toggled", self.on_tray_gesture_toggled)
        tray_menu.append(self.tray_gesture_item)

        self.tray_visual_feedback_item = Gtk.CheckMenuItem(label="Visual Feedback")
        self.tray_visual_feedback_item.connect(
            "toggled", self.on_tray_visual_feedback_toggled
        )
        tray_menu.append(self.tray_visual_feedback_item)

        self.tray_start_minimized_item = Gtk.CheckMenuItem(label="Start Minimized")
        self.tray_start_minimized_item.connect(
            "toggled", self.on_tray_start_minimized_toggled
        )
        tray_menu.append(self.tray_start_minimized_item)

        tray_menu.append(Gtk.SeparatorMenuItem())

        layout_item = Gtk.MenuItem(label="Keyboard Layout")
        layout_menu = Gtk.Menu()
        self.tray_layout_items = {}
        first_layout_item = None
        for layout_key, layout_label in self.keyboard_layout_choices:
            if first_layout_item is None:
                item = Gtk.RadioMenuItem.new_with_label(None, layout_label)
                first_layout_item = item
            else:
                item = Gtk.RadioMenuItem.new_with_label_from_widget(
                    first_layout_item,
                    layout_label,
                )
            item.connect("toggled", self.on_tray_layout_toggled, layout_key)
            layout_menu.append(item)
            self.tray_layout_items[layout_key] = item
        layout_item.set_submenu(layout_menu)
        tray_menu.append(layout_item)

        tray_menu.append(Gtk.SeparatorMenuItem())

        about_item = Gtk.MenuItem(label="About")
        about_item.connect("activate", self.on_tray_about)
        tray_menu.append(about_item)

        report_bugs_item = Gtk.MenuItem(label="Report bugs")
        report_bugs_item.connect("activate", self.on_report_bugs)
        tray_menu.append(report_bugs_item)

        quit_item = Gtk.MenuItem(label="Quit")
        quit_item.connect("activate", self.on_tray_quit)
        tray_menu.append(quit_item)

        tray_menu.show_all()
        self.sync_tray_items()
        return tray_menu

    def update_tray_menu(self):
        if self.tray_toggle_item is None:
            if hasattr(self.tray_icon, "emit_menu_updated"):
                self.tray_icon.emit_menu_updated()
            return

        self.tray_toggle_item.set_label("Hide" if self.get_visible() else "Show")
        if hasattr(self.tray_icon, "emit_menu_updated"):
            self.tray_icon.emit_menu_updated()

    def toggle_visibility(self):
        if self.get_visible():
            self.set_header_controls_visible(False)
            self.hide()
        else:
            self.show_all()
            self.set_header_controls_visible(False)
            self.present()
            self.request_keep_above()
        self.update_tray_menu()

    def on_tray_activate(self, icon):
        self.toggle_visibility()

    def on_statusicon_activate(self, widget):
        self.on_tray_activate(widget)

    def on_statusicon_popup_menu(self, widget, button, activate_time):
        self.popup_tray_menu(widget, button, activate_time)

    def popup_tray_menu_at_coordinates(self, x, y):
        if self.tray_menu:
            root_window = Gdk.get_default_root_window()
            if root_window is not None:
                rect = Gdk.Rectangle()
                rect.x = x
                rect.y = y
                rect.width = 1
                rect.height = 1
                self.tray_menu.popup_at_rect(
                    root_window,
                    rect,
                    Gdk.Gravity.SOUTH_EAST,
                    Gdk.Gravity.NORTH_WEST,
                    None,
                )
            else:
                self.tray_menu.popup_at_pointer(None)
        return False

    def popup_tray_menu(self, widget, button, activate_time):
        if self.tray_menu:
            self.tray_menu.popup(None, None, widget.position_menu, button, activate_time)

    def on_tray_toggle(self, widget):
        self.on_tray_activate(None)

    def on_tray_prediction_toggled(self, widget):
        if not self._syncing_tray_items:
            self.set_text_prediction_enabled(widget.get_active())

    def on_tray_gesture_toggled(self, widget):
        if self._syncing_tray_items:
            return
        if widget.get_active():
            self.enable_gesture_typing()
        else:
            self.disable_gesture_typing()

    def on_tray_visual_feedback_toggled(self, widget):
        if not self._syncing_tray_items:
            self.set_gesture_visual_feedback_enabled(widget.get_active())

    def on_tray_start_minimized_toggled(self, widget):
        if not self._syncing_tray_items:
            self.set_start_minimized(widget.get_active())

    def on_tray_layout_toggled(self, widget, layout_key):
        if not self._syncing_tray_items and widget.get_active():
            self.set_keyboard_layout(layout_key)

    def sync_tray_items(self):
        self._syncing_tray_items = True
        try:
            if self.tray_prediction_item is not None:
                self.tray_prediction_item.set_active(self.text_prediction_enabled)
            if self.tray_gesture_item is not None:
                self.tray_gesture_item.set_active(self.gesture_enabled)
            if self.tray_visual_feedback_item is not None:
                self.tray_visual_feedback_item.set_active(
                    self.gesture_visual_feedback_enabled
                )
                self.tray_visual_feedback_item.set_sensitive(self.gesture_enabled)
            if self.tray_start_minimized_item is not None:
                self.tray_start_minimized_item.set_active(self.start_minimized)
            for layout_key, item in self.tray_layout_items.items():
                item.set_active(layout_key == self.keyboard_layout)
        finally:
            self._syncing_tray_items = False
        if hasattr(self.tray_icon, "emit_menu_updated"):
            self.tray_icon.emit_menu_updated()

    def normalize_keyboard_layout(self, layout_key):
        if layout_key in self.keyboard_layouts:
            return layout_key
        return get_default_layout_key(self.keyboard_layouts)

    def get_layout_config(self):
        return self.keyboard_layouts[self.keyboard_layout]

    def get_active_key_rows(self):
        rows = [list(row) for row in self.get_layout_config()["rows"]]
        if rows and all(LAYOUT_SWITCH_KEY not in row for row in rows):
            rows[-1].insert(0, LAYOUT_SWITCH_KEY)

        if len(rows) < 5:
            return rows

        navigation_column = max(self.get_row_width(row) for row in rows[:3])
        down_column = self.get_key_column(rows[-1], "↓")
        if down_column is not None and down_column < navigation_column:
            self.insert_spacer_before(
                rows[-1],
                "←",
                navigation_column - down_column,
            )
            down_column = self.get_key_column(rows[-1], "↓")

        up_row = next((row for row in rows if "↑" in row), None)
        if up_row is not None and down_column is not None:
            up_column = self.get_key_column(up_row, "↑")
            if up_column is not None and up_column < down_column:
                self.insert_spacer_before(up_row, "↑", down_column - up_column)

        for row, navigation_keys in zip(rows[:3], NAVIGATION_ROW_KEYS):
            row_width = self.get_row_width(row)
            if row_width < navigation_column:
                row.append(self.make_spacer_key(navigation_column - row_width))
            row.extend(navigation_keys)
        return rows

    @staticmethod
    def make_spacer_key(width):
        return f"{SPACER_KEY_PREFIX}{width}"

    @staticmethod
    def is_spacer_key(key_event):
        return key_event.startswith(SPACER_KEY_PREFIX)

    @classmethod
    def get_key_width(cls, key_event):
        if cls.is_spacer_key(key_event):
            try:
                return max(1, int(key_event[len(SPACER_KEY_PREFIX) :]))
            except ValueError:
                return 1
        return KEY_WIDTHS.get(key_event, 2)

    @classmethod
    def get_row_width(cls, row):
        return sum(cls.get_key_width(key_event) for key_event in row)

    @classmethod
    def get_key_column(cls, row, wanted_key):
        column = 0
        for key_event in row:
            if key_event == wanted_key:
                return column
            column += cls.get_key_width(key_event)
        return None

    @classmethod
    def insert_spacer_before(cls, row, wanted_key, width):
        if width <= 0:
            return
        try:
            key_index = row.index(wanted_key)
        except ValueError:
            return
        row.insert(key_index, cls.make_spacer_key(width))

    def get_active_key_labels(self):
        return self.get_layout_config()["labels"]

    def get_active_shifted_map(self):
        return self.get_layout_config()["shifted"]

    def sync_caps_lock_from_system(self, keymap=None, connect=False):
        try:
            keymap = keymap or Gdk.Keymap.get_default()
            if keymap is None or not hasattr(keymap, "get_caps_lock_state"):
                return
            self.set_caps_lock_active(
                bool(keymap.get_caps_lock_state()),
                update_system=False,
            )
            if connect:
                keymap.connect("state-changed", self.sync_caps_lock_from_system)
        except (AttributeError, TypeError, RuntimeError):
            return

    def refresh_layout_character_lookup(self):
        lookup = {}
        key_labels = self.get_active_key_labels()
        shifted_map = self.get_active_shifted_map()

        for row in self.get_active_key_rows():
            for key_event in row:
                if key_event in MODIFIER_KEYS:
                    continue

                key_label = key_labels.get(key_event, key_event)
                if len(key_label) == 1:
                    if key_label.isalpha():
                        lookup[key_label.lower()] = (key_event, False)
                        lookup[key_label.upper()] = (key_event, True)
                    else:
                        lookup[key_label] = (key_event, False)

                shifted_label = shifted_map.get(key_event)
                if shifted_label is not None:
                    lookup[shifted_label] = (key_event, True)

        self.layout_character_lookup = lookup

    def rebuild_keyboard_grid(self):
        for child in self.grid.get_children():
            self.grid.remove(child)

        self.key_buttons = {}
        self.modifier_buttons = {}
        for row_index, keys in enumerate(self.get_active_key_rows()):
            self.create_row(self.grid, row_index, keys)

        self.grid.show_all()
        self.update_suggestion_bar_scale()

    def initialize_plasma_layout_sync(self):
        if not is_kde_environment():
            return

        try:
            controller = PlasmaLayoutController(self.on_plasma_layout_changed)
            current_layout = controller.get_current_vboard_layout()
        except (GLib.Error, OSError, RuntimeError) as exc:
            print(f"Warning: Could not connect to Plasma keyboard layouts ({exc}).")
            return

        self.plasma_layout_controller = controller
        if current_layout in self.keyboard_layouts:
            self.keyboard_layout = current_layout

    def on_plasma_layout_changed(self, layout_key):
        if layout_key in self.keyboard_layouts:
            self.set_keyboard_layout(layout_key, sync_system=False)

    def get_quick_layout_choices(self):
        available_layouts = self.keyboard_layouts.keys()
        if self.plasma_layout_controller is not None:
            available_layouts = (
                layout
                for layout in self.plasma_layout_controller.get_available_vboard_layouts()
                if layout in self.keyboard_layouts
            )
        return tuple(available_layouts)

    def switch_to_next_keyboard_layout(self):
        next_layout = get_next_quick_layout(
            self.keyboard_layout,
            self.get_quick_layout_choices(),
        )
        if next_layout is not None:
            self.set_keyboard_layout(next_layout)

    def set_keyboard_layout(self, layout_key, sync_system=True):
        normalized_layout = self.normalize_keyboard_layout(layout_key)
        if sync_system and self.plasma_layout_controller is not None:
            if not self.plasma_layout_controller.set_vboard_layout(normalized_layout):
                print(
                    "Warning: Layout is not available in Plasma: "
                    f"{normalized_layout}"
                )
                return
        if normalized_layout == self.keyboard_layout:
            return

        self.keyboard_layout = normalized_layout
        self.suggestion_engine.set_layout(normalized_layout)
        self.refresh_layout_character_lookup()
        self.rebuild_keyboard_grid()
        if self.gesture_controller is not None:
            self.gesture_controller.refresh_layout_cache()
            self.gesture_controller.queue_overlay_draw()

        self.clear_suggestion_override(update=False)
        self.current_word = ""
        self.update_suggestions()
        if self.text_prediction_enabled:
            GLib.idle_add(self.preload_suggestions)
        self.sync_tray_items()

        self.save_settings()

    def sync_gesture_controls(self):
        if (
            self.settings_gesture_check is not None
            and self.settings_gesture_check.get_active() != self.gesture_enabled
        ):
            self.settings_gesture_check.set_active(self.gesture_enabled)
        self.sync_tray_items()

    def sync_visual_feedback_controls(self):
        if self.settings_visual_feedback_check is not None:
            self.settings_visual_feedback_check.set_sensitive(self.gesture_enabled)
            if (
                self.settings_visual_feedback_check.get_active()
                != self.gesture_visual_feedback_enabled
            ):
                self.settings_visual_feedback_check.set_active(
                    self.gesture_visual_feedback_enabled
                )
        self.sync_tray_items()

    def set_gesture_visual_feedback_enabled(self, enabled, sync_controls=True):
        self.gesture_visual_feedback_enabled = bool(enabled)
        if self.gesture_controller is not None:
            self.gesture_controller.set_visual_feedback_enabled(
                self.gesture_visual_feedback_enabled
            )
        if sync_controls:
            self.sync_visual_feedback_controls()
        self.save_settings()

    def enable_gesture_typing(self, sync_controls=True, save=True):
        if self.gesture_controller is None:
            gesture_module = importlib.import_module(f"{__package__}.gesture")
            self.gesture_controller = gesture_module.GestureTypingController(
                self,
                self.grid_overlay,
            )
            self.gesture_controller.refresh_layout_cache()
            self.gesture_controller.queue_overlay_draw()
        self.gesture_controller.set_visual_feedback_enabled(
            self.gesture_visual_feedback_enabled
        )

        self.gesture_enabled = True
        if sync_controls:
            self.sync_gesture_controls()
            self.sync_visual_feedback_controls()
        if save:
            self.save_settings()

    def disable_gesture_typing(self, sync_controls=True, save=True):
        had_gesture_commit = (
            self.gesture_controller is not None and self.gesture_controller.has_committed_text()
        )

        if self.gesture_controller is not None:
            self.gesture_controller.destroy()
            self.gesture_controller = None

        self.gesture_enabled = False
        if had_gesture_commit:
            self.suggestion_override = None
            self.update_suggestions()

        sys.modules.pop(f"{__package__}.gesture", None)
        if sync_controls:
            self.sync_gesture_controls()
            self.sync_visual_feedback_controls()
        if save:
            self.save_settings()

    def on_tray_about(self, widget):
        about_dialog = Gtk.AboutDialog()
        about_dialog.set_modal(True)
        about_dialog.set_program_name(APP_DISPLAY_NAME)
        about_dialog.set_version(VERSION)
        about_dialog.set_comments(
            "A lightweight virtual keyboard for GNU/Linux with Wayland support.\n\n"
            "Originally created by mdev588. The original project was archived, "
            "and it is now maintained by Archisman Panigrahi.\n\n"
            "Original project: https://github.com/mdev588/vboard\n"
            "Special thanks to honjow for the icon and patches.\n"
            "Thanks to Yavuz Kagan Yadigar for the enhanced theme inspiration.\n"
            "Thanks to onboard developers for the droid theme inspiration.\n"
            "Thanks to the Hunspell project for the suggestion engine.\n"
            "This project is licensed under GPLv3."
        )
        about_dialog.set_copyright(
            "Copyright © 2025 mdev588\n"
            "Copyright © 2026 Archisman Panigrahi"
        )
        about_dialog.set_website("https://github.com/archisman-panigrahi/vboard")
        about_dialog.set_website_label("Homepage")
        about_dialog.set_logo_icon_name(self.get_app_icon_name())
        about_dialog.run()
        about_dialog.destroy()

    def on_tray_quit(self, widget):
        self.exiting = True
        self.save_settings()
        self.clear_tray_icon()
        self.destroy()

    def on_report_bugs(self, widget=None):
        self.open_bug_report_url()

    def open_bug_report_url(self):
        Gio.AppInfo.launch_default_for_uri(BUG_REPORT_URL, None)

    def on_delete_event(self, widget, event):
        if self.exiting:
            return False
        if self.tray_icon is None:
            return False
        self.save_settings()
        self.set_header_controls_visible(False)
        self.hide()
        self.update_tray_menu()
        return True

    def create_settings(self):
        self.header_key_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=0,
        )
        self.header_key_box.set_name("header-key-box")
        self.header.pack_start(self.header_key_box)

        self.esc_button = Gtk.Button(label="ESC")
        self.esc_button.connect("clicked", lambda widget: self.emit_key("Esc"))
        self.esc_button.set_name("esc-button")
        self.register_header_button(self.esc_button)
        self.header_key_box.pack_start(self.esc_button, False, False, 0)

        self.function_buttons = []
        for function_key in FUNCTION_KEYS:
            button = Gtk.Button(label=function_key)
            button.set_name("function-button")
            button.connect(
                "clicked",
                lambda widget, key=function_key: self.emit_key(key),
            )
            self.register_header_button(button)
            self.header_key_box.pack_start(button, False, False, 0)
            self.function_buttons.append(button)

        self.header_end_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=0,
        )
        self.header_end_box.set_name("header-end-box")
        self.header.pack_end(self.header_end_box)

        self.close_button = Gtk.Button(label="×")
        self.close_button.set_name("header-close-button")
        self.close_button.set_tooltip_text("Close")
        self.close_button.connect("clicked", lambda widget: self.close())
        self.register_header_button(self.close_button)
        self.header_end_box.pack_end(self.close_button, False, False, 0)

        self.create_button("☰", self.change_visibility, callbacks=1)
        self.create_button(
            "Options",
            self.open_settings_dialog,
            callbacks=1,
        )
        self.create_button("+", self.change_opacity, True, 2)
        self.create_button("-", self.change_opacity, False, 2)
        self.create_button(f"{self.opacity}")
        self.color_combobox.append_text("Change Background")
        self.color_combobox.connect("changed", self.change_color)
        self.color_combobox.set_name("combobox")
        self.color_combobox.set_no_show_all(True)
        self.header_end_box.pack_end(self.color_combobox, False, False, 0)

        for label, _color in COLOR_CHOICES:
            self.color_combobox.append_text(label)

        if self.style_variant == "onboard":
            active_label = "Onboard Droid Theme"
        else:
            active_label = None

        if self.style_variant == "enhanced":
            for label, color in COLOR_CHOICES:
                if (
                    isinstance(color, tuple)
                    and len(color) == 2
                    and color[0] == ENHANCED_BACKGROUND_PRESET
                    and color[1] == self.bg_color
                ):
                    active_label = label
                    break
        elif active_label is None:
            for label, color in COLOR_CHOICES:
                if color == self.bg_color:
                    active_label = label
                    break

        active_index = 0
        if active_label is not None:
            for index, (label, _color) in enumerate(COLOR_CHOICES, start=1):
                if label == active_label:
                    active_index = index
                    break

        self.color_combobox.set_active(active_index)
        self.set_header_controls_visible(False)

    def open_settings_dialog(self, widget=None):
        if self.settings_dialog is not None:
            self.settings_dialog.present()
            return

        dialog = Gtk.Dialog(
            title="Options for Vboard",
            transient_for=self,
            modal=True,
        )
        dialog.add_button("Close", Gtk.ResponseType.CLOSE)
        dialog.connect("response", self.on_settings_dialog_response)
        dialog.connect("destroy", self.on_settings_dialog_destroy)

        content = dialog.get_content_area()
        content.set_border_width(12)
        grid = Gtk.Grid(column_spacing=12, row_spacing=10)
        content.add(grid)

        prediction_check = Gtk.CheckButton(label="Text Prediction")
        prediction_check.set_active(self.text_prediction_enabled)
        prediction_check.connect("toggled", self.on_settings_prediction_toggled)
        grid.attach(prediction_check, 0, 0, 2, 1)

        gesture_check = Gtk.CheckButton(
            label="Touch Typing (requires app restart)"
        )
        gesture_check.set_active(self.gesture_enabled)
        gesture_check.connect("toggled", self.on_settings_gesture_toggled)
        grid.attach(gesture_check, 0, 1, 2, 1)
        self.settings_gesture_check = gesture_check

        visual_feedback_check = Gtk.CheckButton(label="Visual Feedback")
        visual_feedback_check.set_active(self.gesture_visual_feedback_enabled)
        visual_feedback_check.set_sensitive(self.gesture_enabled)
        visual_feedback_check.connect(
            "toggled", self.on_settings_visual_feedback_toggled
        )
        grid.attach(visual_feedback_check, 0, 2, 2, 1)
        self.settings_visual_feedback_check = visual_feedback_check

        start_minimized_check = Gtk.CheckButton(label="Start Minimized")
        start_minimized_check.set_active(self.start_minimized)
        start_minimized_check.connect(
            "toggled", self.on_settings_start_minimized_toggled
        )
        grid.attach(start_minimized_check, 0, 3, 2, 1)

        layout_label = Gtk.Label(label="Keyboard Layout", xalign=0)
        layout_combo = Gtk.ComboBoxText()
        for layout_key, layout_name in self.keyboard_layout_choices:
            layout_combo.append(layout_key, layout_name)
        layout_combo.set_active_id(self.keyboard_layout)
        layout_combo.connect("changed", self.on_settings_layout_changed)
        grid.attach(layout_label, 0, 4, 1, 1)
        grid.attach(layout_combo, 1, 4, 1, 1)

        about_button = Gtk.Button(label="About")
        about_button.connect("clicked", self.on_settings_about_clicked)
        report_bugs_button = Gtk.Button(label="Report bugs")
        report_bugs_button.connect("clicked", self.on_settings_report_bugs_clicked)
        quit_button = Gtk.Button(label="Quit")
        quit_button.connect("clicked", self.on_settings_quit_clicked)
        grid.attach(about_button, 0, 5, 1, 1)
        grid.attach(report_bugs_button, 1, 5, 1, 1)
        grid.attach(quit_button, 2, 5, 1, 1)

        self.settings_dialog = dialog
        dialog.show_all()

    def on_settings_dialog_response(self, dialog, response_id):
        dialog.destroy()

    def on_settings_dialog_destroy(self, dialog):
        self.settings_dialog = None
        self.settings_gesture_check = None
        self.settings_visual_feedback_check = None

    def on_settings_prediction_toggled(self, widget):
        self.set_text_prediction_enabled(widget.get_active())

    def on_settings_gesture_toggled(self, widget):
        if widget.get_active():
            self.enable_gesture_typing()
        else:
            self.disable_gesture_typing()
        if self.settings_visual_feedback_check is not None:
            self.settings_visual_feedback_check.set_sensitive(self.gesture_enabled)

    def on_settings_visual_feedback_toggled(self, widget):
        self.set_gesture_visual_feedback_enabled(widget.get_active())

    def on_settings_start_minimized_toggled(self, widget):
        self.set_start_minimized(widget.get_active())

    def on_settings_layout_changed(self, widget):
        layout_key = widget.get_active_id()
        if layout_key is not None:
            self.set_keyboard_layout(layout_key)

    def on_settings_about_clicked(self, widget):
        self.on_tray_about(widget)

    def on_settings_report_bugs_clicked(self, widget):
        self.open_bug_report_url()

    def on_settings_quit_clicked(self, widget):
        self.on_tray_quit(widget)

    def create_suggestion_buttons(self):
        for _ in range(SUGGESTION_LIMIT):
            button = Gtk.Button()
            button.set_name("suggestion-button")
            button.set_label(" ")
            button.set_sensitive(False)
            button.connect("clicked", self.on_suggestion_clicked)
            self.suggestion_bar.pack_start(button, True, True, 0)
            self.suggestion_buttons.append(button)

    def update_suggestion_bar_visibility(self):
        self.suggestion_revealer.set_reveal_child(self.text_prediction_enabled)
        if self.text_prediction_enabled:
            self.suggestion_revealer.show()
            self.suggestion_bar.show_all()
        else:
            self.suggestion_revealer.hide()
        self._last_suggestion_scale = None
        self.update_suggestion_bar_scale()

    def set_text_prediction_enabled(self, enabled):
        enabled = bool(enabled)
        if enabled == self.text_prediction_enabled:
            return

        self.text_prediction_enabled = enabled
        self.current_word = ""
        self.clear_suggestion_override(update=False)
        self.update_suggestion_bar_visibility()
        self.update_suggestions()
        if self.text_prediction_enabled:
            GLib.idle_add(self.preload_suggestions)
        self.sync_tray_items()

        self.save_settings()

    def set_start_minimized(self, enabled):
        enabled = bool(enabled)
        if enabled == self.start_minimized:
            return

        self.start_minimized = enabled
        self.sync_tray_items()
        self.save_settings()

    def preload_suggestions(self):
        self.suggestion_engine.ensure_loaded()
        return False

    def on_resize(self, widget, event):
        self.width, self.height = self.get_size()
        x, y = self.get_position()
        if x > 0 and y > 0:
            self.pos_x, self.pos_y = x, y
        if self.gesture_controller is not None:
            self.gesture_controller.refresh_layout_cache()
        self.update_suggestion_bar_scale()

    def on_grid_size_allocate(self, widget, allocation):
        if self.gesture_controller is not None:
            self.gesture_controller.refresh_layout_cache()
            self.gesture_controller.queue_overlay_draw()
        self.update_suggestion_bar_scale()

    def update_suggestion_bar_scale(self):
        if not self.text_prediction_enabled:
            return False

        grid_height = self.grid.get_allocated_height() if hasattr(self, "grid") else 0
        if grid_height <= 0:
            return False

        row_height = grid_height / max(1, len(self.get_active_key_rows()))
        scale = row_height / self.BASE_KEY_HEIGHT
        suggestion_height = max(24, int(round(self.BASE_SUGGESTION_HEIGHT * scale)))
        suggestion_font_size = max(10, int(round(self.BASE_SUGGESTION_FONT_SIZE * scale)))
        spacing = max(1, int(round(self.BASE_SUGGESTION_SPACING * scale)))
        margin = max(1, int(round(self.BASE_SUGGESTION_MARGIN * scale)))
        margin_bottom = max(0, int(round(self.BASE_SUGGESTION_MARGIN_BOTTOM * scale)))
        scale_values = (
            suggestion_height,
            suggestion_font_size,
            spacing,
            margin,
            margin_bottom,
        )

        if scale_values == self._last_suggestion_scale:
            return False

        self._last_suggestion_scale = scale_values
        self.suggestion_font_size = suggestion_font_size
        self.suggestion_bar.set_spacing(spacing)
        self.suggestion_bar.set_margin_start(margin)
        self.suggestion_bar.set_margin_end(margin)
        self.suggestion_bar.set_margin_top(margin)
        self.suggestion_bar.set_margin_bottom(margin_bottom)

        for button in self.suggestion_buttons:
            button.set_size_request(-1, suggestion_height)

        self.apply_css()
        return False

    def on_map_keep_above(self, widget, event):
        self.request_keep_above()
        self._keep_above_retries = 30
        if self._keep_above_timer_id is None:
            self._keep_above_timer_id = GLib.timeout_add(500, self.keep_above_tick)
        return False

    def request_keep_above(self):
        self.set_keep_above(True)
        self.stick()

    def keep_above_tick(self):
        self.request_keep_above()
        self._keep_above_retries -= 1
        if self._keep_above_retries <= 0:
            self._keep_above_timer_id = None
            return False
        return True

    def on_window_state_changed(self, widget, event):
        self.request_keep_above()
        return False

    def create_button(
        self,
        label_="",
        callback=None,
        callback2=None,
        callbacks=0,
        hide_with_menu=True,
    ):
        button = Gtk.Button(label=label_)
        button.set_name("headbar-button")
        if callbacks == 1:
            button.connect("clicked", callback)
        elif callbacks == 2:
            button.connect("clicked", callback, callback2)

        if label_ == self.opacity:
            self.opacity_btn = button
            self.opacity_btn.set_tooltip_text("opacity")

        button.get_style_context().add_class("header-button")
        self.register_header_button(button)
        self.header_end_box.pack_end(button, False, False, 0)
        if hide_with_menu:
            self.buttons.append(button)
            if label_ != "☰":
                button.set_no_show_all(True)
        return button

    def register_header_button(self, button):
        button.set_can_focus(False)
        button.set_focus_on_click(False)
        button.connect_after("clicked", self.on_header_button_clicked)
        self.header_buttons.append(button)

    def on_header_button_clicked(self, widget):
        GLib.idle_add(self.clear_header_button_visual_states)

    def clear_header_button_visual_states(self):
        stale_flags = (
            Gtk.StateFlags.ACTIVE
            | Gtk.StateFlags.PRELIGHT
            | Gtk.StateFlags.FOCUSED
        )
        for button in self.header_buttons:
            button.unset_state_flags(stale_flags)
        return False

    def change_visibility(self, widget=None):
        self.set_header_controls_visible(not self.header_controls_visible)

    def set_header_controls_visible(self, visible):
        self.header_controls_visible = bool(visible)
        for button in self.function_buttons:
            button.set_visible(not self.header_controls_visible)
        for button in self.buttons:
            if button.get_label() != "☰":
                button.set_visible(self.header_controls_visible)
        self.color_combobox.set_visible(self.header_controls_visible)

    def change_color(self, widget):
        selected_label = self.color_combobox.get_active_text()
        selected_color = self.color_map.get(selected_label)
        if selected_color is not None:
            if selected_color == ONBOARD_BACKGROUND_PRESET:
                self.style_variant = "onboard"
            elif (
                isinstance(selected_color, tuple)
                and len(selected_color) == 2
                and selected_color[0] == ENHANCED_BACKGROUND_PRESET
            ):
                self.style_variant = "enhanced"
                self.bg_color = selected_color[1]
            else:
                self.style_variant = "classic"
                self.bg_color = selected_color

        if self.bg_color in LIGHT_BACKGROUND_COLORS:
            self.text_color = "#1C1C1C"
        else:
            self.text_color = "white"
        self.apply_css()

    def change_opacity(self, widget, increase_opacity):
        if increase_opacity:
            self.opacity = str(round(min(1.0, float(self.opacity) + 0.01), 2))
        else:
            self.opacity = str(round(max(0.0, float(self.opacity) - 0.01), 2))
        self.opacity_btn.set_label(f"{self.opacity}")
        self.apply_css()

    def apply_css(self):
        gnome_specific = ""
        if "GNOME" in DESKTOP_ENV:
            gnome_specific = "background-image: none;"
        theme_opacity = max(0.0, min(1.0, float(self.opacity)))
        command_modifier_rgb = (
            (0, 0, 0)
            if self.style_variant == "classic" and self.bg_color == "255,0,0"
            else (194, 40, 40)
        )

        def rgba(rgb_values, alpha_scale=1.0):
            red, green, blue = rgb_values
            alpha = max(0.0, min(1.0, theme_opacity * alpha_scale))
            return f"rgba({red}, {green}, {blue}, {alpha:.3f})"

        def parse_rgb_value(value):
            try:
                parts = [int(component.strip()) for component in value.split(",")]
                if len(parts) == 3:
                    return tuple(max(0, min(255, component)) for component in parts)
            except (AttributeError, ValueError):
                pass
            return (0, 0, 0)

        def adjust_rgb(rgb_values, amount):
            return tuple(max(0, min(255, component + amount)) for component in rgb_values)

        def rgb_css(rgb_values):
            return f"{rgb_values[0]}, {rgb_values[1]}, {rgb_values[2]}"

        def luminance(rgb_values):
            red, green, blue = rgb_values
            return 0.299 * red + 0.587 * green + 0.114 * blue

        def contrast_text_rgb(rgb_values):
            return (28, 28, 28) if luminance(rgb_values) >= 128 else (255, 255, 255)

        def accent_color(rgb_values):
            red, green, blue = rgb_values
            maximum = max(rgb_values)
            minimum = min(rgb_values)
            if maximum == 0 or (maximum - minimum) / maximum < 0.25:
                return "#000000" if luminance(rgb_values) >= 128 else "#FFFFFF"

            color_range = maximum - minimum
            if maximum == red:
                hue = ((green - blue) / color_range) % 6
            elif maximum == green:
                hue = (blue - red) / color_range + 2
            else:
                hue = (red - green) / color_range + 4
            hue /= 6.0

            sector = int(hue * 6)
            fraction = hue * 6 - sector
            palette = (
                (1, fraction, 0),
                (1 - fraction, 1, 0),
                (0, 1, fraction),
                (0, 1 - fraction, 1),
                (fraction, 0, 1),
                (1, 0, 1 - fraction),
            )
            accent_rgb = palette[sector % 6]
            return "#{:02X}{:02X}{:02X}".format(
                int(accent_rgb[0] * 255),
                int(accent_rgb[1] * 255),
                int(accent_rgb[2] * 255),
            )

        if self.style_variant == "onboard":
            css = f"""
            #vboard-main {{
                background-color: {rgba((18, 24, 33), 1.0)};
                background-image: linear-gradient(
                    to bottom,
                    {rgba((28, 35, 46), 1.0)},
                    {rgba((18, 24, 33), 1.0)}
                );
                border: 1px solid {rgba((7, 11, 18), 0.95)};
                border-radius: 16px;
                color: {rgba((239, 243, 250), 1.0)};
            }}

            #vboard-main headerbar {{
                background-color: {rgba((31, 39, 53), 0.96)};
                background-image: linear-gradient(
                    to bottom,
                    {rgba((52, 61, 78), 0.96)},
                    {rgba((31, 39, 53), 0.96)}
                );
                border: 0px;
                border-bottom: 1px solid {rgba((8, 12, 19), 0.9)};
                box-shadow: none;
                padding: 3px 4px;
            }}

            #vboard-main headerbar button {{
                min-width: 36px;
                min-height: 34px;
                padding: 0px;
                border: 1px solid {rgba((13, 21, 33), 1.0)};
                border-radius: 8px;
                margin: 0px 1px;
                color: {rgba((239, 243, 250), 1.0)};
                background-color: {rgba((38, 49, 66), 1.0)};
                background-image: linear-gradient(
                    to bottom,
                    {rgba((69, 80, 101), 1.0)},
                    {rgba((40, 50, 68), 1.0)}
                );
                box-shadow: inset 0 1px {rgba((255, 255, 255), 0.08)};
                {gnome_specific};
            }}

            #vboard-main headerbar .titlebutton {{
                min-width: 36px;
                min-height: 34px;
            }}

            #vboard-main headerbar .title {{
                min-width: 0px;
                padding: 0px;
            }}

            #vboard-main headerbar button:hover,
            #vboard-main #combobox button.combo:hover {{
                background-image: linear-gradient(
                    to bottom,
                    {rgba((81, 94, 118), 1.0)},
                    {rgba((49, 59, 79), 1.0)}
                );
            }}

            #vboard-main headerbar button:active,
            #vboard-main #combobox button.combo:active {{
                background-image: linear-gradient(
                    to bottom,
                    {rgba((41, 51, 68), 1.0)},
                    {rgba((75, 87, 112), 1.0)}
                );
            }}

            #vboard-main headerbar button label {{
                color: {rgba((239, 243, 250), 1.0)};
            }}

            #vboard-main headerbar .title {{
                color: {rgba((239, 243, 250), 0.72)};
                font-weight: 600;
            }}

            #vboard-main #headbar-button,
            #vboard-main #combobox button.combo {{
                background-color: {rgba((38, 49, 66), 1.0)};
            }}

            #vboard-main #grid button label {{
                color: {rgba((244, 247, 251), 1.0)};
                font-size: 19px;
                font-weight: 500;
            }}

            #vboard-main #grid button {{
                min-width: 10px;
                min-height: 52px;
                border: 1px solid {rgba((12, 20, 32), 1.0)};
                border-radius: 8px;
                background-color: {rgba((48, 58, 76), 1.0)};
                background-image: linear-gradient(
                    to bottom,
                    {rgba((75, 86, 109), 1.0)},
                    {rgba((42, 51, 69), 1.0)}
                );
                padding: 1px;
                margin: 1px;
                box-shadow:
                    inset 0 1px {rgba((255, 255, 255), 0.09)},
                    inset 0 -1px {rgba((0, 0, 0), 0.18)},
                    0 1px 2px {rgba((0, 0, 0), 0.25)};
            }}

            #vboard-main button {{
                color: {rgba((239, 243, 250), 1.0)};
            }}

            #vboard-main #grid button:hover {{
                border: 1px solid {rgba((110, 126, 151), 1.0)};
                background-image: linear-gradient(
                    to bottom,
                    {rgba((86, 98, 123), 1.0)},
                    {rgba((50, 60, 81), 1.0)}
                );
            }}

            #vboard-main #grid button:active,
            #vboard-main #grid button:active:hover {{
                border: 1px solid {rgba((141, 164, 196), 1.0)};
                background-image: linear-gradient(
                    to bottom,
                    {rgba((39, 48, 63), 1.0)},
                    {rgba((70, 81, 106), 1.0)}
                );
            }}

            #vboard-main #grid button.active-modifier {{
                border: 1px solid {rgba((138, 163, 200), 1.0)};
                background-image: linear-gradient(
                    to bottom,
                    {rgba((96, 112, 141), 1.0)},
                    {rgba((55, 69, 90), 1.0)}
                );
                {gnome_specific};
            }}

            #vboard-main #grid button.active-command-modifier {{
                border: 1px solid {rgba(command_modifier_rgb, 1.0)};
                color: {rgba((247, 248, 251), 1.0)};
                background-color: {rgba(command_modifier_rgb, 1.0)};
                background-image: linear-gradient(
                    to bottom,
                    {rgba(command_modifier_rgb, 0.92)},
                    {rgba(command_modifier_rgb, 0.72)}
                );
                {gnome_specific};
            }}

            #vboard-main #grid button.active-command-modifier label {{
                color: {rgba((247, 248, 251), 1.0)};
            }}

            #vboard-main #esc-button {{
                min-width: 52px;
                min-height: 34px;
                border: 1px solid {rgba((17, 24, 36), 1.0)};
                border-radius: 8px;
                color: {rgba((247, 248, 251), 1.0)};
                background-color: {rgba((51, 64, 89), 1.0)};
                background-image: linear-gradient(
                    to bottom,
                    {rgba((86, 98, 123), 1.0)},
                    {rgba((48, 58, 78), 1.0)}
                );
                box-shadow: inset 0 1px {rgba((255, 255, 255), 0.1)};
            }}

            #vboard-main #esc-button:hover {{
                border: 1px solid {rgba((142, 166, 199), 1.0)};
                background-image: linear-gradient(
                    to bottom,
                    {rgba((97, 112, 139), 1.0)},
                    {rgba((54, 65, 86), 1.0)}
                );
            }}

            #vboard-main #function-button {{
                min-width: 36px;
                min-height: 34px;
                font-size: 13px;
            }}

            #vboard-main #header-close-button {{
                min-width: 36px;
                min-height: 34px;
                font-size: 18px;
            }}

            #vboard-main tooltip {{
                color: white;
                padding: 5px;
            }}

            #vboard-main #combobox button.combo {{
                color: {rgba((239, 243, 250), 1.0)};
                padding: 5px;
                border: 1px solid {rgba((13, 21, 33), 1.0)};
                border-radius: 8px;
                background-image: linear-gradient(
                    to bottom,
                    {rgba((69, 80, 101), 1.0)},
                    {rgba((40, 50, 68), 1.0)}
                );
            }}

            #vboard-main #suggestion-bar {{
                background-color: transparent;
            }}

            #vboard-main #suggestion-button {{
                border: 1px solid {rgba((17, 25, 37), 1.0)};
                border-radius: 8px;
                background-color: {rgba((32, 41, 56), 1.0)};
                background-image: linear-gradient(
                    to bottom,
                    {rgba((51, 64, 85), 1.0)},
                    {rgba((32, 41, 56), 1.0)}
                );
                min-height: 0px;
                padding: 2px 8px;
                box-shadow: inset 0 1px {rgba((255, 255, 255), 0.06)};
            }}

            #vboard-main #suggestion-button label,
            #vboard-main #suggestion-button:disabled label {{
                color: {rgba((216, 223, 234), 1.0)};
                font-size: {self.suggestion_font_size}px;
            }}

            #vboard-main #suggestion-button.has-suggestion {{
                border: 1px solid {rgba((37, 49, 68), 1.0)};
            }}

            #vboard-main #suggestion-button.has-suggestion:hover {{
                border: 1px solid {rgba((115, 130, 154), 1.0)};
                background-image: linear-gradient(
                    to bottom,
                    {rgba((59, 73, 96), 1.0)},
                    {rgba((38, 49, 68), 1.0)}
                );
            }}
            """
        elif self.style_variant == "enhanced":
            base_rgb = parse_rgb_value(self.bg_color)
            window_rgb = adjust_rgb(base_rgb, -40)
            header_rgb = adjust_rgb(base_rgb, -18)
            key_rgb = adjust_rgb(base_rgb, 30)
            hover_rgb = adjust_rgb(base_rgb, 48)
            pressed_rgb = adjust_rgb(base_rgb, 78)
            suggestion_rgb = adjust_rgb(base_rgb, 18)
            text_rgb = contrast_text_rgb(key_rgb)
            accent = accent_color(base_rgb)
            css = f"""
            #vboard-main {{
                background-color: {rgba(window_rgb, 1.0)};
                color: rgb({rgb_css(text_rgb)});
            }}

            #vboard-main headerbar {{
                background-color: {rgba(header_rgb, 1.0)};
                border: 0px;
                box-shadow: none;
                padding: 3px 4px;
            }}

            #vboard-main headerbar button {{
                min-width: 36px;
                min-height: 34px;
                padding: 0px;
                border: 1px solid transparent;
                border-radius: 6px;
                margin: 0px 1px;
                color: rgb({rgb_css(text_rgb)});
                background-color: transparent;
                background-image: none;
                {gnome_specific};
            }}

            #vboard-main headerbar .titlebutton {{
                min-width: 36px;
                min-height: 34px;
            }}

            #vboard-main headerbar .title {{
                min-width: 0px;
                padding: 0px;
            }}

            #vboard-main headerbar button:hover,
            #vboard-main #combobox button.combo:hover {{
                border: 1px solid {accent};
                background-color: {rgba(key_rgb, 0.85)};
                background-image: none;
            }}

            #vboard-main headerbar button:active,
            #vboard-main #combobox button.combo:active {{
                border: 1px solid rgb({rgb_css(text_rgb)});
                background-color: {rgba(pressed_rgb, 1.0)};
                background-image: none;
            }}

            #vboard-main headerbar button label,
            #vboard-main headerbar .title {{
                color: rgb({rgb_css(text_rgb)});
            }}

            #vboard-main #headbar-button,
            #vboard-main #combobox button.combo {{
                background-image: none;
            }}

            #vboard-main #grid button label {{
                color: rgb({rgb_css(text_rgb)});
                font-size: 19px;
                font-weight: 500;
            }}

            #vboard-main #grid button {{
                min-width: 10px;
                min-height: 52px;
                border: 1px solid transparent;
                border-radius: 7px;
                background-color: {rgba(key_rgb, 1.0)};
                background-image: none;
                padding: 1px;
                margin: 2px;
                {gnome_specific};
            }}

            #vboard-main button {{
                background-color: transparent;
                color: rgb({rgb_css(text_rgb)});
            }}

            #vboard-main #grid button:hover {{
                border: 1px solid {accent};
                background-color: {rgba(hover_rgb, 1.0)};
            }}

            #vboard-main #grid button:active,
            #vboard-main #grid button:active:hover {{
                border: 1px solid rgb({rgb_css(text_rgb)});
                background-color: {rgba(pressed_rgb, 1.0)};
            }}

            #vboard-main #grid button.active-modifier {{
                border: 1px solid {accent};
                background-color: {rgba(pressed_rgb, 1.0)};
                {gnome_specific};
            }}

            #vboard-main #grid button.active-command-modifier {{
                border: 1px solid {rgba(command_modifier_rgb, 1.0)};
                color: white;
                background-color: {rgba(command_modifier_rgb, 1.0)};
                background-image: none;
                {gnome_specific};
            }}

            #vboard-main #grid button.active-command-modifier label {{
                color: white;
            }}

            #vboard-main #esc-button {{
                min-width: 52px;
                min-height: 34px;
                border: 1px solid transparent;
                border-radius: 6px;
                color: rgb({rgb_css(text_rgb)});
                background-color: {rgba(key_rgb, 1.0)};
                background-image: none;
            }}

            #vboard-main #esc-button:hover {{
                border: 1px solid {accent};
                background-color: {rgba(hover_rgb, 1.0)};
            }}

            #vboard-main #function-button {{
                min-width: 36px;
                min-height: 34px;
                font-size: 13px;
            }}

            #vboard-main #header-close-button {{
                min-width: 36px;
                min-height: 34px;
                font-size: 18px;
            }}

            #vboard-main tooltip {{
                color: white;
                padding: 5px;
            }}

            #vboard-main #combobox button.combo {{
                color: rgb({rgb_css(text_rgb)});
                padding: 5px;
                border: 1px solid transparent;
                border-radius: 6px;
                background-color: transparent;
                background-image: none;
            }}

            #vboard-main #suggestion-bar {{
                background-color: transparent;
            }}

            #vboard-main #suggestion-button {{
                border: 1px solid transparent;
                border-radius: 6px;
                background-color: {rgba(suggestion_rgb, 1.0)};
                background-image: none;
                min-height: 0px;
                padding: 2px 8px;
            }}

            #vboard-main #suggestion-button label,
            #vboard-main #suggestion-button:disabled label {{
                color: rgb({rgb_css(text_rgb)});
                font-size: {self.suggestion_font_size}px;
            }}

            #vboard-main #suggestion-button.has-suggestion {{
                border: 1px solid rgb({rgb_css(text_rgb)});
            }}

            #vboard-main #suggestion-button.has-suggestion:hover {{
                border: 1px solid {accent};
                background-color: {rgba(hover_rgb, 1.0)};
            }}
            """
        else:
            css = f"""
            #vboard-main {{
                background-color: rgba({self.bg_color}, {self.opacity});
            }}

            #vboard-main headerbar {{
                background-color: rgba({self.bg_color}, {self.opacity});
                border: 0px;
                box-shadow: none;
                padding: 3px 4px;
            }}

            #vboard-main headerbar button {{
                min-width: 36px;
                min-height: 34px;
                padding: 0px;
                border: 0px;
                margin: 0px 1px;
                {gnome_specific}
            }}

            #vboard-main headerbar .titlebutton {{
                min-width: 36px;
                min-height: 34px;
            }}

            #vboard-main headerbar .title {{
                min-width: 0px;
                padding: 0px;
            }}

            #vboard-main headerbar button label {{
                color: {self.text_color};
            }}

            #vboard-main #headbar-button,
            #vboard-main #combobox button.combo {{
                background-image: none;
            }}

            #vboard-main #grid button label {{
                color: {self.text_color};
            }}

            #vboard-main #grid button {{
                min-width: 10px;
                border: 1px solid {self.text_color};
                background-image: none;
                padding: 1px;
                margin: 1px;
            }}

            #vboard-main button {{
                background-color: transparent;
                color: {self.text_color};
            }}

            #vboard-main #grid button:hover {{
                border: 1px solid #00CACB;
            }}

            #vboard-main #grid button.pressed,
            #vboard-main #grid button.pressed:hover {{
                border: 1px solid {self.text_color};
            }}

            #vboard-main #grid button.active-modifier {{
                border: 1px solid #00CACB;
                {gnome_specific}
            }}

            #vboard-main #grid button.active-command-modifier {{
                border: 1px solid rgb{command_modifier_rgb};
                color: white;
                background-color: {rgba(command_modifier_rgb, 1.0)};
                background-image: none;
                {gnome_specific}
            }}

            #vboard-main #grid button.active-command-modifier label {{
                color: white;
            }}

            #vboard-main #esc-button {{
                min-width: 52px;
                min-height: 34px;
                border: 1px solid {self.text_color};
                background-image: none;
            }}

            #vboard-main #esc-button:hover {{
                border: 1px solid #00CACB;
            }}

            #vboard-main #function-button {{
                min-width: 36px;
                min-height: 34px;
                font-size: 13px;
            }}

            #vboard-main #header-close-button {{
                min-width: 36px;
                min-height: 34px;
                font-size: 18px;
            }}

            #vboard-main tooltip {{
                color: white;
                padding: 5px;
            }}

            #vboard-main #combobox button.combo {{
                color: {self.text_color};
                padding: 5px;
            }}

            #vboard-main #suggestion-bar {{
                background-color: transparent;
            }}

            #vboard-main #suggestion-button {{
                border: 1px solid transparent;
                background-image: none;
                min-height: 0px;
                padding: 2px 8px;
            }}

            #vboard-main #suggestion-button label,
            #vboard-main #suggestion-button:disabled label {{
                color: {self.text_color};
                font-size: {self.suggestion_font_size}px;
            }}

            #vboard-main #suggestion-button.has-suggestion {{
                border: 1px solid {self.text_color};
            }}

            #vboard-main #suggestion-button.has-suggestion:hover {{
                border: 1px solid #00CACB;
            }}
            """

        try:
            self.css_provider.load_from_data(css.encode("utf-8"))
        except GLib.GError as exc:
            print(f"CSS Error: {exc.message}")
            return

        screen = self.get_screen()
        if screen is not None and not self._css_provider_registered:
            Gtk.StyleContext.add_provider_for_screen(
                screen,
                self.css_provider,
                Gtk.STYLE_PROVIDER_PRIORITY_USER,
            )
            self._css_provider_registered = True

    def create_row(self, grid, row_index, keys):
        col = 0

        for key_event in keys:
            width = self.get_key_width(key_event)
            if self.is_spacer_key(key_event):
                spacer = Gtk.Box()
                spacer.set_sensitive(False)
                grid.attach(spacer, col, row_index, width, 1)
                col += width
                continue

            button = Gtk.Button(label=self.get_button_label(key_event))
            button.set_can_focus(False)
            button.set_focus_on_click(False)
            button.add_events(
                Gdk.EventMask.BUTTON_PRESS_MASK
                | Gdk.EventMask.BUTTON_RELEASE_MASK
                | Gdk.EventMask.POINTER_MOTION_MASK
                | Gdk.EventMask.LEAVE_NOTIFY_MASK
            )
            button.connect("button-press-event", self.on_key_button_press_event, key_event)
            button.connect("motion-notify-event", self.on_key_button_motion_event, key_event)
            button.connect("button-release-event", self.on_key_button_release_event, key_event)
            button.connect("leave-notify-event", self.on_key_button_leave_notify_event)
            if key_event == LAYOUT_SWITCH_KEY:
                button.set_tooltip_text("Switch between Ukrainian and English")
            self.key_buttons[key_event] = button
            if key_event in self.modifiers:
                self.modifier_buttons[key_event] = button

            grid.attach(button, col, row_index, width, 1)
            col += width

    def get_button_label(self, key_event):
        if key_event == LAYOUT_SWITCH_KEY:
            return "UA/EN"

        navigation_labels = {
            "Delete": "Del",
            "PageUp": "PgUp",
            "PageDown": "PgDn",
        }
        if key_event in navigation_labels:
            return navigation_labels[key_event]

        if key_event == "CapsLock":
            return "Caps"

        if key_event in MODIFIER_KEYS:
            return key_event[:-2]

        key_labels = self.get_active_key_labels()
        shifted_map = self.get_active_shifted_map()
        shift_active = self.modifiers["Shift_L"] or self.modifiers["Shift_R"]
        key_label = key_labels.get(key_event, key_event)

        if len(key_label) == 1 and key_label.isalpha():
            uppercase_active = shift_active != self.caps_lock_active
            return key_label.upper() if uppercase_active else key_label.lower()

        if shift_active and key_event in shifted_map:
            return shifted_map[key_event]

        return key_label

    def update_key_labels(self):
        for key_label, button in self.key_buttons.items():
            button.set_label(self.get_button_label(key_label))

    def update_modifier(self, key_event, value):
        self.modifiers[key_event] = value
        button = self.modifier_buttons[key_event]
        style_context = button.get_style_context()
        modifier_class = (
            "active-command-modifier"
            if key_event.startswith(("Shift", "Ctrl", "Alt"))
            else "active-modifier"
        )
        style_context.remove_class("active-modifier")
        style_context.remove_class("active-command-modifier")
        if value:
            style_context.add_class(modifier_class)

    def set_caps_lock_active(self, active, update_system=True):
        active = bool(active)
        if update_system and active != self.caps_lock_active:
            empty_modifiers = {modifier: False for modifier in MODIFIER_KEYS}
            if self.gesture_controller is not None:
                self.gesture_controller.note_non_gesture_key()
            self.backend.emit_key("CapsLock", empty_modifiers)

        if active == self.caps_lock_active:
            return

        self.caps_lock_active = active
        button = self.key_buttons.get("CapsLock")
        if button is not None:
            style_context = button.get_style_context()
            style_context.remove_class("active-modifier")
            style_context.remove_class("active-command-modifier")
            if active:
                style_context.add_class("active-command-modifier")
        self.update_key_labels()

    def toggle_caps_lock(self):
        self.set_caps_lock_active(not self.caps_lock_active)
        self.current_word = ""
        self.update_suggestions()

    def on_key_button_press_event(self, widget, event, key_event):
        if event.type in (Gdk.EventType._2BUTTON_PRESS, Gdk.EventType._3BUTTON_PRESS):
            return True

        self.stop_key_repeat()
        self.clear_key_button_visual_states(except_button=widget)
        self.clear_suggestion_override(update=False)

        if event.button == 3:
            if key_event not in self.modifiers:
                self.emit_shifted_key(key_event)
            return True

        if event.button != 1:
            return False

        if key_event == "CapsLock":
            self.toggle_caps_lock()
            self.reset_modifiers()
            return False

        if key_event == LAYOUT_SWITCH_KEY:
            self.switch_to_next_keyboard_layout()
            self.reset_modifiers()
            return False

        if key_event in self.modifiers:
            self.update_modifier(key_event, not self.modifiers[key_event])

            if self.modifiers["Shift_L"] and self.modifiers["Shift_R"]:
                self.update_modifier("Shift_L", False)
                self.update_modifier("Shift_R", False)

            self.update_key_labels()
            return False

        if self.gesture_controller is not None and self.gesture_controller.handle_key_press(
            widget,
            event,
            key_event,
        ):
            return False

        self.emit_key(key_event)
        self.delay_source = GLib.timeout_add(400, self.start_repeat, key_event)
        return False

    def on_key_button_motion_event(self, widget, event, key_event):
        if self.gesture_controller is not None:
            self.gesture_controller.handle_key_motion(widget, event)
        return False

    def on_key_button_release_event(self, widget, event, key_event):
        self.schedule_key_button_visual_reset()
        if event.button != 1:
            return False

        if self.gesture_controller is not None and self.gesture_controller.handle_key_release(
            widget,
            event,
            key_event,
        ):
            return False

        self.stop_key_repeat()
        return False

    def on_key_button_leave_notify_event(self, widget, event):
        widget.unset_state_flags(Gtk.StateFlags.ACTIVE | Gtk.StateFlags.PRELIGHT)
        return False

    def on_window_button_release_event(self, widget, event):
        self.schedule_key_button_visual_reset()
        return False

    def on_window_leave_notify_event(self, widget, event):
        self.schedule_key_button_visual_reset()
        return False

    def schedule_key_button_visual_reset(self):
        GLib.idle_add(self.clear_key_button_visual_states)

    def clear_key_button_visual_states(self, except_button=None):
        stale_flags = (
            Gtk.StateFlags.ACTIVE
            | Gtk.StateFlags.PRELIGHT
            | Gtk.StateFlags.FOCUSED
        )
        for button in self.key_buttons.values():
            if button is except_button:
                continue
            button.unset_state_flags(stale_flags)
        return False

    def stop_key_repeat(self):
        if hasattr(self, "delay_source"):
            GLib.source_remove(self.delay_source)
            del self.delay_source
        if hasattr(self, "repeat_source"):
            GLib.source_remove(self.repeat_source)
            del self.repeat_source

    def start_repeat(self, key_event):
        self.repeat_source = GLib.timeout_add(100, self.repeat_key, key_event)
        return False

    def repeat_key(self, key_event):
        self.emit_key(key_event)
        return True

    def emit_shifted_key(self, key_event):
        modifiers = dict(self.modifiers)
        modifiers["Shift_L"] = True
        self.emit_key(key_event, modifiers)

    def emit_key(self, key_event, modifiers=None):
        active_modifiers = self.modifiers if modifiers is None else modifiers
        if self.gesture_controller is not None:
            self.gesture_controller.note_non_gesture_key()
        self.track_current_word(key_event, active_modifiers)
        self.backend.emit_key(key_event, active_modifiers)
        self.reset_modifiers()

    def emit_text(self, text):
        for char in text:
            key_event, modifiers = self.character_to_key_event(char)
            if key_event is None:
                continue
            self.backend.emit_key(key_event, modifiers)

    def reset_modifiers(self):
        for mod_key, active in self.modifiers.items():
            if active:
                self.update_modifier(mod_key, False)
        self.update_key_labels()

    def clear_suggestion_override(self, update=False):
        has_gesture_commit = (
            self.gesture_controller is not None and self.gesture_controller.has_committed_text()
        )
        if self.suggestion_override is None and not has_gesture_commit:
            return

        self.suggestion_override = None
        if self.gesture_controller is not None:
            self.gesture_controller.clear_committed_text()
        if update:
            self.update_suggestions()

    def track_current_word(self, key_event, modifiers=None):
        active_modifiers = self.modifiers if modifiers is None else modifiers
        self.clear_suggestion_override(update=False)

        if not self.text_prediction_enabled:
            self.current_word = ""
            return

        if self.has_active_command_modifier(active_modifiers):
            self.current_word = ""
            self.update_suggestions()
            return

        if key_event == "Backspace":
            self.current_word = self.current_word[:-1]
            self.update_suggestions()
            return

        if key_event in {
            "Space",
            "Tab",
            "Enter",
            "Esc",
            "CapsLock",
            "←",
            "→",
            "↑",
            "↓",
            *NAVIGATION_KEYS,
        }:
            self.current_word = ""
            self.update_suggestions()
            return

        typed_char = self.key_event_to_character(key_event, active_modifiers)
        if typed_char and all(
            char.isalpha() or char in SUPPORTED_WORD_CONNECTORS
            for char in typed_char
        ):
            self.current_word += typed_char
        else:
            self.current_word = ""

        self.update_suggestions()

    def has_active_command_modifier(self, modifiers=None):
        active_modifiers = self.modifiers if modifiers is None else modifiers
        return any(active_modifiers[modifier] for modifier in COMMAND_MODIFIER_KEYS)

    def key_event_to_character(self, key_event, modifiers=None):
        active_modifiers = self.modifiers if modifiers is None else modifiers
        shift_active = active_modifiers["Shift_L"] or active_modifiers["Shift_R"]
        key_labels = self.get_active_key_labels()
        shifted_map = self.get_active_shifted_map()
        key_label = key_labels.get(key_event, key_event)

        if len(key_label) == 1 and key_label.isalpha():
            uppercase_active = shift_active != self.caps_lock_active
            return key_label.upper() if uppercase_active else key_label.lower()

        if shift_active and key_event in shifted_map:
            return shifted_map[key_event]

        if len(key_label) == 1:
            return key_label

        return None

    def update_suggestions(self):
        if not self.text_prediction_enabled:
            suggestions = []
        elif self.suggestion_override is not None:
            suggestions = self.suggestion_override
        else:
            suggestions = self.suggestion_engine.get_suggestions(
                self.current_word,
                SUGGESTION_LIMIT,
            )

        for index, button in enumerate(self.suggestion_buttons):
            style_context = button.get_style_context()
            if index < len(suggestions):
                label = suggestions[index]
                if self.suggestion_override is None:
                    label = self.apply_suggestion_case(label)
                button.set_label(label)
                button.set_sensitive(True)
                style_context.add_class("has-suggestion")
            else:
                button.set_label(" ")
                button.set_sensitive(False)
                style_context.remove_class("has-suggestion")
            button.show()

        self.suggestion_revealer.set_reveal_child(self.text_prediction_enabled)

    def apply_suggestion_case(self, suggestion):
        if self.current_word.isupper():
            return suggestion.upper()
        if self.current_word[:1].isupper() and self.current_word[1:].islower():
            return suggestion.capitalize()
        return suggestion

    def on_suggestion_clicked(self, widget):
        suggestion = widget.get_label().strip()
        if not suggestion:
            return

        if (
            self.gesture_controller is not None
            and self.suggestion_override is not None
            and self.gesture_controller.has_committed_text()
        ):
            self.gesture_controller.replace_committed_word(suggestion)
            return

        if not self.current_word:
            return

        completion = suggestion[len(self.current_word):]
        if not completion:
            return

        for modifier in MODIFIER_KEYS:
            if self.modifiers[modifier]:
                self.update_modifier(modifier, False)

        for char in completion:
            key_event, modifiers = self.character_to_key_event(char)
            if key_event is None:
                continue
            self.backend.emit_key(key_event, modifiers)

        self.current_word = suggestion
        self.update_suggestions()

    def character_to_key_event(self, char):
        modifiers = {modifier: False for modifier in MODIFIER_KEYS}

        if char == " ":
            return "Space", modifiers

        key_event_with_shift = self.layout_character_lookup.get(char)
        if key_event_with_shift is not None:
            key_event, needs_shift = key_event_with_shift
            if self.caps_lock_active and char.isalpha():
                needs_shift = not needs_shift
            if needs_shift:
                modifiers["Shift_L"] = True
            return key_event, modifiers

        return None, modifiers

    def read_settings(self):
        try:
            os.makedirs(self.CONFIG_DIR, exist_ok=True)
        except PermissionError:
            print("Warning: No permission to create the config directory. Proceeding without it.")

        try:
            if os.path.exists(self.CONFIG_FILE):
                self.config.read(self.CONFIG_FILE)
                self.bg_color = self.config.get("DEFAULT", "bg_color").replace(" ", "")
                self.opacity = self.config.get("DEFAULT", "opacity")
                self.text_color = self.config.get("DEFAULT", "text_color", fallback="white")
                self.style_variant = self.config.get(
                    "DEFAULT", "style_variant", fallback="classic"
                )
                self.gesture_enabled = self.config.getboolean(
                    "DEFAULT", "gesture_enabled", fallback=True
                )
                self.gesture_visual_feedback_enabled = self.config.getboolean(
                    "DEFAULT",
                    "gesture_visual_feedback_enabled",
                    fallback=True,
                )
                self.text_prediction_enabled = self.config.getboolean(
                    "DEFAULT",
                    "text_prediction_enabled",
                    fallback=True,
                )
                self.start_minimized = self.config.getboolean(
                    "DEFAULT",
                    "start_minimized",
                    fallback=False,
                )
                self.keyboard_layout = self.normalize_keyboard_layout(
                    self.config.get(
                        "DEFAULT",
                        "keyboard_layout",
                        fallback=DEFAULT_KEYBOARD_LAYOUT,
                    )
                )
                self.width = self.config.getint("DEFAULT", "width", fallback=0)
                self.height = self.config.getint("DEFAULT", "height", fallback=0)
                pos_x_str = self.config.get("DEFAULT", "pos_x", fallback="0")
                pos_y_str = self.config.get("DEFAULT", "pos_y", fallback="0")
                try:
                    self.pos_x = int(pos_x_str)
                    self.pos_y = int(pos_y_str)
                    self.config_pos_x = self.pos_x
                    self.config_pos_y = self.pos_y
                except ValueError:
                    self.pos_x = self.config_pos_x = 0
                    self.pos_y = self.config_pos_y = 0

        except configparser.Error as exc:
            print(f"Warning: Could not read config file ({exc}). Using default values.")

    def save_settings(self):
        self.config["DEFAULT"] = {
            "bg_color": self.bg_color,
            "opacity": self.opacity,
            "text_color": self.text_color,
            "style_variant": self.style_variant,
            "text_prediction_enabled": str(self.text_prediction_enabled),
            "start_minimized": str(self.start_minimized),
            "gesture_enabled": str(self.gesture_enabled),
            "gesture_visual_feedback_enabled": str(
                self.gesture_visual_feedback_enabled
            ),
            "keyboard_layout": self.keyboard_layout,
            "width": self.width,
            "height": self.height,
            "pos_x": str(self.pos_x),
            "pos_y": str(self.pos_y),
        }

        try:
            with open(self.CONFIG_FILE, "w") as configfile:
                self.config.write(configfile)
        except (configparser.Error, IOError) as exc:
            print(f"Warning: Could not write to config file ({exc}). Changes will not be saved.")
