import gi

gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")

from gi.repository import Gdk
from gi.repository import Gio
from gi.repository import GLib
from gi.repository import Gtk

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
