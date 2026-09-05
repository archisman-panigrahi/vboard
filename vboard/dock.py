"""Wayland layer-shell integration for Vboard's dock mode."""

from .gtk import GTK_LAYER_SHELL_AVAILABLE, GtkLayerShell


def configure_dock_window(window, enabled, layer_shell=None):
    """Configure *window* as a bottom layer-shell dock before it is realized.

    Returns True only when dock mode was requested and layer-shell support was
    successfully enabled. A regular floating window remains the safe fallback.
    """

    if not enabled:
        return False

    layer_shell = layer_shell or GtkLayerShell
    if not GTK_LAYER_SHELL_AVAILABLE and layer_shell is None:
        print(
            "Warning: Dock mode requires gtk-layer-shell; "
            "falling back to a floating window."
        )
        return False

    try:
        layer_shell.init_for_window(window)
        layer_shell.set_layer(window, layer_shell.Layer.TOP)
        for edge in (
            layer_shell.Edge.LEFT,
            layer_shell.Edge.RIGHT,
            layer_shell.Edge.BOTTOM,
        ):
            layer_shell.set_anchor(window, edge, True)
        layer_shell.set_keyboard_mode(window, layer_shell.KeyboardMode.NONE)
        if hasattr(layer_shell, "set_namespace"):
            layer_shell.set_namespace(window, "vboard")
        layer_shell.auto_exclusive_zone_enable(window)
        return True
    except (AttributeError, RuntimeError, TypeError) as exc:
        print(f"Warning: Could not enable dock mode ({exc}).")
        return False
