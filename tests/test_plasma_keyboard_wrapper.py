import os
import pathlib
import subprocess
import tempfile
import unittest


class PlasmaKeyboardWrapperTest(unittest.TestCase):
    def test_derives_direct_language_switch_style(self):
        repository = pathlib.Path(__file__).resolve().parents[1]
        wrapper = repository / "scripts" / "vboard-plasma-keyboard"

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = pathlib.Path(temporary_directory)
            qml_root = root / "qml"
            breeze_dir = (
                qml_root
                / "QtQuick"
                / "VirtualKeyboard"
                / "Styles"
                / "Breeze"
            )
            breeze_dir.mkdir(parents=True)
            (breeze_dir / "style.qml").write_text(
                "KeyboardStyle { languagePopupListEnabled: true }\n",
                encoding="utf-8",
            )

            bin_dir = root / "bin"
            bin_dir.mkdir()
            qtpaths = bin_dir / "qtpaths6"
            qtpaths.write_text(
                f"#!/bin/sh\nprintf '%s\\n' '{qml_root}'\n",
                encoding="utf-8",
            )
            qtpaths.chmod(0o755)

            environment = os.environ.copy()
            environment["PATH"] = f"{bin_dir}:{environment['PATH']}"
            environment["XDG_CACHE_HOME"] = str(root / "cache")
            completed = subprocess.run(
                [wrapper, "--prepare-style"],
                check=True,
                capture_output=True,
                text=True,
                env=environment,
            )

            generated_style = pathlib.Path(completed.stdout.strip())
            self.assertTrue(generated_style.is_file())
            self.assertEqual(generated_style.parent.name, "Breeze")
            style_text = generated_style.read_text(encoding="utf-8")
            self.assertIn("languagePopupListEnabled: false", style_text)
            self.assertNotIn("languagePopupListEnabled: true", style_text)

    def test_configurator_notifies_kwin_and_restarts_only_input_method(self):
        repository = pathlib.Path(__file__).resolve().parents[1]
        configurator = repository / "scripts" / "configure-plasma-keyboard.sh"

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = pathlib.Path(temporary_directory)
            data_home = root / "share"
            applications = data_home / "applications"
            applications.mkdir(parents=True)
            desktop_entry = (
                applications
                / "io.github.archisman-panigrahi.vboard-plasma-keyboard.desktop"
            )
            desktop_entry.write_text("[Desktop Entry]\n", encoding="utf-8")

            bin_dir = root / "bin"
            bin_dir.mkdir()
            call_log = root / "kwriteconfig.calls"
            kwriteconfig = bin_dir / "kwriteconfig6"
            kwriteconfig.write_text(
                "#!/bin/sh\nprintf '%s\\n' \"$*\" >>\"$CALL_LOG\"\n",
                encoding="utf-8",
            )
            kwriteconfig.chmod(0o755)

            environment = os.environ.copy()
            environment["PATH"] = f"{bin_dir}:{environment['PATH']}"
            environment["XDG_DATA_HOME"] = str(data_home)
            environment["CALL_LOG"] = str(call_log)
            subprocess.run(
                [configurator, "--desktop-and-lock-screen"],
                check=True,
                capture_output=True,
                text=True,
                env=environment,
            )

            calls = call_log.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(calls), 3)
            self.assertTrue(all("--notify" in call for call in calls))
            self.assertIn("--key InputMethod ", calls[0])
            self.assertIn(str(desktop_entry), calls[1])
            self.assertIn("--key VirtualKeyboardEnabled true", calls[2])


if __name__ == "__main__":
    unittest.main()
