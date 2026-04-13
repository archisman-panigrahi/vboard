import os
import subprocess


def get_desktop_environment():
    desktop_env = os.environ.get("XDG_CURRENT_DESKTOP", "")
    if desktop_env:
        return desktop_env.upper()
    return ""


DESKTOP_ENV = get_desktop_environment()


def _desktop_tokens():
    return {token for token in DESKTOP_ENV.split(":") if token}


def is_gnome_environment():
    desktop_tokens = _desktop_tokens()
    session_hint = " ".join(
        filter(
            None,
            [
                DESKTOP_ENV,
                os.environ.get("DESKTOP_SESSION", ""),
                os.environ.get("GNOME_DESKTOP_SESSION_ID", ""),
            ],
        )
    ).upper()
    return "GNOME" in desktop_tokens or "GNOME" in session_hint


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


def is_wayland_session():
    session_type = os.environ.get("XDG_SESSION_TYPE", "").upper()
    if session_type == "WAYLAND":
        return True
    return bool(os.environ.get("WAYLAND_DISPLAY"))


def configure_gdk_backend():
    if os.environ.get("GDK_BACKEND"):
        return
    if is_gnome_environment() and is_wayland_session():
        os.environ["GDK_BACKEND"] = "x11"


def get_data_root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def install_kwin_rule_if_needed():
    if not is_kde_environment():
        return

    local_script = os.path.join(get_data_root(), "scripts", "install-kwin-rule.sh")
    for script_path in (
        local_script,
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
