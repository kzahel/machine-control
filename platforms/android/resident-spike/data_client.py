"""Read-only selected-photo/document handles over the shared native data plane."""
import base64
from pathlib import Path


class PhoneData:
    def __init__(self, session):
        self.session = session

    def photos(self):
        return self.session.call({'operation':'data.photos'})['data']['items']

    def roots(self):
        return self.session.call({'operation':'data.roots'})['data']['items']

    def list(self, directory):
        return self.session.call({'operation':'data.list','id':directory})['data']

    def read(self, handle):
        result = self.session.call({'operation':'data.read','id':handle})['data']
        value = base64.b64decode(result['base64'],validate=True)
        if len(value) != result['size']:
            raise ValueError('Native data size mismatch')
        return value

    def export(self, handle, path):
        value = self.read(handle)
        with Path(path).open('xb') as output:
            output.write(value)
        return {'path':str(path),'bytes':len(value)}

    def thumbnail(self, handle):
        result = self.session.call({'operation':'data.thumbnail','id':handle})
        self.session.emit_image(self.session.transport.image(result))
        return 'Selected photo thumbnail attached'
