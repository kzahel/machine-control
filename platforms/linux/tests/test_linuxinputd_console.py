import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest import mock
import sys


if sys.platform == 'win32':
    raise unittest.SkipTest('The Linux input broker requires the POSIX account database')


SOURCE = Path(__file__).resolve().parents[1] / "guests/ubuntu/input/linuxinputd.py"
SPEC = importlib.util.spec_from_file_location("linuxinputd_console", SOURCE)
MODULE = importlib.util.module_from_spec(SPEC)
with mock.patch.dict(sys.modules, {"evdev": SimpleNamespace(
        AbsInfo=object, UInput=object,
        ecodes=SimpleNamespace(BTN_LEFT=272, BTN_RIGHT=273, BTN_MIDDLE=274))}):
    SPEC.loader.exec_module(MODULE)


class ConsoleTests(unittest.TestCase):
    def test_reads_structured_active_seat_and_session_properties(self):
        properties = "User=1000\nActive=yes\nType=wayland\nClass=user\nRemote=no\nSeat=seat0\n"
        owner = SimpleNamespace(pw_uid=1000)
        with mock.patch.object(MODULE, "logind", side_effect=["3", properties]) as logind, \
             mock.patch.object(MODULE.pwd, "getpwuid", return_value=owner) as lookup:
            self.assertIs(MODULE.active_console_user(), owner)
        self.assertEqual(logind.call_args_list[0].args,
                         ("show-seat", "seat0", "--property=ActiveSession", "--value"))
        self.assertEqual(logind.call_args.args[-2:], ("--", "3"))
        lookup.assert_called_once_with(1000)

    def test_refuses_missing_seat_and_ineligible_sessions(self):
        valid = dict(User="1000", Active="yes", Type="wayland", Class="user", Remote="no", Seat="seat0")
        for field, value in (("Active", "no"), ("Type", "tty"), ("Class", "greeter"),
                             ("Remote", "yes"), ("Seat", "seat1"), ("User", "0")):
            with self.subTest(field=field), mock.patch.object(
                    MODULE, "logind", side_effect=["3", "\n".join(
                        f"{key}={item}" for key, item in {**valid, field: value}.items())]):
                self.assertIsNone(MODULE.active_console_user())
        with mock.patch.object(MODULE, "logind", return_value="") as logind:
            self.assertIsNone(MODULE.active_console_user())
            self.assertEqual(logind.call_count, 1)
