# Gesture Typing In Vboard

This document explains how gesture typing currently works in vboard, why it is structured this way, and what its practical limitations are.

The implementation lives mainly in:

- [vboard/window.py](./vboard/window.py)
- [vboard/suggestions.py](./vboard/suggestions.py)
- [vboard/constants.py](./vboard/constants.py)

## High-Level Idea

Gesture typing, sometimes called swipe typing or glide typing, lets the user drag a finger across the keyboard instead of tapping each letter individually.

The keyboard then tries to infer the intended word by answering this question:

> Which dictionary word produces a path across the keyboard that most closely matches the path the user just traced?

That is the core idea behind most shape-writing systems. In vboard, we implement a lightweight version of that idea using the existing Hunspell dictionary that already powers word suggestions.

In short, the algorithm does this:

1. Track the pointer path while the user drags across letter keys.
2. Convert the keyboard layout into a geometric model by storing the center point of each gesture-eligible key.
3. Turn the user path into a normalized sequence of sampled points and an observed key route.
4. Generate candidate words from the dictionary.
5. Convert each candidate word into its own ideal keyboard path.
6. Score how closely each candidate path matches the user path.
7. Commit the best-scoring word and show the next-best matches in the suggestion bar.

## Why Vboard Uses A Dictionary-Matching Approach

The current implementation is intentionally simple and local:

- It does not use a machine learning model.
- It does not use a user language model.
- It does not depend on a proprietary swipe-decoding library.
- It reuses the Hunspell dictionary already present for completions.

That makes it easy to ship and easy to understand, while still being useful for common words.

The tradeoff is that this decoder is less sophisticated than mature mobile keyboard engines such as Gboard, SwiftKey, or proprietary Android IME decoders. Those systems usually combine geometry, probabilistic language models, personalization, and much more nuanced touch modeling.

## Step 1: Which Keys Participate In Gesture Typing

Not every key is gesture-enabled.

The helper `key_event_to_gesture_char()` in [vboard/window.py](./vboard/window.py) currently allows:

- alphabetic keys `a-z`
- apostrophe `'`
- hyphen `-`

Modifier keys, arrows, space, enter, backspace, and other control keys are not part of the gesture graph.

This matters because gesture decoding only works for words that can be represented using those gesture characters.

## Step 2: Capturing The Swipe

Gesture capture begins in [vboard/window.py](./vboard/window.py) when a left-button press happens on a gesture-capable key:

- `on_key_button_press_event()`
- `begin_gesture()`
- `record_gesture_motion()`
- `on_key_button_motion_event()`
- `on_key_button_release_event()`

Instead of emitting the pressed letter immediately, vboard starts collecting gesture state:

- `points`: the geometric pointer path
- `key_path`: the sequence of keys crossed
- `total_distance`: total traced distance

This allows a normal tap and a swipe to share the same entry point:

- If the path is too short, it is treated as a tap.
- If the path is long enough and crosses enough distinct keys, it is treated as a gesture.

## Step 3: Building The Keyboard Geometry

To compare a swipe against words, the decoder needs a geometric model of the keyboard.

That is done in `refresh_gesture_layout_cache()` in [vboard/window.py](./vboard/window.py).

For each gesture-enabled key, vboard stores:

- the center point of the key
- the rectangular bounds of the key
- an estimated `gesture_key_pitch`

`gesture_key_pitch` is the average key size and acts as a normalization factor. It is used to make distance thresholds and scores scale with the current keyboard size.

This is important because vboard is resizable. A fixed threshold in pixels would behave badly if the keyboard becomes much larger or smaller.

## Step 4: Sampling The User Path

Raw pointer motion is noisy. The user may produce many very tiny movements, and GTK may emit many motion events. The algorithm therefore compresses and normalizes the path before scoring.

This happens in [vboard/suggestions.py](./vboard/suggestions.py), mainly through:

- `normalize_path_points()`
- `resample_path()`

### 4.1 Remove Tiny Movements

`normalize_path_points()` removes points that are too close to the previous stored point.

The threshold is based on:

- `GESTURE_POINT_SAMPLE_STEP_FACTOR`
- `gesture_key_pitch`

This keeps the path shape while reducing jitter.

### 4.2 Resample To A Fixed Number Of Points

`resample_path()` interpolates the path to a fixed number of evenly spaced samples:

- `GESTURE_SAMPLE_POINTS`

This means every gesture is compared in a normalized form with the same number of points, even if one swipe generated 20 GTK motion events and another generated 200.

Without this step, shape comparisons would be unstable and depend too heavily on input sampling rate.

