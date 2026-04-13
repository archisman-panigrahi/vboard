import configparser
import importlib
import os
import sys

from .constants import (
    APP_DISPLAY_NAME,
    COMMAND_MODIFIER_KEYS,
    COLOR_CHOICES,
    KEY_ROWS,
    KEY_WIDTHS,
    LIGHT_BACKGROUND_COLORS,
    MODIFIER_KEYS,
    ONBOARD_BACKGROUND_PRESET,
    SHIFTED_CHAR_TO_KEY_EVENT,
    SHIFTED_KEY_MAP,
    SUGGESTION_LIMIT,
    SUPPORTED_WORD_CHARS,
    VERSION,
)
from .environment import DESKTOP_ENV
from .gtk import (
    APPINDICATOR_AVAILABLE,
    APPINDICATOR_BACKEND,
    AppIndicator3,
    Gdk,
    GLib,
    Gtk,
)
from .input_backends import NullInputBackend, UInputBackend
from .suggestions import HunspellSuggestionEngine


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

        self.bg_color = "0,0,0"
        self.opacity = "0.90"
        self.text_color = "white"
        self.style_variant = "onboard"
        self.gesture_enabled = True
        self.gesture_visual_feedback_enabled = True
        self.read_settings()

        self.modifiers = {mod_key: False for mod_key in MODIFIER_KEYS}
        self.color_map = dict(COLOR_CHOICES)
        if self.width != 0:
            self.set_default_size(self.width, self.height)

        self.header = Gtk.HeaderBar()
        self.header.set_title(APP_DISPLAY_NAME)
        self.header.set_show_close_button(True)
        self.buttons = []
        self.key_buttons = {}
        self.modifier_buttons = {}
        self.current_word = ""
        self.suggestion_engine = HunspellSuggestionEngine()
        self.suggestion_buttons = []
        self.suggestion_override = None
        self.color_combobox = Gtk.ComboBoxText()
        self.tray_icon = None
        self.tray_menu = None
        self.tray_toggle_item = None
        self.tray_gesture_item = None
        self.tray_visual_feedback_item = None
        self.css_provider = Gtk.CssProvider()
        self._css_provider_registered = False
        self._last_suggestion_scale = None
        self._syncing_gesture_menu_item = False
        self._syncing_visual_feedback_menu_item = False
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
        self.suggestion_revealer.set_reveal_child(True)
        content.pack_start(self.suggestion_revealer, False, False, 0)

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
        GLib.idle_add(self.preload_suggestions)
        GLib.idle_add(self.update_suggestion_bar_scale)

        for row_index, keys in enumerate(KEY_ROWS):
            self.create_row(grid, row_index, keys)

        if self.gesture_enabled:
            self.enable_gesture_typing(sync_menu=False)

    def get_app_icon_name(self):
        icon_theme = Gtk.IconTheme.get_default()
        preferred_icon = "io.github.archisman-panigrahi.vboard"
        fallback_icon = "preferences-desktop-keyboard"
        if icon_theme and icon_theme.has_icon(preferred_icon):
            return preferred_icon
        return fallback_icon

    def create_tray_icon(self):
        icon_name = self.get_app_icon_name()
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

        try:
            self.tray_icon = Gtk.StatusIcon()
            self.tray_icon.set_from_icon_name(icon_name)
            self.tray_icon.set_tooltip_text("Vboard - Virtual Keyboard")
            self.tray_icon.connect("activate", self.on_statusicon_activate)
            self.tray_icon.connect("popup-menu", self.on_statusicon_popup_menu)
            self.tray_menu = self.build_tray_menu()
            print("Using Gtk.StatusIcon for system tray.")
        except Exception as exc:
            self.tray_icon = None
            self.tray_menu = None
            self.tray_toggle_item = None
            self.tray_gesture_item = None
            self.tray_visual_feedback_item = None
            print(f"Warning: Could not create tray icon ({exc}). Tray disabled.")

    def build_tray_menu(self):
        tray_menu = Gtk.Menu()
        self.tray_toggle_item = Gtk.MenuItem(label="Hide")
        self.tray_toggle_item.connect("activate", self.on_tray_toggle)
        tray_menu.append(self.tray_toggle_item)

        self.tray_gesture_item = Gtk.CheckMenuItem(
            label="Touch Typing (requires app restart)"
        )
        self.tray_gesture_item.set_active(self.gesture_enabled)
        self.tray_gesture_item.connect("toggled", self.on_tray_gesture_toggled)
        tray_menu.append(self.tray_gesture_item)

        self.tray_visual_feedback_item = Gtk.CheckMenuItem(label="Visual Feedback")
        self.tray_visual_feedback_item.set_active(self.gesture_visual_feedback_enabled)
        self.tray_visual_feedback_item.set_sensitive(self.gesture_enabled)
        self.tray_visual_feedback_item.connect(
            "toggled", self.on_tray_visual_feedback_toggled
        )
        tray_menu.append(self.tray_visual_feedback_item)

        tray_menu.append(Gtk.SeparatorMenuItem())

        about_item = Gtk.MenuItem(label="About")
        about_item.connect("activate", self.on_tray_about)
        tray_menu.append(about_item)

        quit_item = Gtk.MenuItem(label="Quit")
        quit_item.connect("activate", self.on_tray_quit)
        tray_menu.append(quit_item)
        tray_menu.show_all()
        return tray_menu

    def update_tray_menu(self):
        if self.tray_toggle_item is None:
            return
        if self.get_visible():
            self.tray_toggle_item.set_label("Hide")
        else:
            self.tray_toggle_item.set_label("Show")

    def on_tray_activate(self, icon):
        if self.get_visible():
            self.hide()
        else:
            self.show_all()
            self.present()
            self.request_keep_above()
        self.update_tray_menu()

    def on_statusicon_activate(self, widget):
        self.on_tray_activate(widget)

    def on_statusicon_popup_menu(self, widget, button, activate_time):
        if self.tray_menu:
            self.tray_menu.popup(None, None, widget.position_menu, button, activate_time)

    def on_tray_toggle(self, widget):
        self.on_tray_activate(None)

    def on_tray_gesture_toggled(self, widget):
        if self._syncing_gesture_menu_item:
            return

        if widget.get_active():
            self.enable_gesture_typing()
        else:
            self.disable_gesture_typing()

    def on_tray_visual_feedback_toggled(self, widget):
        if self._syncing_visual_feedback_menu_item:
            return

        self.set_gesture_visual_feedback_enabled(widget.get_active())

    def sync_gesture_menu_item(self):
        if self.tray_gesture_item is None:
            return

        if self.tray_gesture_item.get_active() == self.gesture_enabled:
            return

        self._syncing_gesture_menu_item = True
        self.tray_gesture_item.set_active(self.gesture_enabled)
        self._syncing_gesture_menu_item = False

    def sync_visual_feedback_menu_item(self):
        if self.tray_visual_feedback_item is None:
            return

        self.tray_visual_feedback_item.set_sensitive(self.gesture_enabled)
        if (
            self.tray_visual_feedback_item.get_active()
            == self.gesture_visual_feedback_enabled
        ):
            return

        self._syncing_visual_feedback_menu_item = True
        self.tray_visual_feedback_item.set_active(
            self.gesture_visual_feedback_enabled
        )
        self._syncing_visual_feedback_menu_item = False

    def set_gesture_visual_feedback_enabled(self, enabled, sync_menu=True):
        self.gesture_visual_feedback_enabled = bool(enabled)
        if self.gesture_controller is not None:
            self.gesture_controller.set_visual_feedback_enabled(
                self.gesture_visual_feedback_enabled
            )
        if sync_menu:
            self.sync_visual_feedback_menu_item()

    def enable_gesture_typing(self, sync_menu=True):
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
        if sync_menu:
            self.sync_gesture_menu_item()
            self.sync_visual_feedback_menu_item()

    def disable_gesture_typing(self, sync_menu=True):
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
        if sync_menu:
            self.sync_gesture_menu_item()
            self.sync_visual_feedback_menu_item()

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
        self.destroy()

    def on_delete_event(self, widget, event):
        if self.exiting:
            return False
        if self.tray_icon is None:
            return False
        self.save_settings()
        self.hide()
        self.update_tray_menu()
        return True

    def create_settings(self):
        self.esc_button = Gtk.Button(label="ESC")
        self.esc_button.connect("clicked", lambda widget: self.emit_key("Esc"))
        self.esc_button.set_name("esc-button")
        self.header.pack_start(self.esc_button)

        self.create_button("☰", self.change_visibility, callbacks=1)
        self.create_button("+", self.change_opacity, True, 2)
        self.create_button("-", self.change_opacity, False, 2)
        self.create_button(f"{self.opacity}")
        self.color_combobox.append_text("Change Background")
        self.color_combobox.connect("changed", self.change_color)
        self.color_combobox.set_name("combobox")
        self.header.pack_end(self.color_combobox)

        for label, _color in COLOR_CHOICES:
            self.color_combobox.append_text(label)

        active_label = "Onboard Droid Theme" if self.style_variant == "onboard" else None
        if active_label is None:
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

    def create_suggestion_buttons(self):
        for _ in range(SUGGESTION_LIMIT):
            button = Gtk.Button()
            button.set_name("suggestion-button")
            button.set_label(" ")
            button.set_sensitive(False)
            button.connect("clicked", self.on_suggestion_clicked)
            self.suggestion_bar.pack_start(button, True, True, 0)
            self.suggestion_buttons.append(button)

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
        grid_height = self.grid.get_allocated_height() if hasattr(self, "grid") else 0
        if grid_height <= 0:
            return False

        row_height = grid_height / max(1, len(KEY_ROWS))
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

    def create_button(self, label_="", callback=None, callback2=None, callbacks=0):
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
        self.header.pack_end(button)
        self.buttons.append(button)
        return button

    def change_visibility(self, widget=None):
        for button in self.buttons:
            if button.get_label() != "☰":
                button.set_visible(not button.get_visible())
        self.color_combobox.set_visible(not self.color_combobox.get_visible())

    def change_color(self, widget):
        selected_label = self.color_combobox.get_active_text()
        selected_color = self.color_map.get(selected_label)
        if selected_color is not None:
            if selected_color == ONBOARD_BACKGROUND_PRESET:
                self.style_variant = "onboard"
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

        def rgba(rgb_values, alpha_scale=1.0):
            red, green, blue = rgb_values
            alpha = max(0.0, min(1.0, theme_opacity * alpha_scale))
            return f"rgba({red}, {green}, {blue}, {alpha:.3f})"

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
                padding: 4px 6px;
            }}

            #vboard-main headerbar button {{
                min-width: 40px;
                min-height: 34px;
                padding: 0px;
                border: 1px solid {rgba((13, 21, 33), 1.0)};
                border-radius: 8px;
                margin: 0px 2px;
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
                min-width: 50px;
                min-height: 40px;
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

            #vboard-main #esc-button {{
                min-width: 60px;
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
        else:
            css = f"""
            #vboard-main {{
                background-color: rgba({self.bg_color}, {self.opacity});
            }}

            #vboard-main headerbar {{
                background-color: rgba({self.bg_color}, {self.opacity});
                border: 0px;
                box-shadow: none;
            }}

            #vboard-main headerbar button {{
                min-width: 40px;
                padding: 0px;
                border: 0px;
                margin: 0px;
                {gnome_specific}
            }}

            #vboard-main headerbar .titlebutton {{
                min-width: 50px;
                min-height: 40px;
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

            #vboard-main #esc-button {{
                min-width: 60px;
                border: 1px solid {self.text_color};
                background-image: none;
            }}

            #vboard-main #esc-button:hover {{
                border: 1px solid #00CACB;
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

        for key_label in keys:
            button = Gtk.Button(label=self.get_button_label(key_label))
            button.add_events(
                Gdk.EventMask.BUTTON_PRESS_MASK
                | Gdk.EventMask.BUTTON_RELEASE_MASK
                | Gdk.EventMask.POINTER_MOTION_MASK
            )
            button.connect("button-press-event", self.on_key_button_press_event, key_label)
            button.connect("motion-notify-event", self.on_key_button_motion_event, key_label)
            button.connect("button-release-event", self.on_key_button_release_event, key_label)
            self.key_buttons[key_label] = button
            if key_label in self.modifiers:
                self.modifier_buttons[key_label] = button

            width = KEY_WIDTHS.get(key_label, 2)

            grid.attach(button, col, row_index, width, 1)
            col += width

    def get_button_label(self, key_label):
        if key_label in MODIFIER_KEYS:
            return key_label[:-2]

        shift_active = self.modifiers["Shift_L"] or self.modifiers["Shift_R"]
        if len(key_label) == 1 and key_label.isalpha():
            return key_label if shift_active else key_label.lower()

        if key_label in SHIFTED_KEY_MAP:
            return SHIFTED_KEY_MAP[key_label] if shift_active else key_label

        return key_label

    def update_key_labels(self):
        for key_label, button in self.key_buttons.items():
            button.set_label(self.get_button_label(key_label))

    def update_modifier(self, key_event, value):
        self.modifiers[key_event] = value
        button = self.modifier_buttons[key_event]
        style_context = button.get_style_context()
        if value:
            style_context.add_class("active-modifier")
        else:
            style_context.remove_class("active-modifier")

    def on_key_button_press_event(self, widget, event, key_event):
        if event.button != 1:
            return False

        self.stop_key_repeat()
        self.clear_suggestion_override(update=False)

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

    def emit_key(self, key_event):
        if self.gesture_controller is not None:
            self.gesture_controller.note_non_gesture_key()
        self.track_current_word(key_event)
        self.backend.emit_key(key_event, self.modifiers)
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

    def track_current_word(self, key_event):
        self.clear_suggestion_override(update=False)

        if self.has_active_command_modifier():
            self.current_word = ""
            self.update_suggestions()
            return

        if key_event == "Backspace":
            self.current_word = self.current_word[:-1]
            self.update_suggestions()
            return

        if key_event in {"Space", "Tab", "Enter", "Esc", "CapsLock", "←", "→", "↑", "↓"}:
            self.current_word = ""
            self.update_suggestions()
            return

        typed_char = self.key_event_to_character(key_event)
        if typed_char and all(char in SUPPORTED_WORD_CHARS for char in typed_char):
            self.current_word += typed_char
        else:
            self.current_word = ""

        self.update_suggestions()

    def has_active_command_modifier(self):
        return any(self.modifiers[modifier] for modifier in COMMAND_MODIFIER_KEYS)

    def key_event_to_character(self, key_event):
        shift_active = self.modifiers["Shift_L"] or self.modifiers["Shift_R"]

        if len(key_event) == 1 and key_event.isalpha():
            return key_event if shift_active else key_event.lower()

        if key_event in SHIFTED_KEY_MAP:
            return SHIFTED_KEY_MAP[key_event] if shift_active else key_event

        return None

    def update_suggestions(self):
        if self.suggestion_override is not None:
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

        self.suggestion_revealer.set_reveal_child(True)

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

        if char.isalpha():
            key_event = char.upper()
            if char.isupper():
                modifiers["Shift_L"] = True
            return key_event, modifiers

        shifted_key_event = SHIFTED_CHAR_TO_KEY_EVENT.get(char)
        if shifted_key_event is not None:
            modifiers["Shift_L"] = True
            return shifted_key_event, modifiers

        if char in SHIFTED_KEY_MAP:
            return char, modifiers

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
            "gesture_enabled": str(self.gesture_enabled),
            "gesture_visual_feedback_enabled": str(
                self.gesture_visual_feedback_enabled
            ),
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
