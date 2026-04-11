import bisect
import os

from .constants import SUGGESTION_LIMIT, SUPPORTED_WORD_CHARS


class HunspellSuggestionEngine:
    def __init__(self):
        self.words = []
        self.dictionary_path = None
        self.loaded = False

    def ensure_loaded(self):
        if self.loaded:
            return

        self.loaded = True
        self.dictionary_path = self.find_dictionary_path()
        if self.dictionary_path is None:
            return

        words = set()
        try:
            with open(self.dictionary_path, "r", encoding="utf-8", errors="ignore") as handle:
                for index, line in enumerate(handle):
                    if index == 0 and line.strip().isdigit():
                        continue

                    word = self.parse_dictionary_line(line)
                    if word is not None:
                        words.add(word)
        except OSError as exc:
            print(f"Warning: Could not read Hunspell dictionary ({exc}). Suggestions disabled.")
            self.dictionary_path = None
            return

        self.words = sorted(words)

    def get_suggestions(self, prefix, limit=SUGGESTION_LIMIT):
        self.ensure_loaded()
        prefix = self.normalize_word(prefix)
        if not prefix or not self.words:
            return []

        start_index = bisect.bisect_left(self.words, prefix)
        matches = []
        for word in self.words[start_index:]:
            if not word.startswith(prefix):
                break
            if word == prefix:
                continue
            matches.append(word)
            if len(matches) >= 50:
                break

        matches.sort(key=lambda word: (len(word), word))
        return matches[:limit]

    def find_dictionary_path(self):
        candidates = self.get_dictionary_candidates()
        search_dirs = [
            os.path.expanduser("~/.local/share/hunspell"),
            os.path.expanduser("~/.hunspell"),
            "/usr/share/hunspell",
            "/usr/share/myspell",
            "/usr/share/myspell/dicts",
        ]

        for directory in search_dirs:
            if not os.path.isdir(directory):
                continue

            for candidate in candidates:
                path = os.path.join(directory, f"{candidate}.dic")
                if os.path.isfile(path):
                    return path

        for directory in search_dirs:
            if not os.path.isdir(directory):
                continue

            try:
                for entry in sorted(os.listdir(directory)):
                    if entry.endswith(".dic"):
                        return os.path.join(directory, entry)
            except OSError:
                continue

        return None

    def get_dictionary_candidates(self):
        candidates = []
        for value in (
            os.environ.get("LC_ALL", ""),
            os.environ.get("LC_MESSAGES", ""),
            os.environ.get("LC_CTYPE", ""),
            os.environ.get("LANG", ""),
            os.environ.get("LANGUAGE", ""),
        ):
            for locale_name in value.split(":"):
                locale_name = locale_name.strip()
                if not locale_name:
                    continue

                locale_name = locale_name.split(".", 1)[0]
                locale_name = locale_name.split("@", 1)[0]
                if not locale_name:
                    continue

                candidates.append(locale_name)
                if "_" in locale_name:
                    candidates.append(locale_name.split("_", 1)[0])

        candidates.extend(["en_US", "en_GB", "en"])

        ordered = []
        seen = set()
        for candidate in candidates:
            if candidate not in seen:
                ordered.append(candidate)
                seen.add(candidate)
        return ordered

    def parse_dictionary_line(self, line):
        token = line.strip()
        if not token:
            return None

        token = token.split(maxsplit=1)[0]
        if not token:
            return None

        word_chars = []
        escaped = False
        for char in token:
            if escaped:
                word_chars.append(char)
                escaped = False
                continue
            if char == "\\":
                escaped = True
                continue
            if char == "/":
                break
            word_chars.append(char)

        return self.normalize_word("".join(word_chars))

    def normalize_word(self, word):
        if not word or not word.isascii():
            return None

        normalized = word.strip().lower()
        if len(normalized) < 2:
            return None
        if any(char not in SUPPORTED_WORD_CHARS for char in normalized):
            return None
        if not any(char.isalpha() for char in normalized):
            return None
        return normalized
