#!/usr/bin/env python3

import bisect
import configparser
import os
import subprocess
import sys

import gi

gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")
from gi.repository import Gio
from gi.repository import GLib
from gi.repository import Gdk
from gi.repository import Gtk

APP_DISPLAY_NAME = "Vboard"
APP_ID = "io.github.archisman-panigrahi.vboard"


def get_desktop_environment():
    desktop_env = os.environ.get("XDG_CURRENT_DESKTOP", "")
    if desktop_env:
        return desktop_env.upper()
    return ""


DESKTOP_ENV = get_desktop_environment()


def is_kde_environment():
    session_hint = " ".join(
        filter(
            None,
            [
                DESKTOP_ENV,
                os.environ.get("DESKTOP_SESSION", ""),
                os.environ.get("KDE_FULL_SESSION", ""),
            ],
        )
    ).upper()
    return "KDE" in session_hint or "PLASMA" in session_hint


def install_kwin_rule_if_needed():
    if not is_kde_environment():
        return

    for script_path in (
        "/usr/share/vboard/scripts/install-kwin-rule.sh",
        "./scripts/install-kwin-rule.sh",
    ):
        if os.path.isfile(script_path):
            try:
                subprocess.run(["bash", script_path], check=False)
            except OSError as exc:
                print(f"Warning: Could not run {script_path}: {exc}")
            return

    print("Warning: Could not find a KWin rule installer script.")

APPINDICATOR_AVAILABLE = False
AppIndicator3 = None
APPINDICATOR_BACKEND = None

try:
    gi.require_version("AyatanaAppIndicator3", "0.1")
    from gi.repository import AyatanaAppIndicator3 as AppIndicator3

    APPINDICATOR_AVAILABLE = True
    APPINDICATOR_BACKEND = "ayatana"
except (ImportError, ValueError):
    try:
        gi.require_version("AppIndicator3", "0.1")
        from gi.repository import AppIndicator3

        APPINDICATOR_AVAILABLE = True
        APPINDICATOR_BACKEND = "appindicator"
    except (ImportError, ValueError):
        APPINDICATOR_AVAILABLE = False
        APPINDICATOR_BACKEND = None

try:
    import uinput
except ImportError:
    uinput = None


MODIFIER_KEYS = [
    "Shift_L",
    "Shift_R",
    "Ctrl_L",
    "Ctrl_R",
    "Alt_L",
    "Alt_R",
    "Super_L",
    "Super_R",
]

KEY_ROWS = [
    ["`", "1", "2", "3", "4", "5", "6", "7", "8", "9", "0", "-", "=", "Backspace"],
    ["Tab", "Q", "W", "E", "R", "T", "Y", "U", "I", "O", "P", "[", "]", "\\"],
    ["CapsLock", "A", "S", "D", "F", "G", "H", "J", "K", "L", ";", "'", "Enter"],
    ["Shift_L", "Z", "X", "C", "V", "B", "N", "M", ",", ".", "/", "Shift_R", "↑"],
    ["Ctrl_L", "Super_L", "Alt_L", "Space", "Alt_R", "Super_R", "Ctrl_R", "←", "↓", "→"],
]

SHIFTED_KEY_MAP = {
    "`": "~",
    "1": "!",
    "2": "@",
    "3": "#",
    "4": "$",
    "5": "%",
    "6": "^",
    "7": "&",
    "8": "*",
    "9": "(",
    "0": ")",
    "-": "_",
    "=": "+",
    "[": "{",
    "]": "}",
    "\\": "|",
    ";": ":",
    "'": '"',
    ",": "<",
    ".": ">",
    "/": "?",
}

SUPPORTED_WORD_CHARS = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'-")
SUGGESTION_LIMIT = 5


class InputBackend:
    name = "unknown"

    def emit_key(self, key_label, modifiers):
        raise NotImplementedError


