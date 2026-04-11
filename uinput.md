# uinput troubleshooting

vboard now uses `uinput` as its only input backend. This document covers common device and permission issues.

If `vboard.py` fails with:

```text
OSError: [Errno 19] Failed to open the uinput device: No such device
```

it usually means the Linux `uinput` kernel module is not loaded, or the current user cannot access `/dev/uinput`.

## Fixes

1. Check whether the module is loaded:

```bash
lsmod | grep uinput
```

2. Load it if needed:

```bash
sudo modprobe uinput
```

3. Check that the device exists and is accessible:

```bash
ls -l /dev/uinput
```

4. If permissions are restrictive, add your user to the `input` group and log out/in:

```bash
sudo usermod -a -G input $USER
newgrp input
```

5. To load `uinput` automatically at boot:

```bash
echo 'uinput' | sudo tee /etc/modules-load.d/uinput.conf
```

## Notes

- On some systems, installing the relevant package may also be required, such as `python3-uinput`.
- If the device still cannot be opened after loading the module, verify that your distro exposes `/dev/uinput` and that no udev rule is blocking access.
