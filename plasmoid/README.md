# Vboard Plasma widget

This Plasma 6 widget shows or hides Vboard with one click. It expects `vboard`
to be available in the desktop session's `PATH`.

Install or update it for the current user:

```sh
kpackagetool6 --type Plasma/Applet --install plasmoid/package
kpackagetool6 --type Plasma/Applet --upgrade plasmoid/package
```

Then open Plasma's **Add Widgets** view, search for **Vboard Keyboard**, and drag
the widget onto a panel or the desktop.
