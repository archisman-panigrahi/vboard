import bisect
import math
import os

from .constants import (
    GESTURE_NEAREST_KEY_COUNT,
    GESTURE_POINT_SAMPLE_STEP_FACTOR,
    GESTURE_SAMPLE_POINTS,
    SUGGESTION_LIMIT,
    SUPPORTED_WORD_CHARS,
)


class HunspellSuggestionEngine:
    def __init__(self):
        self.words = []
        self.words_by_start_end = {}
        self.dictionary_path = None
        self.loaded = False
        self.word_route_cache = {}

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
        self.words_by_start_end = {}
        self.word_route_cache = {}
        for word in self.words:
            self.words_by_start_end.setdefault((word[0], word[-1]), []).append(word)

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

    def get_gesture_suggestions(
        self,
        path_points,
        key_centers,
        key_pitch,
        observed_route=None,
        limit=SUGGESTION_LIMIT,
    ):
        self.ensure_loaded()
        if not self.words or not key_centers or key_pitch <= 0 or len(path_points) < 2:
            return []

        normalized_points = self.normalize_path_points(
            path_points,
            key_pitch * GESTURE_POINT_SAMPLE_STEP_FACTOR,
        )
        if len(normalized_points) < 2:
            return []

        sampled_points = self.resample_path(normalized_points, GESTURE_SAMPLE_POINTS)
        if len(sampled_points) < 2:
            return []

        if observed_route:
            observed_route = tuple(char for char in observed_route if char in key_centers)
        if not observed_route:
            observed_route = self.points_to_route(sampled_points, key_centers, key_pitch)
        if len(observed_route) < 2:
            return []

        start_keys = self.get_nearest_keys(
            sampled_points[0],
            key_centers,
            GESTURE_NEAREST_KEY_COUNT,
        )
        end_keys = self.get_nearest_keys(
            sampled_points[-1],
            key_centers,
            GESTURE_NEAREST_KEY_COUNT,
        )

        candidate_words = self.collect_gesture_candidates(start_keys, end_keys)
        if not candidate_words:
            candidate_words = self.collect_relaxed_gesture_candidates(start_keys, end_keys)
        if not candidate_words:
            candidate_words = self.words

        scored_candidates = []
        max_route_length_delta = max(2, len(observed_route))
        for word in candidate_words:
            gesture_route = self.word_to_gesture_route(word, key_centers)
            if gesture_route is None:
                continue
            if abs(len(gesture_route) - len(observed_route)) > max_route_length_delta:
                continue

            route_distance = self.route_edit_distance(gesture_route, observed_route)
            max_route_length = max(len(gesture_route), len(observed_route))
            if route_distance > max(4, max_route_length):
                continue

            template_points = self.build_template_points(
                gesture_route,
                key_centers,
                len(sampled_points),
            )
            if not template_points:
                continue

            shape_score = self.average_point_distance(sampled_points, template_points) / key_pitch
            route_score = route_distance / max(1, max_route_length)
            endpoint_score = (
                self.distance(sampled_points[0], key_centers[gesture_route[0]])
                + self.distance(sampled_points[-1], key_centers[gesture_route[-1]])
            ) / (2.0 * key_pitch)
            length_penalty = abs(len(word) - len(observed_route)) / max(4.0, len(word))
            score = shape_score + (0.55 * route_score) + (0.35 * endpoint_score)
            score += 0.15 * length_penalty
            scored_candidates.append((score, len(word), word))

        if not scored_candidates:
            return []

        scored_candidates.sort(key=lambda item: (item[0], item[1], item[2]))
        return [word for _score, _length, word in scored_candidates[:limit]]

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

    def collect_gesture_candidates(self, start_keys, end_keys):
        candidates = []
        seen = set()
        for start_key in start_keys:
            for end_key in end_keys:
                for word in self.words_by_start_end.get((start_key, end_key), []):
                    if word not in seen:
                        seen.add(word)
                        candidates.append(word)
        return candidates

    def collect_relaxed_gesture_candidates(self, start_keys, end_keys):
        candidates = []
        seen = set()
        for start_key in start_keys:
            for (candidate_start, _candidate_end), words in self.words_by_start_end.items():
                if candidate_start != start_key:
                    continue
                for word in words:
                    if word not in seen:
                        seen.add(word)
                        candidates.append(word)

        for end_key in end_keys:
            for (_candidate_start, candidate_end), words in self.words_by_start_end.items():
                if candidate_end != end_key:
                    continue
                for word in words:
                    if word not in seen:
                        seen.add(word)
                        candidates.append(word)
        return candidates

    def word_to_gesture_route(self, word, key_centers):
        cached_route = self.word_route_cache.get(word)
        if cached_route is None:
            route = []
            previous_char = None
            for char in word:
                if char == previous_char:
                    continue
                route.append(char)
                previous_char = char
            cached_route = tuple(route)
            self.word_route_cache[word] = cached_route

        if any(char not in key_centers for char in cached_route):
            return None
        return cached_route

    def points_to_route(self, points, key_centers, key_pitch):
        route = []
        max_distance = max(8.0, key_pitch * 0.95)
        for point in points:
            nearest_keys = self.get_nearest_keys(point, key_centers, 1)
            if not nearest_keys:
                continue
            nearest_key = nearest_keys[0]
            if self.distance(point, key_centers[nearest_key]) > max_distance:
                continue
            if not route or route[-1] != nearest_key:
                route.append(nearest_key)
        return tuple(route)

    def get_nearest_keys(self, point, key_centers, count):
        distances = []
        for key, center in key_centers.items():
            distances.append((self.distance(point, center), key))
        distances.sort(key=lambda item: (item[0], item[1]))
        return [key for _distance, key in distances[:count]]

    def build_template_points(self, route, key_centers, sample_count):
        centers = [key_centers[char] for char in route if char in key_centers]
        if not centers:
            return []
        if len(centers) == 1:
            return [centers[0]] * sample_count
        return self.resample_path(centers, sample_count)

    def normalize_path_points(self, points, min_distance):
        if min_distance <= 0:
            return list(points)

        normalized = [points[0]]
        min_distance_sq = min_distance * min_distance
        for point in points[1:]:
            if self.distance_squared(point, normalized[-1]) >= min_distance_sq:
                normalized.append(point)
        if normalized[-1] != points[-1]:
            normalized.append(points[-1])
        return normalized

    def resample_path(self, points, sample_count):
        if not points:
            return []
        if len(points) == 1 or sample_count <= 1:
            return [points[0]]

        segment_lengths = [0.0]
        total_length = 0.0
        for index in range(1, len(points)):
            total_length += self.distance(points[index - 1], points[index])
            segment_lengths.append(total_length)

        if total_length == 0:
            return [points[0]] * sample_count

        resampled = []
        for sample_index in range(sample_count):
            target_length = (total_length * sample_index) / (sample_count - 1)
            segment_index = bisect.bisect_left(segment_lengths, target_length)
            if segment_index <= 0:
                resampled.append(points[0])
                continue
            if segment_index >= len(points):
                resampled.append(points[-1])
                continue

            start_point = points[segment_index - 1]
            end_point = points[segment_index]
            start_length = segment_lengths[segment_index - 1]
            end_length = segment_lengths[segment_index]
            segment_span = end_length - start_length
            if segment_span == 0:
                resampled.append(end_point)
                continue

            offset = (target_length - start_length) / segment_span
            resampled.append(
                (
                    start_point[0] + ((end_point[0] - start_point[0]) * offset),
                    start_point[1] + ((end_point[1] - start_point[1]) * offset),
                )
            )
        return resampled

    def average_point_distance(self, points_a, points_b):
        if not points_a or not points_b:
            return float("inf")
        total = 0.0
        for point_a, point_b in zip(points_a, points_b):
            total += self.distance(point_a, point_b)
        return total / max(1, min(len(points_a), len(points_b)))

    def route_edit_distance(self, first_route, second_route):
        if first_route == second_route:
            return 0
        if not first_route:
            return len(second_route)
        if not second_route:
            return len(first_route)

        previous_row = list(range(len(second_route) + 1))
        for first_index, first_char in enumerate(first_route, start=1):
            current_row = [first_index]
            for second_index, second_char in enumerate(second_route, start=1):
                substitution_cost = 0 if first_char == second_char else 1
                current_row.append(
                    min(
                        previous_row[second_index] + 1,
                        current_row[second_index - 1] + 1,
                        previous_row[second_index - 1] + substitution_cost,
                    )
                )
            previous_row = current_row
        return previous_row[-1]

    def distance(self, first_point, second_point):
        return math.hypot(first_point[0] - second_point[0], first_point[1] - second_point[1])

    def distance_squared(self, first_point, second_point):
        return ((first_point[0] - second_point[0]) ** 2) + (
            (first_point[1] - second_point[1]) ** 2
        )
