"""Native callback identity and presentation state, never admission policy."""
import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('notification_state',Path(__file__).resolve().parents[2]/'desktop/native/linux/notification_state.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


class NotificationTests(unittest.TestCase):
    def setUp(self):
        self.sent=[];self.closed=[];self.events=[];self.shown=[]
        def notify(identifier,*fields):self.sent.append((identifier,*fields));return identifier or 7
        self.notice=module.Notification(':1.42',notify,self.closed.append,
            lambda method,**fields:self.events.append((method,fields)),lambda:self.shown.append(True))
        self.choices=[('Allow this task','intent.approve',dict(intentId='task')),('Stop all access','stop',{})]
        self.update()
    def update(self,binding='ask',body='Reason'):
        self.notice.update(binding,'Machine Control',body,self.choices,'task','waiting_for_approval')
    def token(self):return next(key for key in self.notice.actions if key!='stop')
    def test_sender_id_and_old_action_cannot_authorize(self):
        token=self.token()
        self.notice.action(':1.43',7,token);self.notice.action(':1.42',8,token)
        self.update('another');self.notice.action(':1.42',7,token)
        self.assertEqual(self.events,[])
        self.notice.action(':1.42',7,self.token())
        self.assertEqual(self.events,[('intent.approve',{'intentId':'task'})])
    def test_decisions_do_not_replay_and_stop_remains_immediate(self):
        token=self.token()
        for _ in range(2):self.notice.action(':1.42',7,token)
        for _ in range(2):self.notice.action(':1.42',7,'stop')
        self.assertEqual([method for method,_ in self.events],['intent.approve','stop'])
    def test_countdown_replaces_without_rotating_callback_binding(self):
        token=self.token();self.update(body='Starting in nine seconds')
        self.assertEqual(self.token(),token);self.assertEqual(self.sent[-1][0],7)
        self.update(body='Starting in nine seconds');self.assertEqual(len(self.sent),2)
    def test_dismissal_defers_once_for_a_minute_without_approval(self):
        self.notice.closed(':1.43',7,2);self.assertEqual(self.events,[])
        self.notice.closed(':1.42',7,2);self.notice.closed(':1.42',7,2)
        self.assertEqual(self.events,[('intent.defer',{'intentId':'task','duration':60})])
        self.update();self.assertEqual(len(self.sent),1)
    def test_opening_controls_grants_no_authority_and_withdraw_ignores_late_signals(self):
        self.notice.action(':1.42',7,'default');self.assertEqual(self.events,[]);self.assertEqual(self.shown,[True])
        self.notice.closed(':1.42',7,2);self.assertEqual(self.events,[])
        self.update('active');self.notice.withdraw()
        self.notice.action(':1.42',7,'stop');self.notice.closed(':1.42',7,2)
        self.assertEqual(self.closed,[7]);self.assertEqual(self.events,[])


if __name__=='__main__':unittest.main()
