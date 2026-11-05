"""Independent raw event sequences prove movement/overflow/loss behavior."""
import asyncio
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'desktop/native/linux'))
from activity_events import EVENT,bitmap,deliberate
from activityd import Tracker
from activity import Activity,console_binding


class ActivityTests(unittest.TestCase):
    def test_deliberate_input_excludes_motion_releases_and_tool_presence(self):
        for event in [(2,0,10),(2,1,-20),(3,0,40),(3,1,50),(1,30,0),(1,0x110,0),(1,0x145,1)]:
            self.assertFalse(deliberate(*event),event)
        for event in [(1,30,1),(1,30,2),(1,0x110,1),(2,8,1),(2,6,-1),(2,11,120),(2,12,-120)]:
            self.assertTrue(deliberate(*event),event)

    def test_sysfs_words_preserve_zero_word_width(self):
        self.assertEqual(bitmap('1 0 1'),(1<<128)|1)
        self.assertEqual(bitmap('0'),0)
        for invalid in ['', 'nothex', '1'*17]:
            with self.assertRaises(ValueError):bitmap(invalid)

    @unittest.skipIf(os.name == 'nt', 'Requires POSIX event-loop pipe readers')
    def test_raw_motion_has_no_activity_and_overflow_or_eof_fences(self):
        loop=asyncio.new_event_loop();self.addCleanup(loop.close)
        tracker=Tracker(loop)
        read,write=os.pipe()
        self.addCleanup(lambda:os.close(write))
        os.set_blocking(read,False)
        tracker.devices['fixture']=((),read);tracker.healthy=True
        self.addCleanup(tracker.close,'test_cleanup')
        loop.add_reader(read,lambda:None)
        initial=tracker.activity
        os.write(write,b''.join(EVENT.pack(0,0,*v) for v in [(2,0,90),(2,1,10),(0,0,0)]))
        tracker.read('fixture',read)
        self.assertEqual(tracker.activity,initial)
        os.write(write,EVENT.pack(0,0,1,30,1))
        tracker.read('fixture',read)
        tracker.sample_boundary()
        self.assertNotEqual(tracker.activity,initial)
        generation=tracker.generation
        os.write(write,EVENT.pack(0,0,0,3,0))
        tracker.read('fixture',read)
        self.assertFalse(tracker.healthy)
        self.assertNotEqual(tracker.generation,generation)
        self.assertEqual(tracker.devices,{})

    @unittest.skipIf(os.name == 'nt', 'Requires POSIX event-loop pipe readers')
    def test_stream_loss_is_unknown_instead_of_idle(self):
        loop=asyncio.new_event_loop();self.addCleanup(loop.close)
        tracker=Tracker(loop);read,write=os.pipe()
        os.set_blocking(read,False)
        tracker.devices['fixture']=((),read);tracker.healthy=True
        self.addCleanup(tracker.close,'test_cleanup')
        loop.add_reader(read,lambda:None)
        os.close(write);tracker.read('fixture',read)
        self.assertFalse(tracker.healthy)
        self.assertEqual(tracker.problem,'input_stream_lost')


class ActivityLivenessTests(unittest.TestCase):
    def test_silence_expires_but_current_negative_fences_immediately(self):
        identity=('fixture-session',123,':fixture')
        sensor=Activity(lambda callback,*args:callback(*args),lambda *_:None)
        self.addCleanup(sensor.close)
        sample=dict(generation='1'*32,activityToken='2'*32,healthy=True,
                    consoleBinding=console_binding(identity),problem=None,observedThroughUptime=100)
        with patch('activity.time.monotonic',return_value=100):
            sensor.completed(sample,None)
            self.assertTrue(sensor.healthy(identity))
        with patch('activity.time.monotonic',return_value=101):
            sensor.completed(None,'activity_observer_silent')
            self.assertTrue(sensor.healthy(identity))
        with patch('activity.time.monotonic',return_value=103):
            self.assertFalse(sensor.healthy(identity),'Silence cannot renew a stale positive')
        with patch('activity.time.monotonic',return_value=104):
            sensor.completed(sample,None)
            sensor.completed({**sample,'healthy':False},None)
            self.assertFalse(sensor.healthy(identity),'Current negative is stronger than a cached positive')
            sensor.completed(sample,None)
            sensor.completed(None,'activity_observer_unavailable')
            self.assertFalse(sensor.healthy(identity),'Endpoint loss fences immediately')
        with patch('activity.time.monotonic',return_value=105):
            sensor.completed({**sample,'observedThroughUptime':100},None)
            self.assertFalse(sensor.healthy(identity),'A new receipt cannot renew an old kernel boundary')

    def test_activation_waits_for_post_offer_kernel_boundary(self):
        identity=('fixture-session',123,':fixture')
        sensor=Activity(lambda callback,*args:callback(*args),lambda *_:None)
        self.addCleanup(sensor.close)
        # Retain the normal sample slot so no OS probe is scheduled by this
        # deterministic native observation-boundary test.
        sensor.pending=True
        sensor.refresh=lambda *_:None
        sample=dict(generation='1'*32,activityToken='2'*32,healthy=True,
                    consoleBinding=console_binding(identity),problem=None,observedThroughUptime=99)
        accepted=[]
        with patch('activity.time.monotonic',return_value=100):
            sensor.completed(sample,None)
            sensor.pending=True
            sensor.barrier(identity,accepted.append)
            self.assertEqual(accepted,[])
            sensor.pending=True
            sensor.completed({**sample,'observedThroughUptime':99.9},None)
            self.assertEqual(accepted,[],'An in-flight pre-offer sample is insufficient')
            sensor.pending=True
            sensor.completed({**sample,'observedThroughUptime':100.1},None)
            self.assertEqual(accepted,[True])
