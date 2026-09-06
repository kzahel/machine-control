#!/usr/bin/env python3
"""Run on the target: enable the built-in desktop provider in the active profile."""
import http.client
import json
import time

import cdp


def browser_connection():
    connection = http.client.HTTPConnection('127.0.0.1', 9222, timeout=10)
    try:
        connection.request('GET', '/json/version')
        return cdp.CDP(json.loads(connection.getresponse().read())['webSocketDebuggerUrl'])
    finally:
        connection.close()


def main():
    try:
        cdp.desktop_tree(max_depth=1)
        print('Desktop accessibility is already available.')
        return
    except Exception:
        pass
    browser = browser_connection()
    created = None
    settings = None
    before = {t['id'] for t in cdp.list_targets()}
    try:
        candidates = [t for t in cdp.list_targets() if t.get('url', '').startswith('chrome://os-settings')]
        if not candidates:
            try:
                created = browser.call('Target.createTarget', url='chrome://os-settings/manageAccessibility')['targetId']
            except RuntimeError:
                # ChromeOS can open the Settings system app while reporting
                # that no browser tab was created. Observe the resulting app.
                pass
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                candidates = [t for t in cdp.list_targets() if t.get('url', '').startswith('chrome://os-settings')]
                if candidates:
                    break
                time.sleep(0.5)
        if not candidates:
            raise RuntimeError('ChromeOS Settings did not open. Sign in to the ChromeOS profile and rerun setup.')
        target = candidates[0]
        settings = target['id'] if target['id'] not in before else None
        page = cdp.CDP(target['webSocketDebuggerUrl'])
        try:
            deadline = time.monotonic() + 20
            while True:
                ready = page.call('Runtime.evaluate',
                                  expression="typeof chrome.settingsPrivate?.setPref === 'function'",
                                  returnByValue=True)
                if ready.get('result', {}).get('value') is True:
                    break
                if time.monotonic() >= deadline:
                    raise RuntimeError('ChromeOS Settings API did not become ready. Rerun setup.')
                time.sleep(0.5)
            expression = """new Promise(resolve => chrome.settingsPrivate.setPref(
                'settings.a11y.select_to_speak', true, '',
                ok => resolve({ok, error: chrome.runtime.lastError?.message})))"""
            result = page.call('Runtime.evaluate', expression=expression, awaitPromise=True, returnByValue=True)
            if not result.get('result', {}).get('value', {}).get('ok'):
                raise RuntimeError('Could not enable Select-to-speak: ' + json.dumps(result))
        finally:
            page.close()
        deadline = time.monotonic() + 20
        while True:
            try:
                cdp.desktop_tree(max_depth=1)
                break
            except Exception:
                if time.monotonic() >= deadline:
                    raise RuntimeError('Select-to-speak was enabled but the desktop provider is unavailable.')
                time.sleep(0.5)
        print('Select-to-speak enabled; desktop accessibility verified.')
    finally:
        for target_id in {created, settings} - {None}:
            try:
                browser.call('Target.closeTarget', targetId=target_id)
            except Exception:
                pass
        browser.close()


if __name__ == '__main__':
    main()
