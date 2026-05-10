#!/usr/bin/env python3

import os
import sys


def _candidate_roots():
    wrapper_dir = os.path.dirname(os.path.realpath(__file__))
    yield wrapper_dir
    yield os.path.normpath(os.path.join(wrapper_dir, "..", "share", "vboard"))


def _add_package_root_to_path():
    checked_roots = []
    for root in _candidate_roots():
        checked_roots.append(root)
        package_init = os.path.join(root, "vboard", "__init__.py")
        if os.path.isfile(package_init):
            if root not in sys.path:
                sys.path.insert(0, root)
            return

    checked_list = ", ".join(checked_roots)
    raise ModuleNotFoundError(f"Could not locate the vboard package. Checked: {checked_list}")


_add_package_root_to_path()

from vboard import main


if __name__ == "__main__":
    raise SystemExit(main())
