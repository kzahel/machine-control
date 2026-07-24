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


class TargetsTest(unittest.TestCase):
    @mock.patch("cdp.list_targets")
    def test_page_indices_match_axtree_indices(self, list_targets):
        list_targets.return_value = [
            {"type": "service_worker", "title": "internal"},
            {"type": "page", "title": "First", "url": "https://one.example"},
            {"type": "background_page", "title": "internal"},
            {"type": "page", "title": "Second", "url": "https://two.example"},
        ]

        result = client.cmd_targets({})

        self.assertEqual([target["index"] for target in result["targets"]], [0, 1])
        self.assertEqual([target["title"] for target in result["targets"]],
                         ["First", "Second"])


class DesktopTapTest(unittest.TestCase):
    @mock.patch.object(client, "tap")
    @mock.patch("cdp.desktop_tree")
    @mock.patch("cdp.desktop_find")
    def test_maps_desktop_coordinates_to_raw_touchscreen(
            self, desktop_find, desktop_tree, tap):
        desktop_find.return_value = [{
            "role": "button",
            "name": "Settings",
            "location": {"x": 760, "y": 430, "width": 80, "height": 40},
        }]
        desktop_tree.return_value = {
            "role": "desktop",
            "location": {"x": 0, "y": 0, "width": 1600, "height": 900},
            "children": [{
                "role": "window",
                "name": "Built-in display",
                "location": {"x": 0, "y": 0, "width": 1600, "height": 900},
            }],
        }

        with mock.patch.object(client, "_ts_device", "/dev/input/event6"), \
             mock.patch.object(client, "_ts_max_x", 3492), \
             mock.patch.object(client, "_ts_max_y", 1968):
            result = client.cmd_desktop_tap({
                "pattern": "^Settings$", "role": "button",
            })

        self.assertTrue(result["ok"])
        self.assertEqual(result["tapped"]["touch"], {"x": 1746, "y": 984})
        tap.assert_called_once_with(1746, 984)

    @mock.patch("cdp.desktop_tree")
    @mock.patch("cdp.desktop_find")
    def test_rejects_element_on_external_display(self, desktop_find, desktop_tree):
        desktop_find.return_value = [{
            "role": "button",
            "name": "External",
            "location": {"x": 1800, "y": 100, "width": 100, "height": 50},
        }]
        desktop_tree.return_value = {
            "role": "desktop",
            "location": {"x": 0, "y": 0, "width": 3520, "height": 1080},
            "children": [{
                "role": "window",
                "name": "Built-in display",
                "location": {"x": 0, "y": 0, "width": 1600, "height": 900},
            }],
        }

        with mock.patch.object(client, "_ts_device", "/dev/input/event6"), \
             mock.patch.object(client, "_ts_max_x", 3492), \
             mock.patch.object(client, "_ts_max_y", 1968):
            result = client.cmd_desktop_tap({"pattern": "External"})

        self.assertIn("not on the built-in display", result["error"])


if __name__ == "__main__":
    unittest.main()