class UInputBackend(InputBackend):
    name = "uinput"

    def __init__(self):
        if uinput is None:
            raise RuntimeError("python-uinput is not installed")

        self.key_map = {
            "Esc": uinput.KEY_ESC,
            "1": uinput.KEY_1,
            "2": uinput.KEY_2,
            "3": uinput.KEY_3,
            "4": uinput.KEY_4,
            "5": uinput.KEY_5,
            "6": uinput.KEY_6,
            "7": uinput.KEY_7,
            "8": uinput.KEY_8,
            "9": uinput.KEY_9,
            "0": uinput.KEY_0,
            "-": uinput.KEY_MINUS,
            "=": uinput.KEY_EQUAL,
            "Backspace": uinput.KEY_BACKSPACE,
            "Tab": uinput.KEY_TAB,
            "Q": uinput.KEY_Q,
            "W": uinput.KEY_W,
            "E": uinput.KEY_E,
            "R": uinput.KEY_R,
            "T": uinput.KEY_T,
            "Y": uinput.KEY_Y,
            "U": uinput.KEY_U,
            "I": uinput.KEY_I,
            "O": uinput.KEY_O,
            "P": uinput.KEY_P,
            "[": uinput.KEY_LEFTBRACE,
            "]": uinput.KEY_RIGHTBRACE,
            "Enter": uinput.KEY_ENTER,
            "Ctrl_L": uinput.KEY_LEFTCTRL,
            "Ctrl_R": uinput.KEY_RIGHTCTRL,
            "A": uinput.KEY_A,
            "S": uinput.KEY_S,
            "D": uinput.KEY_D,
            "F": uinput.KEY_F,
            "G": uinput.KEY_G,
            "H": uinput.KEY_H,
            "J": uinput.KEY_J,
            "K": uinput.KEY_K,
            "L": uinput.KEY_L,
            ";": uinput.KEY_SEMICOLON,
            "'": uinput.KEY_APOSTROPHE,
            "`": uinput.KEY_GRAVE,
            "Shift_L": uinput.KEY_LEFTSHIFT,
            "Shift_R": uinput.KEY_RIGHTSHIFT,
            "\\": uinput.KEY_BACKSLASH,
            "Z": uinput.KEY_Z,
            "X": uinput.KEY_X,
            "C": uinput.KEY_C,
            "V": uinput.KEY_V,
            "B": uinput.KEY_B,
            "N": uinput.KEY_N,
            "M": uinput.KEY_M,
            ",": uinput.KEY_COMMA,
            ".": uinput.KEY_DOT,
            "/": uinput.KEY_SLASH,
            "Alt_L": uinput.KEY_LEFTALT,
            "Alt_R": uinput.KEY_RIGHTALT,
            "Space": uinput.KEY_SPACE,
            "CapsLock": uinput.KEY_CAPSLOCK,
            "→": uinput.KEY_RIGHT,
            "←": uinput.KEY_LEFT,
            "↓": uinput.KEY_DOWN,
            "↑": uinput.KEY_UP,
            "Super_L": uinput.KEY_LEFTMETA,
            "Super_R": uinput.KEY_RIGHTMETA,
        }

        self.modifier_order = [
            "Shift_L",
            "Shift_R",
            "Ctrl_L",
            "Ctrl_R",
            "Alt_L",
            "Alt_R",
            "Super_L",
            "Super_R",
        ]
        self.device = uinput.Device(list(self.key_map.values()))

    def emit_key(self, key_label, modifiers):
        key_event = self.key_map.get(key_label)
        if key_event is None:
            return

        for mod_key in self.modifier_order:
            if modifiers.get(mod_key, False):
                self.device.emit(self.key_map[mod_key], 1)

        self.device.emit(key_event, 1)
        self.device.emit(key_event, 0)

        for mod_key in self.modifier_order:
            if modifiers.get(mod_key, False):
                self.device.emit(self.key_map[mod_key], 0)


