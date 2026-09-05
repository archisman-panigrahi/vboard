import json
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PLASMOID_ROOT = PROJECT_ROOT / "plasmoid" / "package"


class PlasmoidLauncherTest(unittest.TestCase):
    def test_toggle_command_detaches_vboard_from_the_executable_engine(self):
        qml = (PLASMOID_ROOT / "contents" / "ui" / "main.qml").read_text(
            encoding="utf-8"
        )

        self.assertIn("/usr/bin/nohup /usr/bin/env vboard --toggle", qml)
        self.assertIn("</dev/null >/dev/null 2>&1 &", qml)

    def test_widget_version_marks_the_launcher_fix(self):
        metadata = json.loads(
            (PLASMOID_ROOT / "metadata.json").read_text(encoding="utf-8")
        )

        self.assertEqual(metadata["KPlugin"]["Version"], "1.0.1")


if __name__ == "__main__":
    unittest.main()
