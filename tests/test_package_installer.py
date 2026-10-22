"""Exercise the terminal installer with a fake Omarchy command, never pacman."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class PackageInstallerTests(unittest.TestCase):
    def test_uses_omarchy_and_preserves_failure(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'tests') as folder:
            fake = Path(folder) / 'omarchy'
            fake.write_text('#!/bin/bash\nprintf "%s\\n" "$*"\nexit 7\n')
            fake.chmod(0o755)
            result = subprocess.run(['bash', str(ROOT / 'bin/install-clamav.sh')],
                                    input='\n', text=True, capture_output=True,
                                    env=dict(os.environ, PATH=folder + ':' + os.environ['PATH']))
            self.assertEqual(result.returncode, 7)
            self.assertIn('pkg add clamav', result.stdout)
            self.assertIn('Installer exit code: 7', result.stdout)
