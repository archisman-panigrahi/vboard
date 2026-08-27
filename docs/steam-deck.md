# Running Vboard on a Steam Deck (SteamOS 3.8+)

SteamOS runs KDE Plasma on Wayland with a read-only root filesystem, which
makes it a useful worst case for an on-screen keyboard: the X11 test extension
is unavailable, and anything installed into `/usr` is wiped by the next system
update.

Vboard works there with the evdev/uinput backend, which types through
`/dev/uinput` so applications see an ordinary physical keyboard — modifiers,
arrows, Tab and Esc included.

## Install without root

Everything stays in the user's home directory, so a system update cannot
remove it:

| Path | Purpose |
|------|---------|
| `~/.local/bin/vboard` | launcher |
| `~/.local/share/applications/vboard.desktop` | application menu entry |
| `~/.config/vboard/layouts/*.json` | custom layouts |
| `~/.config/vboard/settings.conf` | default layout |

## uinput permissions

Typing through uinput needs write access to `/dev/uinput`. On SteamOS the
device is usually already accessible if something else has set it up (`ydotoold`
does, for instance). If keys stop working after a reboot, the udev rule can be
installed once:

```bash
sudo bash scripts/setup-uinput.sh --scope=system
```

## Keyboard layouts and Cyrillic

uinput sends key *codes*, not characters — which character appears is decided
by the layout the compositor has active. A non-Latin Vboard layout therefore
only produces the right characters if the system layout matches, which is why
Vboard asks KWin to switch its layout alongside its own.

If layouts are switched elsewhere while Vboard is open, it re-syncs on its own.

## Binding to a controller button

In Desktop Mode the Deck's controller is driven by Steam Input, so a keyboard
shortcut is reached in two steps: bind a key combination to Vboard in *System
Settings → Shortcuts*, then map a controller button or chord to that same key
combination in Steam's desktop layout.

Steam may overwrite its own configuration files when the client updates, so a
chord configured by editing them directly can need reapplying. Setting the
binding through Steam's own UI avoids that.

## Why not the alternatives

On this platform Maliit has weak modifier support, Onboard is X11-only, and
Plasma's built-in keyboard does not offer the key set needed for anything
beyond text entry.
