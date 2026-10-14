"""Exercise the actual menu verifier against independent file outcomes."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


class MenuOracleTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.home = Path(self.directory.name)
        self.root = self.home / 'experiment'
        (self.root / 'out').mkdir(parents=True)
        self.source = self.root / 'menu-source.rtf'
        self.source.write_bytes(br'{\rtf1\ansi\b Menu conversion fixture\b0}')
        self.output = self.root / 'out/menu-note.txt'
        self.output.write_text('Menu conversion complete\n')
        script = (Path(__file__).parent / 'tasks/textedit-menu/oracle.sh').read_text()
        self.code = script.split("<<'PY'\n", 1)[1].rsplit('\nPY', 1)[0]

    def verdict(self):
        output = io.StringIO()
        with patch('pathlib.Path.home', return_value=self.home), contextlib.redirect_stdout(output):
            exec(compile(self.code, 'textedit-menu/oracle.sh', 'exec'), {})
        return json.loads(output.getvalue())['passed']

    def test_correct_output_and_intact_source_pass(self):
        self.assertTrue(self.verdict())

    def test_missing_source_is_a_failed_effect_not_a_verifier_error(self):
        self.source.unlink()
        self.assertFalse(self.verdict())

    def test_wrong_source_type_fails(self):
        self.source.unlink(); self.source.mkdir()
        self.assertFalse(self.verdict())

    def test_changed_source_fails(self):
        self.source.write_text('changed')
        self.assertFalse(self.verdict())

    def test_rich_text_output_fails(self):
        self.output.write_bytes(br'{\rtf1\ansi Menu conversion complete}')
        self.assertFalse(self.verdict())

    def test_missing_output_fails(self):
        self.output.unlink()
        self.assertFalse(self.verdict())


if __name__ == '__main__':
    unittest.main()
