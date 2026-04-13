import bisect
import math

from .constants import SUGGESTION_LIMIT
from .gtk import GLib, Gtk

GESTURE_NEAREST_KEY_COUNT = 3
GESTURE_SAMPLE_POINTS = 24
GESTURE_MIN_PATH_KEYS = 3
GESTURE_MIN_PATH_DISTANCE_FACTOR = 0.9
GESTURE_POINT_SAMPLE_STEP_FACTOR = 0.12
GESTURE_FEEDBACK_CLEAR_DELAY_MS = 180


def key_event_to_gesture_char(key_event):
    if len(key_event) == 1 and key_event.isalpha():
        return key_event.lower()
    if key_event in {"-", "'"}:
        return key_event
    return None


class GestureDecoder:
    def __init__(self, suggestion_engine):
        self.suggestion_engine = suggestion_engine
        self._indexed_words = None
        self.words_by_start_end = {}
        self.word_route_cache = {}

    def get_suggestions(
        self,
        path_points,
        key_centers,
        key_pitch,
        observed_route=None,
        limit=SUGGESTION_LIMIT,
    ):
        self.suggestion_engine.ensure_loaded()
        self.ensure_index()
        words = self.suggestion_engine.words
        if not words or not key_centers or key_pitch <= 0 or len(path_points) < 2:
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
            candidate_words = words

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

    def ensure_index(self):
        words = self.suggestion_engine.words
        if words is self._indexed_words:
            return

        self._indexed_words = words
        self.words_by_start_end = {}
        self.word_route_cache = {}
        for word in words:
            self.words_by_start_end.setdefault((word[0], word[-1]), []).append(word)

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