class HunspellSuggestionEngine:
    def __init__(self):
        self.words = []
        self.dictionary_path = None
        self.loaded = False

    def ensure_loaded(self):
        if self.loaded:
            return

        self.loaded = True
        self.dictionary_path = self.find_dictionary_path()
        if self.dictionary_path is None:
            return

        words = set()
        try:
            with open(self.dictionary_path, "r", encoding="utf-8", errors="ignore") as handle:
                for index, line in enumerate(handle):
                    if index == 0 and line.strip().isdigit():
                        continue

                    word = self.parse_dictionary_line(line)
                    if word is not None:
                        words.add(word)
        except OSError as exc:
            print(f"Warning: Could not read Hunspell dictionary ({exc}). Suggestions disabled.")
            self.dictionary_path = None
            return

        self.words = sorted(words)

    def get_suggestions(self, prefix, limit=SUGGESTION_LIMIT):
        self.ensure_loaded()
        prefix = self.normalize_word(prefix)
        if not prefix or not self.words:
            return []

        start_index = bisect.bisect_left(self.words, prefix)
        matches = []
        for word in self.words[start_index:]:
            if not word.startswith(prefix):
                break
            if word == prefix:
                continue
            matches.append(word)
            if len(matches) >= 50:
                break

        matches.sort(key=lambda word: (len(word), word))
        return matches[:limit]

    def find_dictionary_path(self):
        candidates = self.get_dictionary_candidates()
        search_dirs = [
            os.path.expanduser("~/.local/share/hunspell"),
            os.path.expanduser("~/.hunspell"),
            "/usr/share/hunspell",
            "/usr/share/myspell",
            "/usr/share/myspell/dicts",
        ]

        for directory in search_dirs:
            if not os.path.isdir(directory):
                continue

            for candidate in candidates:
                path = os.path.join(directory, f"{candidate}.dic")
                if os.path.isfile(path):
                    return path

        for directory in search_dirs:
            if not os.path.isdir(directory):
                continue

            try:
                for entry in sorted(os.listdir(directory)):
                    if entry.endswith(".dic"):
                        return os.path.join(directory, entry)
            except OSError:
                continue

        return None

    def get_dictionary_candidates(self):
        candidates = []
        for value in (
            os.environ.get("LC_ALL", ""),
            os.environ.get("LC_MESSAGES", ""),
            os.environ.get("LC_CTYPE", ""),
            os.environ.get("LANG", ""),
            os.environ.get("LANGUAGE", ""),
        ):
            for locale_name in value.split(":"):
                locale_name = locale_name.strip()
                if not locale_name:
                    continue

                locale_name = locale_name.split(".", 1)[0]
                locale_name = locale_name.split("@", 1)[0]
                if not locale_name:
                    continue

                candidates.append(locale_name)
                if "_" in locale_name:
                    candidates.append(locale_name.split("_", 1)[0])

        candidates.extend(["en_US", "en_GB", "en"])

        ordered = []
        seen = set()
        for candidate in candidates:
            if candidate not in seen:
                ordered.append(candidate)
                seen.add(candidate)
        return ordered

    def parse_dictionary_line(self, line):
        token = line.strip()
        if not token:
            return None

        token = token.split(maxsplit=1)[0]
        if not token:
            return None

        word_chars = []
        escaped = False
        for char in token:
            if escaped:
                word_chars.append(char)
                escaped = False
                continue
            if char == "\\":
                escaped = True
                continue
            if char == "/":
                break
            word_chars.append(char)

        return self.normalize_word("".join(word_chars))

    def normalize_word(self, word):
        if not word or not word.isascii():
            return None

        normalized = word.strip().lower()
        if len(normalized) < 2:
            return None
        if any(char not in SUPPORTED_WORD_CHARS for char in normalized):
            return None
        if not any(char.isalpha() for char in normalized):
            return None
        return normalized