## Step 5: Converting The Swipe Into An Observed Key Route

In addition to geometric points, vboard also records which keys the pointer appears to cross.

There are two related representations:

- `key_path` collected during motion in [vboard/window.py](./vboard/window.py)
- `observed_route` used by the decoder in [vboard/suggestions.py](./vboard/suggestions.py)

The path is converted into a route using nearby key centers, and repeated consecutive keys are collapsed. For example:

- `hello` becomes roughly `h-e-l-o`
- `good` becomes roughly `g-o-d`

This is deliberate. Gesture typing generally models the path of distinct key transitions, not repeated taps on the same key.

Repeated letters are hard to observe geometrically because the finger usually does not make a visible loop for them. Collapsing repeated letters avoids penalizing the user for that.

## Step 6: Restricting The Candidate Set

The dictionary may contain many thousands of words, so scoring every word for every gesture would be wasteful.

Vboard narrows candidates using the likely start and end keys of the swipe:

- `get_nearest_keys()`
- `collect_gesture_candidates()`
- `collect_relaxed_gesture_candidates()`

The decoder first finds a few nearest keys to:

- the first sampled point
- the last sampled point

Then it prefers words whose:

- first letter matches one of those likely start keys
- last letter matches one of those likely end keys

This is a very useful filter because the first and last letters of a swipe are often among the strongest signals.

If that strict filter yields nothing, vboard relaxes it by allowing candidates that match only the start or only the end.

If that still yields nothing, it falls back to the whole dictionary.

## Step 7: Turning Each Candidate Word Into A Template Path

Each candidate word is converted into an idealized keyboard route using:

- `word_to_gesture_route()`
- `build_template_points()`

For each word:

1. Normalize it to a route of distinct consecutive letters.
2. Map those letters to key centers.
3. Resample the resulting polyline so it has the same number of points as the user path.

This gives us a template path for that dictionary word that can be compared directly against the user’s traced path.

Example:

- word: `there`
- route: `t-h-e-r-e`
- template: line segments joining the centers of `t`, `h`, `e`, `r`, and `e`

## Step 8: Scoring A Candidate Word

The main scoring logic is in `get_gesture_suggestions()` in [vboard/suggestions.py](./vboard/suggestions.py).

Each candidate is assigned a score built from several parts.

Lower scores are better.

### 8.1 Shape Score

The decoder computes the average Euclidean distance between:

- the sampled user path
- the sampled template path of the candidate word

This is the most direct measure of geometric similarity.

If the finger trace follows the same overall shape as the candidate word’s center-to-center path, the shape score will be low.

### 8.2 Route Score

The decoder also compares:

- the observed key route from the swipe
- the candidate word’s distinct-letter route

This is done with `route_edit_distance()`, a standard Levenshtein-style edit distance.

This helps distinguish words with similar geometry but different key transition sequences.

For example, two words can have somewhat similar shapes while still differing in the order of crossed letters. Route distance helps separate them.

### 8.3 Endpoint Score

The decoder measures how close the swipe endpoints are to:

- the first key center of the candidate
- the last key center of the candidate

This gives extra weight to start and end accuracy, which is often a strong signal in gesture typing.

### 8.4 Length Penalty

A small penalty is applied when the candidate word length differs too much from the observed route length.

This is only a soft bias, not a hard rule.

It nudges the ranking toward words whose structural complexity looks closer to the swipe.

### 8.5 Final Combined Score

The final score is a weighted combination of:

- shape similarity
- route similarity
- endpoint accuracy
- length mismatch penalty

The current implementation uses hand-tuned weights. They are intended to be practical defaults rather than mathematically optimal values.

## Step 9: Deciding Whether The Gesture Is Real

Not every drag should become a word. Users also tap keys normally.

Vboard uses `should_commit_gesture_from_state()` in [vboard/window.py](./vboard/window.py) to decide whether the collected movement is gesture-like enough.

The gesture must satisfy both of these conditions:

- it crosses at least `GESTURE_MIN_PATH_KEYS` distinct keys
- it travels at least `GESTURE_MIN_PATH_DISTANCE_FACTOR * gesture_key_pitch`

If the movement is too short or only stays on one or two keys, vboard falls back to the normal tap behavior and emits the original key instead.

This is what allows taps and swipes to coexist.

## Step 10: Committing The Word

If decoding succeeds, `finish_gesture()` in [vboard/window.py](./vboard/window.py):

1. takes the best-ranked candidate
2. emits the full word character by character through the existing input backend
3. stores that committed word in `current_word`
4. shows the top gesture candidates in the suggestion bar

