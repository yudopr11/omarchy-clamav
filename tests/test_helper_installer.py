"""Exercise explicit helper setup with fake sudo, never live elevation."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class HelperInstallerTests(unittest.TestCase):
    def test_sudo_arguments_and_result_from_path_with_spaces(self):
        for code in (0, 7):
            with self.subTest(code=code), tempfile.TemporaryDirectory() as folder:
                base = Path(folder)
                plugin = base / 'plugin with spaces'
                (plugin / 'bin').mkdir(parents=True)
                shutil.copyfile(ROOT / 'bin/install-helper.sh', plugin / 'bin/install-helper.sh')
                fake = base / 'sudo'
                fake.write_text('#!/usr/bin/env python3\n'
                                'import json, os, sys\n'
                                'print(json.dumps(sys.argv[1:]))\n'
                                'sys.exit(int(os.environ["INSTALL_RESULT"]))\n')
                fake.chmod(0o755)
                result = subprocess.run(['bash', str(plugin / 'bin/install-helper.sh')],
                                        cwd=base, input='\n', text=True, capture_output=True,
                                        env=dict(os.environ, PATH=folder + ':' + os.environ['PATH'],
                                                 INSTALL_RESULT=str(code)))
                self.assertEqual(result.returncode, code)
                self.assertIn(json.dumps(['bash', str(plugin / 'scripts/install-helper.sh')]), result.stdout)
                self.assertIn('No services or ClamAV configuration will be changed', result.stdout)
                self.assertIn('Press Enter to close', result.stdout)
                self.assertIn('Helper installer exit code: ' + str(code), result.stdout)
                self.assertIn('completed' if code == 0 else 'failed', result.stdout)