class VirtualKeyboard(Gtk.Window):
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
        self.set_deletable(True)  # Keep close button
        
        # Remove minimize and maximize buttons while keeping resize handles
        self.set_type_hint(Gdk.WindowTypeHint.DIALOG)
        
        self.connect("delete-event", self.on_delete_event)
        self.connect("map-event", self.on_map_keep_above)
        self.connect("window-state-event", self.on_window_state_changed)
        self._keep_above_retries = 0
        self._keep_above_timer_id = None
        self.width=0
        self.height=0
        self.pos_x = 0
        self.pos_y = 0
        self.config_pos_x = 0
        self.config_pos_y = 0
        self.set_position(Gtk.WindowPosition.NONE)

        self.CONFIG_DIR = os.path.expanduser("~/.config/vboard")
        self.CONFIG_FILE = os.path.join(self.CONFIG_DIR, "settings.conf")
        self.config = configparser.ConfigParser()

        self.bg_color = "0, 0, 0"  # background color
        self.opacity="0.90"
        self.text_color="white"
        self.read_settings()

        self.modifiers = {mod_key: False for mod_key in MODIFIER_KEYS}
        self.colors = [
            ("Black", "0,0,0"),
            ("Red", "255,0,0"),
            ("Pink", "255,105,183"),
            ("White", "255,255,255"),
            ("Green", "0,255,0"),
            ("Blue", "0,0,110"),
            ("Gray", "128,128,128"),
            ("Dark Gray", "64,64,64"),
            ("Orange", "255,165,0"),
            ("Yellow", "255,255,0"),
            ("Purple", "128,0,128"),
            ("Cyan", "0,255,255"),
            ("Teal", "0,128,128"),
            ("Brown", "139,69,19"),
            ("Gold", "255,215,0"),
            ("Silver", "192,192,192"),
            ("Turquoise", "64,224,208"),
            ("Magenta", "255,0,255"),
            ("Olive", "128,128,0"),
            ("Maroon", "128,0,0"),
            ("Indigo", "75,0,130"),
            ("Beige", "245,245,220"),
            ("Lavender", "230,230,250")

        ]
        if (self.width!=0):
            self.set_default_size(self.width, self.height)

        self.header = Gtk.HeaderBar()
        self.header.set_title(APP_DISPLAY_NAME)
        self.header.set_show_close_button(True)
        self.buttons=[]
        self.modifier_buttons={}
        self.row_buttons=[]
        self.current_word = ""
        self.suggestion_engine = HunspellSuggestionEngine()
        self.suggestion_buttons = []
        self.color_combobox = Gtk.ComboBoxText()
        # Set the header bar as the titlebar of the window
        self.set_titlebar(self.header)
        self.set_name("vboard-main")
        self.set_default_icon_name(self.get_app_icon_name())

        self.create_settings()

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

        grid = Gtk.Grid()  # Use Grid for layout
        grid.set_row_homogeneous(True)  # Allow rows to resize based on content
        grid.set_column_homogeneous(True)  # Columns are homogeneous
        grid.set_margin_start(3)
        grid.set_margin_end(3)
        grid.set_name("grid")
        content.pack_start(grid, True, True, 0)
        self.apply_css()
        self.backend = UInputBackend()
        self.create_tray_icon()
        GLib.idle_add(self.preload_suggestions)

        # Define rows for keys
        # Create each row and add it to the grid
        for row_index, keys in enumerate(KEY_ROWS):
            self.create_row(grid, row_index, keys)

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
                # Suppress upstream runtime deprecation spam from libayatana-appindicator.
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

            self.tray_menu = Gtk.Menu()
            self.tray_toggle_item = Gtk.MenuItem(label="Hide")
            self.tray_toggle_item.connect("activate", self.on_tray_toggle)
            self.tray_menu.append(self.tray_toggle_item)

            separator1 = Gtk.SeparatorMenuItem()
            self.tray_menu.append(separator1)

            about_item = Gtk.MenuItem(label="About")
            about_item.connect("activate", self.on_tray_about)
            self.tray_menu.append(about_item)

            quit_item = Gtk.MenuItem(label="Quit")
            quit_item.connect("activate", self.on_tray_quit)
            self.tray_menu.append(quit_item)
            self.tray_menu.show_all()
            self.tray_icon.set_menu(self.tray_menu)
        else:
            # Fallback to Gtk.StatusIcon if appindicator is not available
            try:
                self.tray_icon = Gtk.StatusIcon()
                self.tray_icon.set_from_icon_name(icon_name)
                self.tray_icon.set_tooltip_text("Vboard - Virtual Keyboard")
                self.tray_icon.connect("activate", self.on_statusicon_activate)
                self.tray_icon.connect("popup-menu", self.on_statusicon_popup_menu)

                self.tray_menu = Gtk.Menu()
                self.tray_toggle_item = Gtk.MenuItem(label="Hide")
                self.tray_toggle_item.connect("activate", self.on_tray_toggle)
                self.tray_menu.append(self.tray_toggle_item)

                separator1 = Gtk.SeparatorMenuItem()
                self.tray_menu.append(separator1)

                about_item = Gtk.MenuItem(label="About")
                about_item.connect("activate", self.on_tray_about)
                self.tray_menu.append(about_item)

                quit_item = Gtk.MenuItem(label="Quit")
                quit_item.connect("activate", self.on_tray_quit)
                self.tray_menu.append(quit_item)
                self.tray_menu.show_all()
                print("Using Gtk.StatusIcon for system tray.")
            except Exception as e:
                self.tray_icon = None
                print(f"Warning: Could not create tray icon ({e}). Tray disabled.")

    def update_tray_menu(self):
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
        """Left-click handler for Gtk.StatusIcon."""
        self.on_tray_activate(widget)

    def on_statusicon_popup_menu(self, widget, button, activate_time):
        """Right-click handler for Gtk.StatusIcon to show context menu."""
        if self.tray_menu:
            self.tray_menu.popup(None, None, widget.position_menu, button, activate_time)

    def on_tray_toggle(self, widget):
        self.on_tray_activate(None)

    def on_tray_about(self, widget):
        """Show the About dialog."""
        about_dialog = Gtk.AboutDialog()
        about_dialog.set_modal(True)
        about_dialog.set_program_name("Vboard")
        about_dialog.set_version("1.3")
        about_dialog.set_comments(
            "A lightweight virtual keyboard for Linux and Wayland.\n\n"
            "Originally created by mdev588. The original project was archived, "
            "and it is now maintained by Archisman Panigrahi.\n\n"
            "Icon by honjow.\n\n"
            "Original project: https://github.com/mdev588/vboard\n"
        )
        about_dialog.set_copyright(
            "Copyright © 2025 mdev588\n"
            "Copyright © 2026 Archisman Panigrahi"
        )
        about_dialog.set_website("https://github.com/archisman-panigrahi/vboard")
        about_dialog.set_website_label("Homepage")
        icon_theme = Gtk.IconTheme.get_default()
        preferred_icon = "io.github.archisman-panigrahi.vboard"
        fallback_icon = "preferences-desktop-keyboard"
        if icon_theme and icon_theme.has_icon(preferred_icon):
            about_dialog.set_logo_icon_name(preferred_icon)
        else:
            about_dialog.set_logo_icon_name(fallback_icon)
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

        self.create_button("☰", self.change_visibility,callbacks=1)
        self.create_button("+", self.change_opacity,True,2)
        self.create_button("-", self.change_opacity, False,2)
        self.create_button(f"{self.opacity}")
        self.color_combobox.append_text("Change Background")
        self.color_combobox.set_active(0)
        self.color_combobox.connect("changed", self.change_color)
        self.color_combobox.set_name("combobox")
        self.header.pack_end(self.color_combobox)


        for label, color in self.colors:
            self.color_combobox.append_text(label)

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
        self.width, self.height = self.get_size()  # Get the current size after resize
        x, y = self.get_position()
        if x > 0 and y > 0:
            self.pos_x, self.pos_y = x, y

    def on_map_keep_above(self, widget, event):
        # Reapply hints when mapped since some compositors ignore initial requests.
        self.request_keep_above()
        # Keep requesting for a short period so compositors that defer placement
        # still receive repeated keep-above requests.
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
        button= Gtk.Button(label=label_)
        button.set_name("headbar-button")
        if callbacks==1:
            button.connect("clicked", callback)
        elif callbacks==2:
            button.connect("clicked", callback, callback2)

        if label_==self.opacity:
            self.opacity_btn=button
            self.opacity_btn.set_tooltip_text("opacity")

        button.get_style_context().add_class("header-button")
        self.header.pack_end(button)
        self.buttons.append(button)
        return button

    def change_visibility(self, widget=None):
        for button in self.buttons:
            if button.get_label() != "☰" and button.get_name() != "esc-button":
                button.set_visible(not button.get_visible())
        self.color_combobox.set_visible(not self.color_combobox.get_visible() )

    def change_color (self, widget):
        label=self.color_combobox.get_active_text()
        for label_ , color_ in self.colors:
            if label_==label:
                self.bg_color = color_

        if (self.bg_color in {"255,255,255" ,"0,255,0" , "255,255,0", "245,245,220", "230,230,250", "255,215,0"}):
            self.text_color="#1C1C1C"
        else:
            self.text_color="white"
        self.apply_css()


    def change_opacity(self,widget, boolean):
        if (boolean):
            self.opacity = str(round(min(1.0, float(self.opacity) + 0.01),2))
        else:
            self.opacity = str(round(max(0.0, float(self.opacity) - 0.01),2))
        self.opacity_btn.set_label(f"{self.opacity}")
        self.apply_css()
    def apply_css (self):
        provider = Gtk.CssProvider()

        gnome_specific = ""
        if "GNOME" in DESKTOP_ENV:
            gnome_specific = "background-image: none;"


        css = f"""
        #vboard-main {{
            background-color: rgba({self.bg_color}, {self.opacity});
        }}

        #vboard-main headerbar {{
            background-color: rgba({self.bg_color}, {self.opacity});
            border: 0px;
            box-shadow: none;

        }}

        #vboard-main headerbar button{{
            min-width: 40px;
            padding: 0px;
            border: 0px;
            margin: 0px;
            {gnome_specific}
            


        }}

        #vboard-main headerbar .titlebutton {{
            min-width: 50px;  /* Set custom min-width for the close button */
            min-height: 40px
        }}

        #vboard-main headerbar button label{{
        color: {self.text_color};

        }}

        #vboard-main #headbar-button,
        #vboard-main #combobox button.combo {{
            background-image: none;
        }}

        #vboard-main #grid button label{{
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
            color:{self.text_color};

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

       #vboard-main #combobox button.combo  {{

            color: {self.text_color};
            padding: 5px;
        }}

       #vboard-main #suggestion-bar {{
            background-color: transparent;
       }}

       #vboard-main #suggestion-button {{
          border: 1px solid transparent;
            background-image: none;
            min-height: 34px;
            padding: 2px 8px;
       }}

      #vboard-main #suggestion-button.has-suggestion {{
          border: 1px solid {self.text_color};
      }}

      #vboard-main #suggestion-button.has-suggestion:hover {{
            border: 1px solid #00CACB;
       }}


        """


        try:
            provider.load_from_data(css.encode("utf-8"))
        except GLib.GError as e:
            print(f"CSS Error: {e.message}")
        # Scope custom styling to the main window only.
        Gtk.StyleContext.add_provider_for_screen(self.get_screen(), provider, Gtk.STYLE_PROVIDER_PRIORITY_USER)

    def create_row(self, grid, row_index, keys):
        col = 0  # Start from the first column
        width=0


        for key_label in keys:
            if key_label in ("Shift_R", "Shift_L", "Alt_L", "Alt_R", "Ctrl_L", "Ctrl_R", "Super_L", "Super_R"):
                button = Gtk.Button(label=key_label[:-2])
            else:
                button = Gtk.Button(label=key_label)
            button.connect("pressed", self.on_button_press, key_label)
            button.connect("released", self.on_button_release)
            button.connect("leave-notify-event", self.on_button_release)
            self.row_buttons.append(button)
            if key_label in self.modifiers:
                self.modifier_buttons[key_label] = button
            if key_label == "Space": width=12
            elif key_label == "CapsLock": width=3
            elif key_label == "Shift_R" : width=2
            elif key_label == "Shift_L" : width=4
            elif key_label == "Backspace": width=5
            elif key_label == "`": width=1
            elif key_label == "\\" : width=4
            elif key_label == "Enter": width=5
            else: width=2

            grid.attach(button, col, row_index, width, 1)
            col += width  # Skip 4 columns for the space button

    def update_label(self, show_symbols):
        button_positions = [(0, "` ~"), (1, "1 !"), (2, "2 @"), (3, "3 #"), (4, "4 $"), (5, "5 %"), (6, "6 ^"), (7, "7 &"), (8, "8 *"), (9, "9 ("), (10, "0 )")
        , (11, "- _"), (12, "= +"),(25,"[ {"), (26,"] }"), (27,"\\ |"), (38, "; :"), (39, "' \""), (49, ", <"), (50, ". >"), (51, "/ ?")]

        for pos, label in button_positions:
            label_parts = label.split()  
            if show_symbols:
                self.row_buttons[pos].set_label(label_parts[1])
            else:
                self.row_buttons[pos].set_label(label_parts[0])

    def update_modifier(self, key_event, value):
      self.modifiers[key_event] = value
      button = self.modifier_buttons[key_event]
      style_context = button.get_style_context()
      if (value):
          style_context.add_class('active-modifier')
      else:
          style_context.remove_class('active-modifier')

    def on_button_press(self, widget, key_event):
        # If it's a modifier, toggle state (like Shift, Ctrl, etc.)
        if key_event in self.modifiers:
            self.update_modifier(key_event, not self.modifiers[key_event])

            # prevent both shifts being active at once
            if self.modifiers["Shift_L"] and self.modifiers["Shift_R"]:
                self.update_modifier("Shift_L", False)
                self.update_modifier("Shift_R", False)

            # update label state (caps-like effect)
            if self.modifiers["Shift_L"] or self.modifiers["Shift_R"]:
                self.update_label(True)
            else:
                self.update_label(False)
            return  # modifiers don’t repeat

        # Fire key once immediately
        self.emit_key(key_event)

        # Start a one-time delay before repeat kicks in (e.g. 400ms)
        self.delay_source = GLib.timeout_add(400, self.start_repeat, key_event)

    def on_button_release(self, widget, *args):
        # Cancel both delay and repeat when released
        if hasattr(self, "delay_source"):
            GLib.source_remove(self.delay_source)
            del self.delay_source
        if hasattr(self, "repeat_source"):
            GLib.source_remove(self.repeat_source)
            del self.repeat_source

    def start_repeat(self, key_event):
        # After the delay, start the repeat loop
        self.repeat_source = GLib.timeout_add(100, self.repeat_key, key_event)
        return False  # stop this one-time delay timer

    def repeat_key(self, key_event):
        self.emit_key(key_event)
        return True  # keep repeating

    def emit_key(self, key_event):
        self.track_current_word(key_event)
        self.backend.emit_key(key_event, self.modifiers)
        self.update_label(False)
        for mod_key, active in self.modifiers.items():
            if active:
                self.update_modifier(mod_key, False)

    def track_current_word(self, key_event):
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
        return any(
            self.modifiers[modifier]
            for modifier in ("Ctrl_L", "Ctrl_R", "Alt_L", "Alt_R", "Super_L", "Super_R")
        )

    def key_event_to_character(self, key_event):
        shift_active = self.modifiers["Shift_L"] or self.modifiers["Shift_R"]

        if len(key_event) == 1 and key_event.isalpha():
            return key_event if shift_active else key_event.lower()

        if key_event in SHIFTED_KEY_MAP:
            return SHIFTED_KEY_MAP[key_event] if shift_active else key_event

        return None

    def update_suggestions(self):
        suggestions = self.suggestion_engine.get_suggestions(self.current_word, SUGGESTION_LIMIT)

        for index, button in enumerate(self.suggestion_buttons):
            style_context = button.get_style_context()
            if index < len(suggestions):
                button.set_label(self.apply_suggestion_case(suggestions[index]))
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
        suggestion = widget.get_label()
        if not suggestion or not self.current_word:
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

        if char.isalpha():
            key_event = char.upper()
            if char.isupper():
                modifiers["Shift_L"] = True
            return key_event, modifiers

        for key_event, shifted_char in SHIFTED_KEY_MAP.items():
            if char == shifted_char:
                modifiers["Shift_L"] = True
                return key_event, modifiers

        if char in SHIFTED_KEY_MAP:
            return char, modifiers

        return None, modifiers

    def read_settings(self):
        # Ensure the config directory exists
        try:
            os.makedirs(self.CONFIG_DIR, exist_ok=True)
        except PermissionError:
            print("Warning: No permission to create the config directory. Proceeding without it.")

        try:
            if os.path.exists(self.CONFIG_FILE):
                self.config.read(self.CONFIG_FILE)
                self.bg_color = self.config.get("DEFAULT", "bg_color" )
                self.opacity = self.config.get("DEFAULT", "opacity" )
                self.text_color = self.config.get("DEFAULT", "text_color", fallback="white" )
                self.width=self.config.getint("DEFAULT", "width" , fallback=0)
                self.height=self.config.getint("DEFAULT", "height", fallback=0)
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

        except configparser.Error as e:
            print(f"Warning: Could not read config file ({e}). Using default values.")



    def save_settings(self):

        self.config["DEFAULT"] = {
            "bg_color": self.bg_color,
            "opacity": self.opacity,
            "text_color": self.text_color,
            "width": self.width,
            "height": self.height,
            "pos_x": str(self.pos_x),
            "pos_y": str(self.pos_y),
        }

        try:
            with open(self.CONFIG_FILE, "w") as configfile:
                self.config.write(configfile)

        except (configparser.Error, IOError) as e:
            print(f"Warning: Could not write to config file ({e}). Changes will not be saved.")


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


if __name__ == "__main__":
    install_kwin_rule_if_needed()
    app = VboardApplication()
    raise SystemExit(app.run(sys.argv))