The suggestion bar is reused instead of building a separate gesture-candidate UI.

If the user taps one of the alternative gesture suggestions, `replace_gesture_committed_word()` backspaces the committed word and inserts the selected alternative.

## How Shift Interacts With Gesture Typing

If shift is active when the gesture is committed, `apply_gesture_word_case()` capitalizes the first letter of the chosen candidate.

This is intentionally conservative:

- It supports a capitalized first word such as `Hello`.
- It does not currently attempt full uppercase gesture entry.

That keeps the behavior predictable and avoids overcomplicating the first implementation.

## Relation To Existing Word Suggestions

Gesture typing is built on top of the same Hunspell dictionary that already powers prefix suggestions.

That gives several nice properties:

- no second dictionary is needed
- gesture candidates and typed suggestions share the same vocabulary
- systems with an installed Hunspell dictionary gain gesture typing automatically

But it also means gesture typing depends on dictionary availability. If Hunspell data is missing, gesture decoding will not have a useful candidate list.

## Why Repeated Letters Are Not Explicitly Traced

This is worth calling out because it is a common source of confusion.

If the intended word is:

- `letter`

The finger usually does not produce:

- `l-e-t-t-e-r`

as distinct spatial stops.

Instead, the geometric path is closer to:

- `l-e-t-e-r`

with the double `t` implied by the language model and candidate vocabulary.

That is why vboard collapses consecutive repeated letters when constructing gesture routes. This matches how swipe typing is generally modeled in practice.

## Current Limitations

This decoder is intentionally lightweight, so it has some limitations.

### No Statistical Language Model

The ranking is based only on dictionary membership and geometric matching. It does not yet use:

- word frequency
- user history
- previous-word context
- sentence-level prediction

This means two geometrically similar words may rank less naturally than they would in a mature phone keyboard.

### No Personalization

The system does not currently learn:

- names
- slang
- custom abbreviations
- words the user frequently selects after correction

### Limited Character Set

Only alphabetic keys plus apostrophe and hyphen are gesture-enabled right now.

### No Cross-Word Swiping

Some commercial keyboards let the user keep swiping through the space bar to enter multiple words in one continuous stroke.

Vboard does not do that yet. Each gesture corresponds to one word.

### Geometry Is Center-Based

The template path for a word is just the polyline through key centers. More advanced decoders usually use richer touch models, such as:

- probabilistic key hit regions
- anisotropic touch error models
- curvature and speed features
- directional features
- language-model rescoring

## Tuning Knobs

The main constants live in [vboard/constants.py](./vboard/constants.py):

- `GESTURE_NEAREST_KEY_COUNT`
- `GESTURE_SAMPLE_POINTS`
- `GESTURE_MIN_PATH_KEYS`
- `GESTURE_MIN_PATH_DISTANCE_FACTOR`
- `GESTURE_POINT_SAMPLE_STEP_FACTOR`

What they do:

- `GESTURE_NEAREST_KEY_COUNT`: how many possible start/end keys are considered
- `GESTURE_SAMPLE_POINTS`: how many evenly spaced points are used for comparison
- `GESTURE_MIN_PATH_KEYS`: minimum distinct crossed keys before a drag counts as a gesture
- `GESTURE_MIN_PATH_DISTANCE_FACTOR`: minimum travel distance relative to key size
- `GESTURE_POINT_SAMPLE_STEP_FACTOR`: how aggressively tiny pointer movements are collapsed

These are all practical tuning levers if gesture typing feels too eager, too strict, too noisy, or too insensitive.

## Why This Is A Good First Version

Even though this is simpler than a production mobile IME decoder, it has several strong properties:

- It is fully local.
- It is understandable.
- It reuses the existing dictionary infrastructure.
- It scales with keyboard size.
- It keeps normal tapping behavior intact.
- It exposes clear tuning points for future improvement.

That makes it a good foundation for iterative improvement.

## Possible Future Improvements

Some natural next steps would be:

- rank candidates using dictionary frequency or word usage frequency
- add user-learned custom words
- improve repeated-letter handling with language-aware rescoring
- add better capitalization behavior
- support multi-word swiping via the space bar
- incorporate directional and curvature features into scoring
- cache more candidate templates for speed
- add a debug overlay that visualizes the gesture path and candidate templates

## Summary

Vboard’s gesture typing algorithm is a shape-matching decoder:

1. capture a swipe
2. normalize the path
3. infer the crossed-key route
4. build idealized paths for dictionary words
5. score each candidate by geometric and structural similarity
6. commit the best match

That makes the feature simple, transparent, and practical, while leaving plenty of room for smarter ranking in future versions.