class GestureTypingController:
    def __init__(self, keyboard, grid_overlay):
        self.keyboard = keyboard
        self.grid_overlay = grid_overlay
        self.decoder = GestureDecoder(keyboard.suggestion_engine)
        self.active_gesture = None
        self.visible_gesture_points = []
        self.gesture_key_centers = {}
        self.gesture_key_rects = {}
        self.gesture_key_pitch = 0.0
        self._gesture_feedback_clear_source = None
        self.gesture_committed_text = ""
        self.gesture_overlay = self.build_overlay()

    def build_overlay(self):
        gesture_overlay = Gtk.DrawingArea()
        gesture_overlay.set_halign(Gtk.Align.FILL)
        gesture_overlay.set_valign(Gtk.Align.FILL)
        gesture_overlay.set_hexpand(True)
        gesture_overlay.set_vexpand(True)
        gesture_overlay.set_sensitive(False)
        gesture_overlay.set_can_focus(False)
        if hasattr(gesture_overlay, "set_has_window"):
            gesture_overlay.set_has_window(False)
        gesture_overlay.connect("draw", self.on_gesture_overlay_draw)
        self.grid_overlay.add_overlay(gesture_overlay)
        if hasattr(self.grid_overlay, "set_overlay_pass_through"):
            self.grid_overlay.set_overlay_pass_through(gesture_overlay, True)
        return gesture_overlay

    def destroy(self):
        self.cancel_gesture_feedback_clear()
        self.active_gesture = None
        self.clear_committed_text()
        self.visible_gesture_points = []
        if self.gesture_overlay is not None:
            self.gesture_overlay.destroy()
            self.gesture_overlay = None

    def has_committed_text(self):
        return bool(self.gesture_committed_text)

    def clear_committed_text(self):
        self.gesture_committed_text = ""

    def handle_key_press(self, widget, event, key_event):
        if key_event_to_gesture_char(key_event) is None:
            return False
        if self.keyboard.has_active_command_modifier():
            return False

        self.begin_gesture(widget, event, key_event)
        return True

    def handle_key_motion(self, widget, event):
        if self.active_gesture is None or self.active_gesture["widget"] is not widget:
            return False

        self.record_gesture_motion(widget, event)
        return True

    def handle_key_release(self, widget, event, key_event):
        if self.active_gesture is None or self.active_gesture["widget"] is not widget:
            return False

        self.record_gesture_motion(widget, event)
        self.finish_gesture(key_event)
        return True

    def refresh_layout_cache(self):
        gesture_key_centers = {}
        gesture_key_rects = {}
        key_sizes = []

        for key_event, button in self.keyboard.key_buttons.items():
            gesture_char = key_event_to_gesture_char(key_event)
            if gesture_char is None:
                continue

            allocation = button.get_allocation()
            if allocation.width <= 0 or allocation.height <= 0:
                continue

            origin_x, origin_y = self.translate_widget_point_to_overlay(button)
            gesture_key_centers[gesture_char] = (
                origin_x + (allocation.width / 2.0),
                origin_y + (allocation.height / 2.0),
            )
            gesture_key_rects[gesture_char] = (
                origin_x,
                origin_y,
                allocation.width,
                allocation.height,
            )
            key_sizes.append(min(allocation.width, allocation.height))

        self.gesture_key_centers = gesture_key_centers
        self.gesture_key_rects = gesture_key_rects
        self.gesture_key_pitch = (
            (sum(key_sizes) / len(key_sizes))
            if key_sizes
            else float(self.keyboard.BASE_KEY_HEIGHT)
        )

    def queue_overlay_draw(self):
        if self.gesture_overlay is not None:
            self.gesture_overlay.queue_draw()

    def begin_gesture(self, widget, event, key_event):
        self.cancel_gesture_feedback_clear()
        self.refresh_layout_cache()
        self.active_gesture = {
            "widget": widget,
            "points": [],
            "key_path": [],
            "total_distance": 0.0,
        }
        self.record_gesture_motion(widget, event, fallback_key_event=key_event)

    def record_gesture_motion(self, widget, event, fallback_key_event=None):
        if self.active_gesture is None:
            return

        point = self.get_gesture_point(widget, event)
        if point is None:
            return

        points = self.active_gesture["points"]
        min_step = max(2.0, self.gesture_key_pitch * GESTURE_POINT_SAMPLE_STEP_FACTOR)
        if not points:
            points.append(point)
        else:
            distance = self.distance_between(points[-1], point)
            self.active_gesture["total_distance"] += distance
            if distance >= min_step:
                points.append(point)
            else:
                points[-1] = point
        self.show_gesture_feedback(points)

        gesture_key = self.find_gesture_key_at_point(point)
        if gesture_key is None and fallback_key_event is not None:
            gesture_key = key_event_to_gesture_char(fallback_key_event)
        if gesture_key is None:
            return

        key_path = self.active_gesture["key_path"]
        if not key_path or key_path[-1] != gesture_key:
            key_path.append(gesture_key)

    def get_gesture_point(self, widget, event):
        origin_x, origin_y = self.translate_widget_point_to_overlay(widget)
        return (origin_x + event.x, origin_y + event.y)

    def translate_widget_point_to_overlay(self, widget):
        translated = widget.translate_coordinates(self.gesture_overlay, 0, 0)
        if translated is not None:
            return translated

        allocation = widget.get_allocation()
        return (allocation.x, allocation.y)

    def find_gesture_key_at_point(self, point):
        if not self.gesture_key_centers:
            return None

        best_key = None
        best_distance = None
        tolerance = max(4.0, self.gesture_key_pitch * 0.2)

        for key, rect in self.gesture_key_rects.items():
            rect_x, rect_y, rect_width, rect_height = rect
            if (
                rect_x - tolerance <= point[0] <= rect_x + rect_width + tolerance
                and rect_y - tolerance <= point[1] <= rect_y + rect_height + tolerance
            ):
                distance = self.distance_between(point, self.gesture_key_centers[key])
                if best_distance is None or distance < best_distance:
                    best_key = key
                    best_distance = distance

        if best_key is not None:
            return best_key

        max_distance = max(8.0, self.gesture_key_pitch * 0.95)
        for key, center in self.gesture_key_centers.items():
            distance = self.distance_between(point, center)
            if distance > max_distance:
                continue
            if best_distance is None or distance < best_distance:
                best_key = key
                best_distance = distance
        return best_key

    def finish_gesture(self, fallback_key_event):
        active_gesture = self.active_gesture
        self.active_gesture = None
        self.keyboard.stop_key_repeat()

        if active_gesture is None:
            return

        self.show_gesture_feedback(active_gesture["points"])
        if not self.should_commit_gesture_from_state(active_gesture):
            self.keyboard.emit_key(fallback_key_event)
            self.schedule_gesture_feedback_clear()
            return

        suggestions = self.decoder.get_suggestions(
            active_gesture["points"],
            self.gesture_key_centers,
            self.gesture_key_pitch,
            observed_route=active_gesture["key_path"],
            limit=SUGGESTION_LIMIT,
        )
        if not suggestions:
            self.keyboard.emit_key(fallback_key_event)
            self.schedule_gesture_feedback_clear()
            return

        formatted_suggestions = [self.apply_word_case(word) for word in suggestions]
        committed_text = formatted_suggestions[0]
        self.keyboard.emit_text(committed_text)
        self.keyboard.current_word = committed_text
        self.keyboard.suggestion_override = formatted_suggestions
        self.gesture_committed_text = committed_text
        self.keyboard.update_suggestions()
        self.keyboard.reset_modifiers()
        self.schedule_gesture_feedback_clear()

    def should_commit_gesture_from_state(self, gesture_state):
        return (
            len(gesture_state["key_path"]) >= GESTURE_MIN_PATH_KEYS
            and gesture_state["total_distance"]
            >= self.gesture_key_pitch * GESTURE_MIN_PATH_DISTANCE_FACTOR
        )

    def apply_word_case(self, word):
        if self.keyboard.modifiers["Shift_L"] or self.keyboard.modifiers["Shift_R"]:
            return word[:1].upper() + word[1:]
        return word

    def replace_committed_word(self, suggestion):
        suggestion = suggestion.strip()
        if not suggestion or not self.gesture_committed_text:
            return False

        if suggestion == self.gesture_committed_text:
            return True

        empty_modifiers = {modifier: False for modifier in self.keyboard.modifiers}
        for _ in self.gesture_committed_text:
            self.keyboard.backend.emit_key("Backspace", empty_modifiers)

        self.keyboard.emit_text(suggestion)
        self.keyboard.current_word = suggestion
        self.gesture_committed_text = suggestion
        if self.keyboard.suggestion_override is not None:
            remaining = [
                word for word in self.keyboard.suggestion_override if word != suggestion
            ]
            self.keyboard.suggestion_override = [suggestion] + remaining
        self.keyboard.update_suggestions()
        return True

    def cancel_gesture_feedback_clear(self):
        if self._gesture_feedback_clear_source is None:
            return
        GLib.source_remove(self._gesture_feedback_clear_source)
        self._gesture_feedback_clear_source = None

    def show_gesture_feedback(self, points):
        self.visible_gesture_points = [tuple(point) for point in points]
        self.queue_overlay_draw()

    def schedule_gesture_feedback_clear(self):
        self.cancel_gesture_feedback_clear()
        self._gesture_feedback_clear_source = GLib.timeout_add(
            GESTURE_FEEDBACK_CLEAR_DELAY_MS,
            self.clear_gesture_feedback,
        )

    def clear_gesture_feedback(self):
        self._gesture_feedback_clear_source = None
        self.visible_gesture_points = []
        self.queue_overlay_draw()
        return False

    def on_gesture_overlay_draw(self, widget, cr):
        if not self.visible_gesture_points:
            return False

        line_width = max(4.0, self.gesture_key_pitch * 0.16)
        start_x, start_y = self.visible_gesture_points[0]
        cr.move_to(start_x, start_y)
        for point_x, point_y in self.visible_gesture_points[1:]:
            cr.line_to(point_x, point_y)

        cr.set_source_rgba(0.16, 0.74, 0.86, 0.24)
        cr.set_line_width(line_width + 4.0)
        cr.stroke_preserve()

        cr.set_source_rgba(0.46, 0.92, 1.0, 0.78)
        cr.set_line_width(line_width)
        cr.stroke()

        end_x, end_y = self.visible_gesture_points[-1]
        radius = max(5.0, self.gesture_key_pitch * 0.14)
        cr.arc(end_x, end_y, radius, 0.0, 6.283185307179586)
        cr.set_source_rgba(0.7, 0.97, 1.0, 0.92)
        cr.fill()
        return False

    def distance_between(self, first_point, second_point):
        return (
            (first_point[0] - second_point[0]) ** 2
            + (first_point[1] - second_point[1]) ** 2
        ) ** 0.5
