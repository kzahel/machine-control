import unittest
from unittest import mock

import client


class ShortcutTest(unittest.TestCase):
    def setUp(self):
        self.layout = mock.patch.object(client, "_kb_layout", "qwerty")
        self.remappings = mock.patch.object(client, "_kb_remappings", {})
        self.press_keys = mock.patch.object(client, "press_keys")
        self.layout.start()
        self.remappings.start()
        self.mock_press_keys = self.press_keys.start()

    def tearDown(self):
        mock.patch.stopall()

    def test_named_key_with_modifiers(self):
        self.assertEqual(client.shortcut(["ctrl", "shift"], "tab"), [29, 42, 15])
        self.mock_press_keys.assert_called_once_with([29, 42, 15])

    def test_named_key_without_modifier(self):
        self.assertEqual(client.shortcut([], "enter"), [28])
        self.mock_press_keys.assert_called_once_with([28])

    def test_unknown_key_is_an_error(self):
        with self.assertRaisesRegex(ValueError, "unknown key"):
            client.shortcut(["ctrl"], "definitely-not-a-key")
        self.mock_press_keys.assert_not_called()

    def test_unknown_modifier_is_an_error(self):
        with self.assertRaisesRegex(ValueError, "unknown modifier"):
            client.shortcut(["hyper"], "t")
        self.mock_press_keys.assert_not_called()


if __name__ == "__main__":
    unittest.main()
