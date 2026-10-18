"""On-phone data acceptance under the real YA app UID; no ADB in this path."""
import base64
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import sys
import time

from session import AndroidTransport, Worker


def run():
    expected = json.loads(Path('expected.json').read_text())
    phase = Path('phase').read_text().strip()
    uid = int(next(s for s in Path('/proc/self/status').read_text().splitlines() if s.startswith('Uid:')).split()[1])
    assert uid >= 10000
    workers = [Worker({'receipt':str(Path('bridge.json').resolve())}, timeout=15,
        command=[sys.executable,str(Path('session.py').resolve()),'--worker']) for _ in range(2)]
    reports = []
    def code(index, source):
        result = workers[index].request({'code':source})
        reports.append(result)
        assert not result['isError'], result
        return result
    def wait(name):
        Path('await-'+name).write_text('ready')
        deadline = time.monotonic()+60
        while not Path('done-'+name).exists():
            assert time.monotonic() < deadline, 'Controller did not '+name
            time.sleep(.1)
    try:
        # Both workers keep open, authenticated connections, independent namespaces.
        with ThreadPoolExecutor(2) as pool:
            results = [pool.submit(code,i,f"remembered = {i}; photos = phone.photos(); roots = phone.roots(); assert photos[0]['available'] and roots[0]['available']") for i in range(2)]
            for result in results: result.result()
        for i in range(2):
            code(i,f"assert remembered == {i}; capabilities = mc.call({{'operation':'open'}})['data']; assert capabilities['concurrentReaders'] and not capabilities['uiClaim']; photo = photos[0]['id']; root = roots[0]['id']; doc = next(x['id'] for x in phone.list(root)['items'] if x['name'] == 'proof.txt')")
            code(i,f"import hashlib; assert hashlib.sha256(phone.read(photo)).hexdigest() == {expected['photoHash']!r}; assert hashlib.sha256(phone.read(doc)).hexdigest() == {expected['docHash']!r}")
        code(0,f"phone.export(photo, 'export-{phase}.png'); phone.export(doc, 'export-{phase}.txt')")
        thumbnail = code(0,"phone.thumbnail(photo)")
        png = base64.b64decode(next(c['data'] for c in thumbnail['content'] if c['type']=='image'))
        assert png.startswith(b'\x89PNG\r\n\x1a\n')
        Path('thumbnail-'+phase+'.png').write_bytes(png)
        code(0,"try:\n phone.export(doc, 'export-"+phase+".txt')\n raise AssertionError('Export overwrote file')\nexcept FileExistsError:\n pass")
        code(0,"bad = mc.transport.call({'operation':'data.read','id':'content://media/external/images/media/1'}); assert bad['errorCode'] == 'stale_data_reference'; bad = mc.transport.call({'operation':'data.write','id':doc,'text':'WRONG'}); assert bad['errorCode'] == 'unsupported_operation'")
        workers[0].close()
        code(1,"assert phone.read(doc); assert phone.read(photo)")
        if phase == 'restart':
            wait('revoke-tree')
            code(1,"bad = mc.transport.call({'operation':'data.read','id':doc}); assert bad['errorCode'] == 'permission_revoked'; assert phone.read(photo); assert phone.roots()[0]['available'] is False")
            wait('revoke-photo')
            code(1,"bad = mc.transport.call({'operation':'data.read','id':photo}); assert bad['errorCode'] == 'permission_revoked'; assert phone.photos()[0]['available'] is False")
            wait('stop')
            result = workers[1].request({'code':'phone.photos()'})
            assert result['isError'] and workers[1].closed, result
            try:
                AndroidTransport(Path('bridge.json'))
                raise AssertionError('Stopped data bridge admitted old receipt')
            except Exception as error:
                assert getattr(error,'code','') in ('bridge_lost','approval_denied') or isinstance(error,OSError), error
        Path('data-witness-'+phase+'.json').write_text(json.dumps({
            'appUid':uid,'phase':phase,'independentReaders':2,'namespaceIsolation':True,
            'closingOneReaderPreservesOther':True,'selectedPhotoHashVerified':True,
            'safDocumentHashVerified':True,'linuxExportVerified':True,'inlineThumbnail':True,
            'arbitraryUriRefused':True,'writesRefused':True,'uiClaim':False,
            'liveRevocationVerified':phase=='restart','adbInOperationPath':False},indent=2)+'\n')
        for report in reports: report['content']=[c for c in report['content'] if c['type']!='image']
        Path('data-snippets-'+phase+'.json').write_text(json.dumps(reports,indent=2)+'\n')
    finally:
        for worker in workers: worker.close()


if __name__ == '__main__': run()
