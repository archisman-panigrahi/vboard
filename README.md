# <img src="io.github.archisman-panigrahi.vboard.svg" align="left" width="100" height="100">  <br> vboard
*A configurable virtual keyboard for GNU/Linux with Wayland support on KDE Plasma, GNOME support via Xwayland, and desktop-oriented modifier, function, and navigation keys.*

*Wayland-compatible on KDE Plasma; also works on GNOME via Xwayland*.

It supports many themes, as you can see below:

<img src="screenshots/Screenshot_0_droid.png" width="600">

<img src="screenshots/Screenshot_1_enhanced_lavendar.png" width="600">

<img src="screenshots/stitched.gif" width="600">

## Overview
vboard is a lightweight, customizable virtual keyboard designed for Linux desktop systems. It runs as a Wayland-compatible on-screen keyboard on KDE Plasma, and also works on GNOME by falling back to Xwayland. It provides a full on-screen keyboard with modifier keys such as Ctrl, Alt, and Super (Meta/Win), which makes it especially useful for:

- Touchscreen devices without physical keyboards
- Systems with malfunctioning physical keyboards
- Accessibility needs
- Kiosk applications

The keyboard supports customizable colors and opacity, six built-in layouts,
and user-defined JSON layouts.

## Features
- **Customizable appearance**: Change background color and opacity
- **Persistent settings**: Configuration is saved between sessions
- **Modifier key support**: Provide Ctrl, Alt, Tab and Super (Meta/Win) keys
- **Function and navigation keys**: Includes F1-F12, arrows, Delete, Insert, Page Up, Page Down, Home, and End
- **Multiple layouts**: Includes English (US), German, French, Russian, Swedish, and Ukrainian layouts, plus user-defined JSON layouts
- **Plasma layout synchronization**: Follows supported KDE Plasma keyboard layouts and provides a configurable quick-switch key
- **Desktop compatibility**: Native Wayland-friendly behavior on KDE Plasma, with GNOME support via Xwayland fallback
- **Hold for repetitive clicks**: Keep holding the mouse button to trigger repeated clicks
- **Word suggestions**: Offers Unicode completions from the Hunspell dictionary that matches the active vboard layout
- **Gesture typing**: Swipe across letter keys in the active layout and vboard will decode the path with its matching Hunspell dictionary
- **Plasma widget**: Includes an optional one-click panel/desktop widget for showing or hiding vboard
- **Compact interface**: Headerbar with minimal controls to save screen space
- **Tray icon support**: Keeps vboard running in the background and you can quickly reopen it when needed
- **True dock mode**: Uses Wayland layer shell to reserve space at the bottom so normal windows do not sit underneath the keyboard
- **Text-field auto-show on Plasma Wayland**: Follows KWin's text-input state while yielding to Plasma Keyboard whenever its secure panel is visible
- **Secure Plasma integration**: An optional wrapper keeps KDE's native keyboard for lock screen and SDDM while making the language key switch directly without a popup
- **uinput input backend**: Injects keys through Linux `uinput`

Implementation notes for gesture typing are documented in [GESTURE_TYPING.md](./GESTURE_TYPING.md).

## Installation

### Ubuntu/Debian: `.deb` package

Download the latest `.deb` from this fork's [GitHub Releases](https://github.com/keefeere/vboard/releases) page, then install it with:

```bash
sudo apt install ./vboard_*.deb
```
**DO NOT** use `dpkg`. Please use `apt`. Otherwise, it will not work.

The package post-install step sets up `uinput` and installs the `udev` rule needed for desktop-session access to `/dev/uinput`.

**Log out and back in, or reboot, after installation.**

### PPA for Ubuntu

