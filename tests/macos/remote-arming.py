"""Composed packaged recovery checks; invoked only in the claimed VirtualMac.

Uses the independent standing observer to operate the actual native Settings.
No approval hook or secret appears on the resident's agent endpoint.
"""
import concurrent.futures
import hashlib
import json
import os
import plistlib
import subprocess
import time


def _run(context):
    raw, call, check, poll, exchange = (context[k] for k in ['raw', 'call', 'check', 'poll', 'exchange'])
    observer, pid, resident, tab, url, effects = (context[k] for k in ['observer', 'pid', 'resident', 'tab', 'url', 'effects'])
    assert observer

    def tree(query='', target=None):
        result = exchange(observer, 'snapshot', target=str(target or context['pid']), query=query,
                          projection='full', maxDepth=40, maxElements=2000, provider='macos-native')
        assert result.get('accepted'), result.get('errorCode')
        return result['data']['elements']

    def find(label, role=None):
        matches = [e for e in tree(label) if e.get('label') == label and (not role or e.get('role') == role)]
        return matches[0] if len(matches) == 1 else None

    def press(label, role=None):
        element = poll(lambda: find(label, role), 'operator control ' + label)
        result = exchange(observer, 'action', reference=element['reference'], action='press', provider='macos-native')
        assert result.get('accepted'), (label, result.get('errorCode'))

    def toggle(label):
        element = poll(lambda: find(label, 'AXCheckBox'), 'operator checkbox ' + label)
        if str(element.get('value', '')).lower() not in {'1', 'true'}:
            result = exchange(observer, 'action', reference=element['reference'], action='press', provider='macos-native')
            assert result.get('accepted'), label

    from pathlib import Path
    endpoint = Path.home() / 'Library/Application Support/MachineControl/control.sock'
    subprocess.run([str(resident), 'serve', str(endpoint), '--settings'],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
    call('grant.revoke')
    assert context['disposable'], 'Locked trials require an explicitly disposable workspace'
    covered = None
    if context['covered_recovery']:
        import importlib.util
        spec = importlib.util.spec_from_file_location('covered_recovery', context['source_root'] / 'tests/macos/covered-recovery.py')
        covered = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(covered)
        context['covered_module'] = covered
        context.update(press=press, toggle=toggle, tree=tree)
        covered.prepare(context)
    press('Access', 'AXButton')
    for label in ['View desktop', 'Control apps and input', 'Browser tabs', 'Browser scripts and DevTools']:
        toggle(label)
    result = exchange(observer, 'application.activate', target=str(context['pid']), provider='macos-native')
    assert result.get('accepted'), result.get('errorCode')
    press('Access duration', 'AXPopUpButton')
    # WebKit's native select popup is not always in the app's AX subtree.
    # Its focused popup accepts targeted keyboard selection; verify the actual
    # grant lifetime below instead of inferring success from key delivery.
    # Keep the independent appliance compatible with the already qualified
    # U-prefixed menu selection; older observers do not implement End.
    for key in ['u', 'enter']:
        result = exchange(observer, 'input.key', target=str(pid), key=key, provider='macos-native')
        assert result.get('accepted'), result.get('errorCode')
    press('Enable access', 'AXButton')
    grant = poll(lambda: call('grant.status').get('grant'), 'standing operator grant')
    check('native operator arms until-stopped access', grant['lifetime'] == 'until_stopped')
    if covered:
        result = exchange(observer, 'window.close', target=str(context['pid']), provider='macos-native')
        assert result.get('accepted'), result.get('errorCode')
        poll(lambda: call('status')['presentation']['settingsWebViews'] == 0, 'Settings closes before pointer fixture')
        covered.native_browser(context, 'ordinary')
        extra = call('browser.navigate',newTab=True,url=url,active=False)['tab']['tabId']
        context['browser_tab'] = extra
        try:
            covered.native_browser(context, 'ordinary-tab-switch')
        finally:
            context.pop('browser_tab',None)
        covered.launch_fixture(context)
        covered.native_fixture(context, 'ordinary')
    for clean in [True, False]:
        fixture_before = json.loads(context['fixture_state'].read_text()) if covered else None
        context['pid'] = context['restart'](clean=clean)
        def restored():
            current = call('grant.status').get('grant') or {}
            return current if current.get('lifetime') == 'until_stopped' and set(current.get('scopes', [])) == {'observe','control','browser','devtools'} else None
        grant = poll(restored, 'same-console arming restoration after ' + ('clean quit' if clean else 'crash'), timeout=45)
        check(('clean quit' if clean else 'crash') + ' restores original scopes and indefinite consent')
        if covered:
            covered.verify_saved_model(context,'clean quit' if clean else 'crash')
            fixture_after = json.loads(context['fixture_state'].read_text())
            check('native fixture receives no replay on resident restart',
                  all(fixture_after[k] == fixture_before[k] for k in ['text','keyEventCount']))
    # Minimal presentation intentionally has no Settings WebView at launch.
    subprocess.run([str(resident), 'serve', str(endpoint), '--settings'],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
    poll(lambda: call('status')['presentation']['settingsWebViews'] == 1, 'Settings after restart')
    def quiet_after_restart():
        reasons = call('grant.status')['availability']['blockingReasons']
        assert not any(reason not in {'physical_activity','activity_unknown'} for reason in reasons), reasons
        return not reasons
    poll(quiet_after_restart, 'ordinary post-restart physical quiet', timeout=45)
    original_id = grant['grantId']
    consent = Path.home() / 'Library/Application Support/MachineControl/operator-consent.json'
    context['consent_digest'] = hashlib.sha256(consent.read_bytes()).digest()
    press('Settings', 'AXButton')
    toggle('Allow approved browser access while locked')
    poll(lambda: call('status')['browserWhileLocked']['enabled'], 'locked browser preference')
    result = exchange(observer, 'window.close', target=str(context['pid']), provider='macos-native')
    assert result.get('accepted'), result.get('errorCode')
    poll(lambda: call('status')['presentation']['settingsWebViews'] == 0, 'Settings closes before covered work')
    if covered:
        assert context['fixture'].poll() is None

    lock_binary = context['root'] / 'session-lock'
    subprocess.run(['xcrun', 'clang', '-fobjc-arc', '-framework', 'Foundation', '-framework', 'IOKit',
                    str(context['source_root'] / 'tests/macos/session-lock.m'), '-o', str(lock_binary)],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def locked():
        roots = plistlib.loads(subprocess.check_output(['ioreg', '-a', '-l', '-d', '1']))
        value = (roots[0] if isinstance(roots, list) else roots).get('IOConsoleLocked')
        assert isinstance(value, bool), 'Independent native lock observation unavailable'
        return value

    subprocess.run([str(lock_binary), '--lock'], check=True, stdout=subprocess.DEVNULL)
    poll(locked, 'independently observed native lock')
    check('standing browser trial runs with the OS independently locked')
    # Real beforeunload: sticky activation comes from prior fixture clicks.
    call('browser.eval', tabId=tab, expression="window.addEventListener('beforeunload', e => { e.preventDefault(); e.returnValue = ''; }); true")
    with concurrent.futures.ThreadPoolExecutor() as pool:
        pending = pool.submit(raw, 'browser.cdp', tabId=tab, method='Page.reload')
        dialog = poll(lambda: call('browser.dialog', tabId=tab).get('dialog'), 'beforeunload dialog')
        check('typed dialog identifies beforeunload', dialog['type'] == 'beforeunload')
        other = call('browser.navigate', newTab=True, url=url, active=False)['tab']['tabId']
        check('tab discovery progresses despite a page dialog', len(call('browser.tabs')['tabs']) >= 2)
        before = effects['clicks']
        call('browser.eval', tabId=other, expression="fetch('/click', {method:'POST'}); true")
        poll(lambda: effects['clicks'] == before + 1, 'independent second-tab effect')
        check('another tab has an independent effect while a dialog blocks the first')
        stale = raw('browser.dialog', tabId=tab, action='dismiss', dialogId='stale')
        check('stale dialog handling is refused', not stale['accepted'])
        release = raw('browser.release')
        check('release refuses before abandoning an observed open dialog',
              not release['accepted'] and release['errorCode'] == 'dialog_open' and release['delivery'] == 'refused')
        current = call('browser.dialog', tabId=tab)['dialog']
        check('refused release preserves the actual dialog attachment', current['id'] == dialog['id'])
        call('browser.dialog', tabId=tab, action='dismiss', dialogId=current['id'])
        pending.result(timeout=10)  # Never replay the uncertain reload.
        call('browser.release')
        reattached = call('browser.dialog', tabId=tab)
        check('reattachment reports event readiness after dialog resolution',
              reattached['observerState'] == 'ready' and reattached['state'] == 'not_observed')
        stale = raw('browser.dialog', tabId=tab, action='dismiss', dialogId=dialog['id'])
        check('completed release fences the previous dialog identity', not stale['accepted'])
        before = effects['clicks']
        call('browser.eval', tabId=tab, expression="fetch('/click', {method:'POST'}); true", timeoutMs=3000)
        poll(lambda: effects['clicks'] == before + 1, 'independent effect after preexisting-dialog recovery')
        check('recovered original tab has a fresh independent effect')
    check('dialog recovery retains the original operator grant', call('grant.status')['grant']['grantId'] == original_id)

    # A truly unresolved CDP promise exercises the extension deadline rather
    # than relying on dialog behavior to reproduce the old queue wedge.
    with concurrent.futures.ThreadPoolExecutor() as pool:
        pending = pool.submit(raw, 'browser.eval', tabId=other, expression='new Promise(() => {})', timeoutMs=1500)
        time.sleep(.2)
        queued = pool.submit(raw, 'browser.eval', tabId=other,
                             expression="fetch('/click', {method:'POST'}); true", timeoutMs=1500)
        check('recovery discovery progresses during an unresolved command', bool(call('browser.tabs')['tabs']))
        outcome = pending.result(timeout=10)
        check('dispatched timeout reports unknown delivery', not outcome['accepted'] and outcome['delivery'] == 'unknown')
        queued_outcome = queued.result(timeout=10)
        check('abandoned queued command is refused', not queued_outcome['accepted'])
    before = effects['clicks']
    call('browser.release')
    time.sleep(.3)
    check('release does not replay abandoned work', effects['clicks'] == before)
    call('browser.eval', tabId=other, expression="fetch('/click', {method:'POST'}); true")
    poll(lambda: effects['clicks'] == before + 1, 'fresh post-release effect')
    check('browser control recovers under unchanged standing authorization', call('grant.status')['grant']['grantId'] == original_id)
    check('browser recovery leaves the OS locked', locked())
    if covered:
        context.update(locked=locked, original_id=original_id, browser_tab=other)
        covered.run(context)
    if not covered:
        check('browser-only qualification leaves the disposable OS locked', locked())
        return
    subprocess.run([str(resident), 'serve', str(endpoint), '--settings'],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
    # The operator's Stop, unlike agent cleanup, must erase arming.
    press('Access', 'AXButton')
    press('Stop access', 'AXButton')
    poll(lambda: call('grant.status')['grant'] is None, 'operator Stop')
    check('operator Stop remains authoritative', not raw('browser.tabs')['accepted'])
    poll(locked,'operator Stop independently relocks',timeout=45)
    check('operator Stop ends covered use and independently relocks')
    context['check_stop_lock'] = False
    context['pid'] = context['restart'](clean=True, use_lifecycle=True)
    # The console is now genuinely locked, so a newly created WebView need not
    # expose its DOM to AX. Check durable native choices here; the separate
    # unlocked/cold-boot runner verifies visible controls after Stop/relaunch.
    saved = json.loads(consent.read_text())
    check('native choices retain all four scopes after protected Stop and relaunch',
          set(saved['accessChoices']['scopes']) == {'observe','control','browser','devtools'})
    check('native indefinite choice survives protected Stop and relaunch', saved['accessChoices']['duration'] is None)
    check('remembering choices does not rearm after Stop', call('grant.status')['grant'] is None)


def run(context):
    try:
        _run(context)
        if context.get('check_stop_lock'):
            context['poll'](context['locked'], 'operator Stop independently relocks', timeout=45)
            context['check']('operator Stop ends covered use and independently relocks')
        if context.get('qualification'):
            return dict(context['qualification'],
                        coveredDurationSeconds=context.get('qualified_duration', 0),
                        renewableOwnerSeconds=context.get('qualified_renewal', 0))
    finally:
        if context.get('covered_module'):
            context['covered_module'].cleanup(context)
