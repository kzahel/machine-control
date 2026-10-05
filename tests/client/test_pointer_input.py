import sys
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "client"))
from machine_control import translate_request

class PointerTranslationTests(unittest.TestCase):
    def test_windows_preserves_gesture_and_owner_fences(self):
        for native, fields in (("move", {"x": -40, "y": 30}),
                               ("drag", {"x": 10, "y": 20, "x2": 30, "y2": 40,
                                         "button": "right", "durationMs": 900}),
                               ("scroll", {"deltaX": -120, "deltaY": 240})):
            source = {"operation": "input." + native, **fields,
                      "expectedGeneration": "g", "requestId": "test"}
            result = translate_request("windows", source)
            self.assertEqual(result, {**source, "operation": native})
            self.assertEqual(source["operation"], "input." + native)
            self.assertEqual(translate_request("macos", source), source)

if __name__ == "__main__":
    unittest.main()
