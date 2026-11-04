"""Native callback identity and presentation state, never admission policy."""
import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('notification_state',Path(__file__).resolve().parents[2]/'desktop/native/linux/notification_state.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


class NotificationTests(unittest.TestCase):
    def setUp(self):
        self.sent=[];self.closed=[];self.events=[];self.shown=[]
        self.next_id=6
        def notify(identifier,*fields):
            self.sent.append((identifier,*fields))
            if not identifier:self.next_id+=1
            return identifier or self.next_id
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
        self.notice.action(':1.42',self.notice.identifier,self.token())
        self.assertEqual(self.events,[('intent.approve',{'intentId':'task'})])
    def test_decisions_do_not_replay_and_stop_remains_immediate(self):
        token=self.token()
        for _ in range(2):self.notice.action(':1.42',7,token)
        for _ in range(2):self.notice.action(':1.42',7,'stop')
        self.assertEqual([method for method,_ in self.events],['intent.approve','stop'])
    def test_changed_buttons_rotate_callbacks_even_when_task_state_is_same(self):
        old=self.token()
        self.notice.update('ask','Machine Control','Reason',[
            ('Pause all 30 seconds','pause',{'duration':30}),('Stop all access','stop',{})],
            'task','waiting_for_approval')
        self.notice.action(':1.42',7,old);self.assertEqual(self.events,[])
        self.notice.action(':1.42',self.notice.identifier,self.token())
        self.assertEqual(self.events,[('pause',{'duration':30})])
    def test_late_close_cannot_defer_a_replaced_notification_generation(self):
        old=self.notice.identifier;self.update('announcing')
        self.assertNotEqual(old,self.notice.identifier)
        self.notice.closed(':1.42',old,2)
        self.assertEqual(self.events,[]);self.assertEqual(self.closed,[old])
    def test_dismissing_paused_status_keeps_timed_retry_presentable(self):
        self.notice.update('paused','Machine Control','Paused',self.choices,'task','paused')
        self.notice.closed(':1.42',self.notice.identifier,2)
        self.assertTrue(self.notice.acknowledged());self.assertEqual(self.events,[])
        self.notice.update('retry','Machine Control','Warning',self.choices,'task','announcing')
        self.assertTrue(self.notice.identifier);self.assertTrue(self.notice.acknowledged())
        self.notice.withdraw();self.assertFalse(self.notice.acknowledged())
    def test_visible_open_controls_action_grants_no_authority(self):
        self.notice.update('active','Machine Control','Reason',[
            ('Open task controls','panel.show',{}),('Stop all access','stop',{})],
            'task','active')
        self.notice.action(':1.42',self.notice.identifier,self.token())
        self.assertEqual(self.shown,[True]);self.assertEqual(self.events,[])
    def test_hiding_open_panel_restores_banner_before_late_old_close(self):
        old=self.notice.identifier
        self.notice.action(':1.42',old,'default')
        self.notice.closed(':1.42',old,2)
        self.assertFalse(self.notice.acknowledged())
        self.notice.return_to_banner();self.update()
        self.assertTrue(self.notice.acknowledged())
        self.assertNotEqual(old,self.notice.identifier)
        self.notice.closed(':1.42',old,2)
        self.assertEqual(self.events,[])
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
        self.assertEqual(self.closed,[8]);self.assertEqual(self.events,[])


class PresentationTests(unittest.TestCase):
    def test_imminent_browser_warning_is_not_hidden_by_desktop_approval(self):
        ask=dict(state='waiting_for_approval',surfaces=['desktop'])
        automatic=dict(state='announcing',surfaces=['browser'])
        self.assertIs(module.primary_request([ask,automatic]),automatic)
    def test_concurrent_surface_warnings_keep_each_remaining_countdown(self):
        desktop=dict(state='announcing',surfaces=['desktop'],noticeRemainingSeconds=3,reason='Desktop task')
        browser=dict(state='announcing',surfaces=['browser'],noticeRemainingSeconds=8.2,reason='Browser task')
        selected=module.primary_request([desktop,browser])
        self.assertEqual(module.other_announcements([desktop,browser],selected),['Also starting browser in 9 seconds: Browser task'])


if __name__=='__main__':unittest.main()
