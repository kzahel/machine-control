"""A matching Mach-O UUID alone must never qualify an empty dSYM."""
import hashlib
import importlib.util
import json
from pathlib import Path
import plistlib
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('macos_symbols',
    Path(__file__).resolve().parents[2] / 'desktop/scripts/macos-symbols.py')
symbols = importlib.util.module_from_spec(spec)
spec.loader.exec_module(symbols)


class Symbols(unittest.TestCase):
    def test_final_identity_and_real_debug_information_required(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            app, output = root / 'App', root / 'Symbols'
            (app / 'Contents').mkdir(parents=True)
            info = {'MCSourceRevision': 'a' * 40, 'CFBundleShortVersionString': '0.6.9'}
            (app / 'Contents/Info.plist').write_bytes(plistlib.dumps(info))
            manifest = {'schema': 'machine-control-macos-symbols/v0',
                        'sourceRevision': 'a' * 40, 'version': '0.6.9', 'images': {}}
            identity = [['00000000-0000-4000-8000-000000000000', 'arm64']]
            for name in symbols.BINARIES:
                dwarf = output / (name + '.dSYM') / 'Contents/Resources/DWARF' / name
                dwarf.parent.mkdir(parents=True)
                dwarf.write_bytes(b'debug information')
                manifest['images'][name] = {'uuids': identity,
                    'sha256': hashlib.sha256(dwarf.read_bytes()).hexdigest()}
            (output / 'symbols.json').write_text(json.dumps(manifest))
            with patch.object(symbols, 'uuids', return_value=identity), patch.object(
                    symbols.subprocess, 'check_output', return_value='DW_TAG_compile_unit') as dump:
                symbols.verify(app, output)
                dump.return_value = 'empty debug info'
                with self.assertRaisesRegex(ValueError, 'Empty debug information'):
                    symbols.verify(app, output)
                dump.return_value = 'DW_TAG_compile_unit'
                with patch.object(symbols, 'uuids', return_value=[['other', 'arm64']]):
                    with self.assertRaisesRegex(ValueError, 'UUIDs'):
                        symbols.verify(app, output)
                dwarf.write_bytes(b'changed')
                with self.assertRaisesRegex(ValueError, 'Changed symbol data'):
                    symbols.verify(app, output)
                manifest['sourceRevision'] = 'b' * 40
                (output / 'symbols.json').write_text(json.dumps(manifest))
                with self.assertRaisesRegex(ValueError, 'source/version'):
                    symbols.verify(app, output)


if __name__ == '__main__':
    unittest.main()
