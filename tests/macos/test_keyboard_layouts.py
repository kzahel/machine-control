"""Regression for safe restoration of hidutil's OpenStep property output."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("keyboard_layouts", Path(__file__).with_name("keyboard-layouts.py"))
keyboard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(keyboard)
SRC = "HIDKeyboardModifierMappingSrc"
DST = "HIDKeyboardModifierMappingDst"


class HidMappingRestoreTests(unittest.TestCase):
    def test_openstep_numeric_strings_become_json_numbers(self):
        # plutil converts these OpenStep numbers into XML strings. Sending JSON
        # strings to hidutil caused WindowServer's keyboard filter to abort.
        restored = keyboard.normalized_hid_mapping([{SRC: "30064771298", DST: "30064771299"}])
        self.assertEqual(restored, [{SRC: 30064771298, DST: 30064771299}])
        self.assertTrue(all(type(v) is int for v in restored[0].values()))

    def test_unrecognized_or_unsafe_properties_are_refused(self):
        for value in [None, {}, [None], [{SRC: 1}], [{SRC: 1, DST: 2, "other": 3}],
                      [{SRC: True, DST: 2}], [{SRC: 1.5, DST: 2}],
                      [{SRC: -1, DST: 2}], [{SRC: 1 << 64, DST: 2}],
                      [{SRC: "not-a-number", DST: 2}]]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                keyboard.normalized_hid_mapping(value)

    def test_empty_and_existing_numeric_maps_are_preserved(self):
        self.assertEqual(keyboard.normalized_hid_mapping([]), [])
        original = [{SRC: 30064771129, DST: 30064771296}]
        self.assertEqual(keyboard.normalized_hid_mapping(original), original)


class HostObservationTests(unittest.TestCase):
    def test_passive_change_is_not_attributed_to_the_injector(self):
        observation = keyboard.host_observation({"cursor": [1, 2]}, {"cursor": [3, 4]})
        self.assertFalse(observation["hostUnchanged"])
        self.assertEqual(observation["hostObservation"], "changed_unattributed")
        self.assertEqual(observation["hostInputPolicy"], "forbidden")

    def test_quiet_controller_can_require_strict_equality(self):
        self.assertTrue(keyboard.host_observation({}, {}, True)["hostUnchanged"])
        with self.assertRaises(AssertionError):
            keyboard.host_observation({"cursor": 1}, {"cursor": 2}, True)


if __name__ == "__main__":
    unittest.main()
