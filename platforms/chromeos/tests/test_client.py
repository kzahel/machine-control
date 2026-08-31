from pathlib import Path
import struct
import sys
import unittest
from unittest import mock


PLATFORM_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLATFORM_ROOT))
import client


class DrmWakeRetryTests(unittest.TestCase):
    def test_awake_capture_does_not_send_input(self):
        expected = {"image": "frame", "method": "egl", "format": "png"}
        with (
            mock.patch.object(client, "_drm_screenshot_b64", return_value=expected),
            mock.patch.object(client, "wake_display") as wake,
        ):
            actual = client._drm_screenshot_after_wake("egl", "png", 80)

        self.assertEqual(expected, actual)
        wake.assert_not_called()

    def test_sleeping_capture_wakes_and_retries_once(self):
        expected = {"image": "frame", "method": "egl", "format": "png"}
        with (
            mock.patch.object(
                client,
                "_drm_screenshot_b64",
                side_effect=[RuntimeError("No active CRTC found"), expected],
            ) as capture,
            mock.patch.object(client, "wake_display") as wake,
        ):
            actual = client._drm_screenshot_after_wake("egl", "png", 80)

        self.assertEqual(expected, actual)
        self.assertEqual(2, capture.call_count)
        wake.assert_called_once_with()

    def test_unrelated_capture_failure_does_not_send_input(self):
        with (
            mock.patch.object(
                client,
                "_drm_screenshot_b64",
                side_effect=RuntimeError("permission denied"),
            ),
            mock.patch.object(client, "wake_display") as wake,
        ):
            with self.assertRaisesRegex(RuntimeError, "permission denied"):
                client._drm_screenshot_after_wake("egl", "png", 80)

        wake.assert_not_called()

    def test_retry_failure_is_returned(self):
        with (
            mock.patch.object(
                client,
                "_drm_screenshot_b64",
                side_effect=[
                    RuntimeError("No active CRTC found"),
                    RuntimeError("No active CRTC found"),
                ],
            ) as capture,
            mock.patch.object(client, "wake_display") as wake,
        ):
            with self.assertRaisesRegex(RuntimeError, "No active CRTC"):
                client._drm_screenshot_after_wake("egl", "png", 80)

        self.assertEqual(2, capture.call_count)
        wake.assert_called_once_with()


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

    @mock.patch.object(client, "tap")
    @mock.patch("cdp.desktop_tree")
    @mock.patch("cdp.desktop_find")
    def test_preserves_top_left_origin_away_from_display_center(
            self, desktop_find, desktop_tree, tap):
        desktop_find.return_value = [{
            "role": "button",
            "name": "Settings",
            "location": {"x": 1544, "y": 796, "width": 32, "height": 32},
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

        self.assertEqual(result["tapped"]["touch"], {"x": 3405, "y": 1776})
        tap.assert_called_once_with(3405, 1776)

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


class TapTest(unittest.TestCase):
    @mock.patch.object(client, "VirtualTouchscreen")
    def test_uses_isolated_virtual_touchscreen(self, virtual_touchscreen):
        touchscreen = virtual_touchscreen.return_value
        with mock.patch.object(client, "_ts_max_x", 3492), \
             mock.patch.object(client, "_ts_max_y", 1968):
            client.tap(123, 456)

        virtual_touchscreen.assert_called_once_with(3492, 1968)
        touchscreen.tap.assert_called_once_with(123, 456)
        touchscreen.close.assert_called_once_with()

    @mock.patch.object(client, "VirtualTouchscreen")
    def test_closes_virtual_touchscreen_after_tap_failure(
            self, virtual_touchscreen):
        touchscreen = virtual_touchscreen.return_value
        touchscreen.tap.side_effect = RuntimeError("input failed")

        with self.assertRaisesRegex(RuntimeError, "input failed"):
            client.tap(123, 456)

        touchscreen.close.assert_called_once_with()


@unittest.skipIf(client.fcntl is None, "requires Linux fcntl")
class VirtualTouchscreenTest(unittest.TestCase):
    def test_declares_direct_device_and_emits_complete_contact(self):
        fd = mock.Mock()
        fd.fileno.return_value = 12
        with (
            mock.patch("builtins.open", return_value=fd),
            mock.patch.object(client.fcntl, "ioctl") as ioctl,
            mock.patch.object(client.time, "sleep"),
        ):
            touchscreen = client.VirtualTouchscreen(3492, 1968)
            touchscreen.tap(123, 456)
            touchscreen.close()

        ioctl.assert_any_call(12, client._UI_SET_PROPBIT,
                              client._INPUT_PROP_DIRECT)
        ioctl.assert_any_call(12, client._UI_DEV_CREATE)
        ioctl.assert_any_call(12, client._UI_DEV_DESTROY)
        events = [
            struct.unpack("llHHi", call.args[0])[-3:]
            for call in fd.write.call_args_list[1:]
        ]
        self.assertIn((client.EV_ABS, client.ABS_MT_POSITION_X, 123), events)
        self.assertIn((client.EV_ABS, client.ABS_MT_POSITION_Y, 456), events)
        self.assertIn((client.EV_ABS, client.ABS_X, 123), events)
        self.assertIn((client.EV_ABS, client.ABS_Y, 456), events)
        self.assertIn((client.EV_KEY, client.BTN_TOUCH, 1), events)
        self.assertIn((client.EV_KEY, client.BTN_TOUCH, 0), events)


if __name__ == "__main__":
    unittest.main()
