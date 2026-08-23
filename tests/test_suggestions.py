import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from vboard.suggestions import HunspellSuggestionEngine


class HunspellSuggestionEngineTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.home = Path(self.temp_dir.name)
        self.dictionary_dir = self.home / ".local" / "share" / "hunspell"
        self.dictionary_dir.mkdir(parents=True)
        (self.dictionary_dir / "uk_UA.dic").write_text(
            "4\nпривіт\nпривітний/A\nприв'язка\nУкраїна\n",
            encoding="utf-8",
        )
        (self.dictionary_dir / "en_US.dic").write_text(
            "3\nhello\nhelp\nworld\n",
            encoding="utf-8",
        )
        self.home_patch = mock.patch.dict(os.environ, {"HOME": str(self.home)})
        self.home_patch.start()
        self.addCleanup(self.home_patch.stop)

    def test_ukrainian_unicode_suggestions(self):
        engine = HunspellSuggestionEngine("uk")

        self.assertEqual(engine.normalize_word("ПРИВʼЯЗКА"), "прив'язка")
        self.assertEqual(
            engine.get_suggestions("прив", 5),
            ["привіт", "прив'язка", "привітний"],
        )
        self.assertEqual(engine.dictionary_path, str(self.dictionary_dir / "uk_UA.dic"))

    def test_layout_switch_reloads_the_matching_dictionary(self):
        engine = HunspellSuggestionEngine("uk")
        engine.ensure_loaded()

        engine.set_layout("en")

        self.assertFalse(engine.loaded)
        self.assertEqual(engine.get_suggestions("hel", 5), ["help", "hello"])
        self.assertEqual(engine.dictionary_path, str(self.dictionary_dir / "en_US.dic"))

    def test_non_word_characters_are_rejected(self):
        engine = HunspellSuggestionEngine("uk")

        self.assertIsNone(engine.normalize_word("слово123"))
        self.assertIsNone(engine.normalize_word("--"))


if __name__ == "__main__":
    unittest.main()
