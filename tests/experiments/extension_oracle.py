"""Observe an installed extension; never install, enable or flush it here."""
from __future__ import annotations

import json
from pathlib import Path
import time
import urllib.request


def registration(root):
    """Chrome writes preferences asynchronously after a successful UI load."""
    try:
        settings=json.loads((root/'cft-profile/Default/Secure Preferences').read_text())['extensions']['settings']
        enabled=any(v.get('path')==str(root/'probe-ext') and v.get('state') in (None,1)
                    and not v.get('disable_reasons') for v in settings.values())
        return {'readable':True,'enabled':enabled}
    except (OSError,ValueError,KeyError,TypeError,AttributeError):
        return {'readable':False,'enabled':False}


def poll(registry, behavior, *, timeout=30, clock=time.monotonic, sleep=time.sleep):
    start=clock()
    first=None
    attempts=0
    while True:
        state=registry()
        if first is None:
            first=state['enabled']
        observed=behavior()
        attempts+=1
        passed=state['enabled'] and observed
        if passed or clock()-start>=timeout:
            # A behavior/registration disagreement is inconclusive, not evidence
            # that the agent failed to install the extension.
            available=state['readable'] and not (observed and not state['enabled'])
            return {'passed':passed,'verifierAvailable':available,
                    'detail':('enabled extension changed the fresh fixture page' if passed else
                              'extension verifier inconclusive' if not available else
                              'extension registration or behavior absent'),
                    'registeredAtStart':first,'registeredEnabled':state['enabled'],
                    'preferencesReadable':state['readable'],'behaviorObserved':observed,
                    'polls':attempts,'verificationSeconds':clock()-start}
        sleep(min(.25,max(0,timeout-(clock()-start))))


def read_json(url, method='GET'):
    with urllib.request.urlopen(urllib.request.Request(url,method=method),timeout=5) as response:
        return json.load(response)


def main():
    root=Path.home()/'experiment'
    try:
        expected=(root/'extension-expected.txt').read_text()
        tab=read_json('http://127.0.0.1:9223/json/new?http://127.0.0.1:9225/','PUT')['id']
        result=poll(lambda:registration(root),lambda:any(
            p.get('id')==tab and p.get('title')==expected
            for p in read_json('http://127.0.0.1:9223/json')))
    except (OSError,ValueError,KeyError,TypeError,AttributeError):
        result={'passed':False,'verifierAvailable':False,'detail':'extension verifier unavailable'}
    print(json.dumps(result))
    return 0 if result['verifierAvailable'] else 1


if __name__=='__main__':
    raise SystemExit(main())
