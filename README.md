# vboard
*A virtual keyboard for Linux with Wayland support and extensive customization options.*


<img src="https://github.com/user-attachments/assets/66e9a879-c677-429f-bd11-503d10e63c2b" width="400">

## Overview
vboard is a lightweight, customizable virtual keyboard designed for Linux systems with Wayland support. It provides an on-screen keyboard solution that's especially useful for:

- Touchscreen devices without physical keyboards
- Systems with malfunctioning physical keyboards
- Accessibility needs
- Kiosk applications

The keyboard supports customizable colors, opacity settings, and can be easily modified to support different layouts.

## Features
- **Customizable appearance**: Change background color, text color, and opacity
- **Persistent settings**: Configuration is saved between sessions
- **Modifier key support**: Use Shift, Ctrl, Alt and Super keys
- **Hold for repetitive clicks**: Keep holding the mouse button to trigger repeated clicks
- **Word suggestions**: Offers completions from an installed Hunspell dictionary while you type with vboard
- **Compact interface**: Headerbar with minimal controls to save screen space
- **Always-on-top**: Stays above other windows for easy access
- **Tray icon support**: Keeps vboard running in the background and you can quickly reopen it when needed
- **uinput input backend**: Injects keys through Linux `uinput`

## Installation


### PPA for Ubuntu

Run the following commands to install vboard from its official PPA:

```bash
sudo add-apt-repository ppa:apandada1/vboard
sudo apt update
sudo apt install vboard
```

**Restart for changes to take effect**.

### Install from source in Ubuntu/Debian

For Ubuntu and Debian-based systems, use the automated setup script for a complete installation:

```bash
git clone https://github.com/archisman-panigrahi/vboard.git
cd vboard
sudo bash setup-ubuntu-debian.sh
```

This script will handle all setup steps including dependency installation, uinput configuration, and system-wide installation. A system restart is recommended after installation.

### Manual Installation

For other distributions or custom setups, follow the steps below.

### 1. Install dependencies

**For Debian/Ubuntu-based distributions:**
```bash
sudo apt install python3-gi gir1.2-gtk-3.0 python3-uinput gir1.2-ayatanaappindicator3-0.1 meson ninja-build --no-install-recommends
```
Optional for word suggestions:
```bash
sudo apt install hunspell-en-us
```

**For Fedora-based distributions:**
```bash
sudo dnf install python3-gobject gtk3 python3-uinput libappindicator-gtk3 meson ninja-build
```

**For Arch-based distributions:**
```bash
sudo pacman -S python-gobject gtk3 python-uinput libayatana-appindicator meson ninja
```
Optional for word suggestions:
```bash
sudo pacman -S hunspell-en_us
```

### 2. Download latest master

```bash
git clone https://github.com/archisman-panigrahi/vboard.git
cd vboard
```

### 3. Prepare uinput (required)

Run once with sudo before Meson install:

```bash
sudo bash scripts/setup-uinput.sh
```

For system installs, this also installs a `udev` rule so your logged-in desktop user can access `/dev/uinput`. If permissions still do not apply, log out/log in or restart your computer.

### 4. Build and install with Meson

On KDE/Plasma, install hooks automatically create the appropriate KWin window rule for vboard using its Wayland application ID instead of the window title.

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

### 5. Uninstall

```bash
meson compile -C builddir uninstall-local
```

For system installs:
```bash
sudo meson compile -C builddir uninstall-local
```

### KDE Plasma: enable vboard as the on-screen keyboard

After installation, open **System Settings**, search for **Virtual Keyboard**, and select **Vboard**.

## Usage
When launched, vboard presents a compact keyboard with a minimal interface. The keyboard includes:
- Standard QWERTY layout keys
- Arrow keys
- Modifier keys (Shift, Ctrl, Alt, Super)
- Header-bar suggestions that appear while typing words through vboard when a system Hunspell dictionary is available

### Interface Controls
- ☰ (menu) - Toggle visibility of other interface controls
- + - Increase opacity
- - - Decrease opacity
- **Background dropdown** - Change the keyboard background color

## Configuration
vboard saves its settings to `~/.config/vboard/settings.conf`. This configuration file stores:
- Background color
- Opacity level
- Text color

You can manually edit this file or use the built-in interface controls to customize the appearance.

## Customizing Keyboard Layout
The keyboard layout is defined in the `rows` list in the source code. To modify the layout:
1. Download the source code
2. Locate the rows definition
3. Modify the key arrangement as needed

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

## License
vboard is licensed under the GNU Lesser General Public License v2.1. See `LICENSE` for details.

## Note
Currently only the QWERTY US layout is supported.
