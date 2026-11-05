"""Bounded development diagnostic of real extension dialog observations."""
import concurrent.futures
import json
import plistlib
import subprocess
import time
from urllib.request import urlopen


def run(c):
    rig,call,raw,poll,check=(c[k] for k in ['rig','call','raw','poll','check'])
    tab=c['tab'];records=[];worker=None
    with urlopen('http://127.0.0.1:'+c['port']+'/json/list',timeout=5) as response:
        targets=[t for t in json.load(response) if t['type']=='service_worker' and t['url'].startswith('chrome-extension://ncbfifkjllmnkkjmomjohinigfgdocjc/')]
    assert len(targets)==1,'Diagnostic requires one exact owned extension worker'
    worker=c['cdp'].CDP(targets[0]['webSocketDebuggerUrl'])
    def trace(expression):
        return worker.call('Runtime.evaluate',expression=expression,returnByValue=True)['result'].get('value')
    trace("globalThis.__dialogProbe=[];chrome.debugger.onEvent.addListener((s,m,p)=>{if(m.startsWith('Page.javascriptDialog'))globalThis.__dialogProbe.push({method:m,type:p.type,hasBrowserHandler:p.hasBrowserHandler})});true")
    try:
        for locked in [False,True]:
            if locked:
                rig.settings()
                row=poll(lambda:rig.find('Allow approved Browser work while locked','AXCheckBox'),'locked Browser preference')
                if str(row.get('value','')).lower() not in {'1','true'}:rig.observe('action',reference=row['reference'],action='press')
                poll(lambda:rig.status()['browserWhileLocked']['enabled'],'locked Browser enabled')
                rig.close_owners();rig.owner('browser')
                tool=c['root']/'session-lock'
                subprocess.run(['xcrun','clang','-fobjc-arc','-framework','Foundation','-framework','IOKit',str(c['source']/'tests/macos/session-lock.m'),'-o',str(tool)],check=True,capture_output=True)
                subprocess.run([str(tool),'--lock'],check=True,capture_output=True)
                def observed_lock():
                    rows=plistlib.loads(subprocess.check_output(['ioreg','-a','-l','-d','1']))
                    return (rows[0] if isinstance(rows,list) else rows).get('IOConsoleLocked') is True
                poll(observed_lock,'independent OS lock')
            reference=poll(lambda:next((e['reference'] for e in call('browser.snapshot',tabId=tab)['elements'] if e.get('name')=='Increment'),None),'activation button')
            before=c['effects']['clicks'];call('browser.click',reference=reference)
            poll(lambda:c['effects']['clicks']==before+1,'independent click effect')
            active=call('browser.eval',tabId=tab,expression='navigator.userActivation.hasBeenActive')['value']
            call('browser.cdp',tabId=tab,method='Page.enable')
            call('browser.eval',tabId=tab,expression="window.onbeforeunload=()=>{navigator.sendBeacon('/beforeunload','fired');return 'prompt';};true")
            record=dict(locked=locked,activation=active,beforeunloadBefore=c['effects']['beforeunload'])
            with concurrent.futures.ThreadPoolExecutor() as pool:
                pending=pool.submit(raw,'browser.cdp',tabId=tab,method='Page.reload',timeoutMs=2000)
                try:
                    reply=pending.result(timeout=10)
                    record['reload']={k:reply.get(k) for k in ['accepted','errorCode','delivery','effect','uncertainty','data']}
                except Exception as error:record['reloadError']=getattr(error,'code',type(error).__name__)
                deadline=time.monotonic()+10;dialog=None
                while time.monotonic()<deadline:
                    try:
                        current=call('browser.dialog',tabId=tab);record['observer']=current
                        dialog=current.get('dialog')
                    except Exception as error:
                        record['observerError']=getattr(error,'code',type(error).__name__);break
                    if dialog:break
                    time.sleep(.2)
                if dialog:call('browser.dialog',tabId=tab,action='dismiss',dialogId=dialog['id'])
            record.update(beforeunloadAfter=c['effects']['beforeunload'],events=trace('globalThis.__dialogProbe'))
            records.append(record)
            c['report'].write_text(json.dumps(dict(passed=False,diagnostic=True,records=records),indent=2))
            print('DIALOG_PROBE '+json.dumps(record),flush=True)
            assert not record.get('observerError'),'Dialog discovery refused while reload pending'
            if dialog:check(('locked' if locked else 'unlocked')+' real beforeunload is observed and dismissed')
            else:
                call('browser.eval',tabId=tab,expression='window.onbeforeunload=null;true')
                call('browser.navigate',tabId=tab,url=c['url'])
        assert all(r['observer'].get('dialog') for r in records),'Real beforeunload was not observed in both states'
        c['report'].write_text(json.dumps(dict(passed=True,diagnostic=True,checks=len(records),records=records)))
    finally:
        if worker is not None:worker.close()
