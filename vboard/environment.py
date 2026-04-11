import os
import subprocess


def get_desktop_environment():
    desktop_env = os.environ.get("XDG_CURRENT_DESKTOP", "")
    if desktop_env:
        return desktop_env.upper()
    return ""


DESKTOP_ENV = get_desktop_environment()


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
