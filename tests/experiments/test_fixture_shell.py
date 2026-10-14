"""Reject shell parse warnings, including silently unterminated here-docs."""
from pathlib import Path
import subprocess
import unittest


class FixtureShellTest(unittest.TestCase):
    def test_all_task_scripts_parse_without_warnings(self):
        for script in (Path(__file__).parent / 'tasks').rglob('*.sh'):
            with self.subTest(script=script):
                result=subprocess.run(['bash','-n',str(script)],capture_output=True,text=True)
                self.assertEqual(result.returncode,0,result.stderr)
                self.assertEqual(result.stderr,'')


if __name__=='__main__':unittest.main()
