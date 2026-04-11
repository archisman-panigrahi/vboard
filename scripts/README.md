# scripts

This directory contains helper scripts used by vboard installation and integration.

- install-kwin-rule.sh
  - Adds/updates a KWin rule named `vboard` in `kwinrulesrc`.
  - Rule keeps vboard above other windows, disables focus, and remembers position.
  - Triggers `qdbus6 ... reconfigure` when available.

- uninstall-kwin-rule.sh
  - Removes the `vboard` KWin rule from `kwinrulesrc`.
  - Cleans up empty config state where possible.
  - Triggers `qdbus6 ... reconfigure` when available.

- install-plasma-osk.sh
  - Installs the desktop entry into the applications directory for user/system scope.
  - Refreshes desktop database.
  - Intended for KDE/Plasma virtual keyboard discovery.

- uninstall-plasma-osk.sh
  - Removes the installed desktop entry for user/system scope.
  - Refreshes desktop database.

- setup-uinput.sh
  - Prepares the uinput environment.
  - Must run as root.
  - Loads `uinput` module if needed.
  - For system scope, writes `/etc/modules-load.d/uinput.conf` for boot persistence.
  - Verifies `/dev/uinput` accessibility.

- meson-post-install.sh
  - Meson post-install hook entrypoint.
  - Runs `setup-uinput.sh` (root installs), then KDE/Plasma integration scripts when in KDE/Plasma session.
  - Skips mutating behavior when `DESTDIR` is set.

- meson-uninstall.sh
  - Meson uninstall helper used by `uninstall-local` target.
  - Runs uninstall integration scripts, removes installed vboard files, and prunes empty directories.

- meson-install.sh
  - Convenience helper for local development installs.
  - Handles `meson setup`, `meson compile`, and `meson install` with options for build dir, prefix, and sudo.
