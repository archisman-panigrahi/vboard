import os
import pathlib
import subprocess
import tempfile
import unittest


class PlasmaKeyboardWrapperTest(unittest.TestCase):
    def test_derives_layouts_with_direct_language_switch(self):
        repository = pathlib.Path(__file__).resolve().parents[1]
        wrapper = repository / "scripts" / "vboard-plasma-keyboard"

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = pathlib.Path(temporary_directory)
            source_layouts = root / "source-layouts"
            ukrainian = source_layouts / "uk_UA"
            ukrainian.mkdir(parents=True)
            source_layout = ukrainian / "main.qml"
            source_layout.write_text(
                "KeyboardLayout {\n"
                "    ChangeLanguageKey {\n"
                "        customLayoutsOnly: true\n"
                "    }\n"
                "}\n",
                encoding="utf-8",
            )

            environment = os.environ.copy()
            environment["XDG_CACHE_HOME"] = str(root / "cache")
            environment["VBOARD_PLASMA_LAYOUTS_SOURCE"] = str(source_layouts)
            completed = subprocess.run(
                [wrapper, "--prepare-layouts"],
                check=True,
                capture_output=True,
                text=True,
                env=environment,
            )

            generated_layouts = pathlib.Path(completed.stdout.strip())
            generated_layout = generated_layouts / "uk_UA" / "main.qml"
            self.assertTrue(generated_layout.is_file())
            layout_text = generated_layout.read_text(encoding="utf-8")
            self.assertIn(
                "onClicked: keyboard.changeInputLanguage(customLayoutsOnly)",
                layout_text,
            )
            self.assertNotIn("onClicked:", source_layout.read_text(encoding="utf-8"))

    def test_wrapper_exposes_derived_layouts_as_xdg_data_home(self):
        repository = pathlib.Path(__file__).resolve().parents[1]
        wrapper = repository / "scripts" / "vboard-plasma-keyboard"

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = pathlib.Path(temporary_directory)
            source_layouts = root / "source-layouts"
            layout_dir = source_layouts / "en_US"
            layout_dir.mkdir(parents=True)
            (layout_dir / "main.qml").write_text(
                "ChangeLanguageKey {\n}\n",
                encoding="utf-8",
            )
            fake_keyboard = root / "fake-plasma-keyboard"
            fake_keyboard.write_text(
                "#!/bin/sh\nprintf '%s\\n' \"$XDG_DATA_HOME\"\n",
                encoding="utf-8",
            )
            fake_keyboard.chmod(0o755)

            environment = os.environ.copy()
            environment["XDG_CACHE_HOME"] = str(root / "cache")
            environment["VBOARD_PLASMA_LAYOUTS_SOURCE"] = str(source_layouts)
            environment["VBOARD_PLASMA_KEYBOARD_EXECUTABLE"] = str(fake_keyboard)
            completed = subprocess.run(
                [wrapper],
                check=True,
                capture_output=True,
                text=True,
                env=environment,
            )

            data_home = pathlib.Path(completed.stdout.strip())
            self.assertEqual(
                data_home,
                root / "cache" / "vboard" / "plasma-keyboard" / "data",
            )
            self.assertTrue(
                (
                    data_home
                    / "plasma"
                    / "keyboard"
                    / "layouts"
                    / "en_US"
                    / "main.qml"
                ).is_file()
            )

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
