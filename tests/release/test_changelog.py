"""Release notes must describe the exact published version."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('changelog', Path(__file__).resolve().parents[2] / 'release/changelog.py')
changelog = importlib.util.module_from_spec(spec)
spec.loader.exec_module(changelog)


class ChangelogTests(unittest.TestCase):
    def test_missing_empty_duplicate_and_placeholder_notes_refused(self):
        cases = ['## [Unreleased]\n- Next change\n', '## [1.2.3]\n',
                 '## [1.2.3]\n- \n', '## [1.2.3]\n- TBD\n',
                 '## [1.2.3]\n```\n- Example only\n```\n',
                 '## [1.2.3]\n- Change\n## [1.2.3]\n- Duplicate\n',
                 '## [1.2.3]\n## [1.2.2]\n- Older change\n']
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'CHANGELOG.md'
            for text in cases:
                path.write_text(text)
                with self.subTest(text=text), self.assertRaises(ValueError):
                    changelog.notes('1.2.3', path)

    def test_exact_version_notes_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'CHANGELOG.md'
            path.write_text('## [Unreleased]\n- Future\n\n## [1.2.3]\n\n- Fix permissions.\n\nPreview limitations.\n\n## [1.2.2]\n- Old\n')
            self.assertEqual(changelog.notes('1.2.3', path), '- Fix permissions.\n\nPreview limitations.\n')


if __name__ == '__main__':
    unittest.main()