You can also use the following [PPA](https://code.launchpad.net/~apandada1/+archive/ubuntu/vboard) in Ubuntu.
Run the following commands one by one:

```bash
sudo add-apt-repository ppa:apandada1/vboard
sudo apt update
sudo apt install vboard
```

**Restart for changes to take effect**.

### Ubuntu/Debian: install from source

For the latest unreleased changes on Ubuntu and Debian-based systems, use the automated setup script:

```bash
git clone https://github.com/keefeere/vboard.git
cd vboard
sudo bash setup-ubuntu-debian.sh
```

This script will handle all setup steps including dependency installation, uinput configuration, and system-wide installation. **A system restart is recommended after installation**.

### Manual installation on other distros

For Debian/Ubuntu, Fedora, Arch, and other distributions, install the dependencies manually and then build with Meson.

### 1. Install dependencies

**For Debian/Ubuntu-based distributions:**
```bash
sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-3.0 gir1.2-gtklayershell-0.1 python3-uinput gir1.2-ayatanaappindicator3-0.1 meson ninja-build --no-install-recommends
```
Optional for word suggestions:
```bash
sudo apt install hunspell-en-us
```

**For Fedora-based distributions:**
```bash
sudo dnf install python3-gobject python3-cairo gtk3 gtk-layer-shell python3-uinput python3-setuptools libappindicator-gtk3 meson ninja-build
```
Optional for word suggestions:
```bash
sudo dnf install hunspell-en-US hunspell-uk
```

Release builds also provide `vboard` and `vboard-plasma` RPMs for Fedora 44.
Install both packages for the keyboard and its optional Plasma widget. On an
immutable Bazzite system, local RPMs must be layered with `rpm-ostree` and take
effect after a reboot; use the user-only source installation below if you want
to avoid package layering.

For only the dock-mode dependency on Bazzite/Fedora Atomic, use the additive
live-apply form when no conflicting deployment is pending:

```bash
rpm-ostree install -yA gtk-layer-shell
```

If rpm-ostree cannot live-apply it, the package becomes active after reboot.
Do not use `apply-live --allow-replacement` for this dependency.

In Fedora KDE, you will also have to create a symlink for qdbus
```
sudo ln -sf /usr/bin/qdbus-qt6 /usr/local/bin/qdbus6
```

**For Arch-based distributions:**
```bash
sudo pacman -S python-gobject gtk3 python-uinput python-cairo libayatana-appindicator meson ninja
```
Optional for word suggestions:
```bash
sudo pacman -S hunspell-en_us
```

### 2. Clone the repository

```bash
git clone https://github.com/keefeere/vboard.git
cd vboard
```

### 3. Prepare uinput (required)

Run once with sudo before Meson install:

```bash
sudo bash scripts/setup-uinput.sh
```

For system installs, this also installs a `udev` rule so your logged-in desktop user can access `/dev/uinput`. If permissions still do not apply, log out/log in or restart your computer.

### 4. Build and install with Meson

**Global install:**

```bash
meson setup builddir --prefix=/usr/local
meson compile -C builddir
sudo meson install -C builddir
```

**User-only install:**

```bash
meson setup builddir-user --prefix=$HOME/.local
meson compile -C builddir-user
meson install -C builddir-user
```

**Restart for changes to take effect.**
On KDE/Plasma, install hooks automatically create the appropriate KWin window rule for vboard using its Wayland application ID instead of the window title.

### 5. Uninstall

```bash
meson compile -C builddir uninstall-local
```

For system installs:
```bash
sudo meson compile -C builddir uninstall-local
```

### KDE Plasma: text fields, direct language switch, lock screen, and SDDM

Vboard's main window injects desktop keys through `uinput`; it is deliberately
not run inside the lock screen or login greeter. The install also provides
**Vboard Plasma Keyboard**, a wrapper around KDE's native secure keyboard (in
the `vboard-plasma` subpackage on Fedora). It retains Plasma's input-method
protocol and changes the language button from a popup into direct layout
cycling. It does this with a process-local, update-safe copy of Plasma's own
layouts: each `ChangeLanguageKey` directly selects the next enabled locale,
while the system layouts remain untouched.

Select it for the current Plasma session with:

```bash
~/.local/share/vboard/scripts/configure-plasma-keyboard.sh --desktop-and-lock-screen
```

For a system package installation, use
`/usr/share/vboard/scripts/configure-plasma-keyboard.sh` instead. You can also
select **Vboard Plasma Keyboard** in **System Settings → Virtual Keyboard**.
The same KWin input method is then available on Plasma's lock screen.

Plasma does not expose separate input-method provider selectors for the
unlocked desktop and lock screen: both belong to the same running KWin and use
the `InputMethod` entry in `kwinrc`. Vboard's GTK dock is used only on the
unlocked desktop; the wrapped native Plasma Keyboard remains the secure
provider that the lock screen can display. SDDM is genuinely separate because
it starts its own KWin compositor, so it is configured independently below.

To apply the wrapper to a Wayland SDDM greeter after a system-wide install:

```bash
sudo /usr/share/vboard/scripts/configure-plasma-keyboard.sh --sddm
```

This writes a separate SDDM drop-in and does not restart the display manager;
it takes effect on the next SDDM start. The generated layout tree lives in each
account's cache and is refreshed automatically whenever Plasma's installed
layouts change, so Plasma upgrades do not overwrite it. Plasma Keyboard 6.7
uses its own external language popup, which is why changing only Qt's Breeze
style is insufficient.

Enable **Dock Mode** in Vboard Options and restart Vboard to reserve the bottom
work area, or use the `⌄` header button to switch immediately. Dock mode forces
an opaque keyboard surface; the configured transparency is kept for floating
mode. Enable **Auto-show on text fields** to follow KWin's Wayland
text-input state. When native Plasma Keyboard is visible (including secure
screens), Vboard hides and lets it take precedence.

### KDE Plasma: install the toggle widget

The Fedora release provides the widget in the separate `vboard-plasma` RPM.
Install both binary RPMs to get the keyboard and widget; the `.src.rpm` is only
source code and is not needed for normal installation. The current `.deb`
installs the keyboard only.

When installing from a source checkout, install the included Plasma 6 widget
for the current user with:

```bash
kpackagetool6 --type Plasma/Applet --install plasmoid/package
```

Then open Plasma's **Add Widgets** view, search for **Vboard Keyboard**, and drag
it onto a panel or the desktop. Use `--upgrade` instead of `--install` after
changing the widget source.

## Usage
When launched, vboard presents a compact keyboard with a minimal interface. The keyboard includes:
- English (US), German (QWERTZ), French (AZERTY), Russian, Swedish, and Ukrainian layouts
- Arrow keys
- Modifier keys (Shift, Ctrl, Alt, Super)
- F1-F12 function keys in the header bar
- Delete, Insert, Page Up, Page Down, Home, and End navigation keys
- Header-bar suggestions that follow vboard's active layout when a matching system or user Hunspell dictionary is available
- Experimental swipe typing on alphabetic keys: drag across the intended letters and release to insert the best matching dictionary word

### Interface Controls
- ☰ (menu) - Toggle visibility of other interface controls
- **Options** - Open in-app options for typing, startup, layout, about, bug reports, and quit actions
- **UA/EN, RU/EN, …** - Switch between English and the secondary layout selected in Options
- `+ -` Increase opacity
- `- -` Decrease opacity
- **Background dropdown** - Change the keyboard background color or pick an enhanced color theme
- **Right-click a key** - Send Shift + that key once
- **Tray icon click** - Hide or show vboard
- **Tray icon right-click** - Open tray controls when the tray backend supports a separate context menu

Run `vboard --toggle` to start and show vboard when it is not running, or to
show/hide the existing instance. The included Plasma widget uses this command,
and it remains responsive when **Start Minimized** is enabled.

## Configuration
vboard saves its settings to `~/.config/vboard/settings.conf`. This configuration file stores:
- Background color
- Theme style
- Text prediction enabled/disabled state
- Gesture typing enabled/disabled state
- Gesture visual feedback enabled/disabled state
- Start minimized enabled/disabled state
- Dock mode enabled/disabled state
- Text-field auto-show enabled/disabled state
- Keyboard layout
- Secondary keyboard layout used by the quick-switch key
- Opacity level
- Text color

You can manually edit this file or use the built-in interface controls to customize vboard.

Hunspell dictionaries are searched in `~/.local/share/hunspell/`,
`~/.hunspell/`, and the usual system dictionary directories. For example, the
Ukrainian layout looks for `uk_UA.dic` or `uk.dic` and the English layout looks
for `en_US.dic`, `en_GB.dic`, or `en.dic`.

## Customizing Keyboard Layout
Keyboard layouts are JSON files. Packaged layouts are installed to:

```bash
/usr/share/vboard/vboard/layouts/
```

User layouts can be added or overridden in:

```bash
~/.config/vboard/layouts/
```

Each layout file defines an `id`, display `label`, `rows`, optional key `labels`, and optional `shifted` output. To customize a packaged layout, copy its JSON file into `~/.config/vboard/layouts/`, edit it, and restart vboard.

## Troubleshooting

### Input does not work

If vboard opens but pressing keys does not type anything, the `uinput` backend usually could not open `/dev/uinput`.

1. Check whether `uinput` exists and inspect its permissions:

```bash
ls -l /dev/uinput
```

2. Run the setup helper again as root:

```bash
sudo bash scripts/setup-uinput.sh
```

3. Reload `udev` rules and retrigger the device:

```bash
sudo udevadm control --reload-rules
sudo udevadm trigger --subsystem-match=misc --sysname-match=uinput
```

4. Log out and back in, or reboot, so your desktop session picks up the updated device permissions.

5. If it still does not work, add your user to the `input` group and log out/in again:

```bash
sudo usermod -a -G input $USER
```

You can also start vboard from a terminal and look for errors such as `Could not initialize uinput backend ([Errno 13])`.

### Error: no such device
Make sure `uinput` module is loaded:
```bash
sudo modprobe uinput
```

To auto-load at boot:
```bash
echo 'uinput' | sudo tee /etc/modules-load.d/uinput.conf
```

### Error: Permission denied
Run uinput setup script:
```bash
sudo bash scripts/setup-uinput.sh
```

This installs the packaged `udev` rule at `/etc/udev/rules.d/70-vboard-uinput.rules` for system installs. If needed, reload `udev`, then log out/log in or reboot:

```bash
sudo udevadm control --reload-rules
sudo udevadm trigger --subsystem-match=misc --sysname-match=uinput
```

## Contributing
Contributions are welcome.

## Credits
Originally created by mdev588. The original project was archived, and it is now maintained by Archisman Panigrahi.

Original project: https://github.com/mdev588/vboard

Special thanks to honjow for the icon and patches.

Thanks to Yavuz Kagan Yadigar for the enhanced theme inspiration.

Thanks to onboard developers for the droid theme inspiration.

Thanks to the Hunspell project for the suggestion engine.

This project is licensed under GPLv3.

## License
vboard is licensed under the GNU General Public License v3. See `LICENSE` for details.

## Layout support

Vboard ships with English (US), German, French, Russian, Swedish, and Ukrainian
layouts. On KDE Plasma, supported system layouts (`us`, `de`, `fr`, `ru`, `se`,
and `ua`) are synchronized through Plasma's keyboard-layout service. The
quick-switch key alternates between English and the **Secondary Layout** chosen
in Options. Additional vboard layouts can be supplied as user JSON files, but
automatic Plasma synchronization requires a corresponding XKB mapping in
`vboard/plasma_layouts.py`.
