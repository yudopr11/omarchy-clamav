"""Bounded fixture logs; no services or real user state are changed."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class MonitorTests(unittest.TestCase):
    def sample(self, log):
        with tempfile.TemporaryDirectory(dir=ROOT / 'tests') as folder:
            home = Path(folder)
            state = home / '.local/state/omarchy'
            state.mkdir(parents=True)
            (state / 'clamav-detections.log').write_text(log)
            fakebin = home / 'bin'
            fakebin.mkdir()
            systemctl = fakebin / 'systemctl'
            systemctl.write_text('#!/bin/sh\nprintf "inactive\\n"\nexit 3\n')
            systemctl.chmod(0o755)
            result = subprocess.run(['bash', str(ROOT / 'bin/status.sh')], capture_output=True, text=True,
                                    env=dict(os.environ, HOME=folder, PATH=str(fakebin) + ':' + os.environ['PATH']), timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertLess(len(result.stdout), 65536)
            return json.loads(result.stdout)

    def test_recent_records_newest_first(self):
        result = self.sample(''.join(f'2026-01-01 12:00:00 /missing/file{i}: Test.Signature FOUND\n' for i in range(12)))
        self.assertEqual(len(result['recent']), 10)
        self.assertEqual(result['recent'][0]['path'], '/missing/file11')
        self.assertEqual(result['recent'][-1]['path'], '/missing/file2')
        self.assertEqual(result['activeCount'], 0)

    def test_oversized_record_is_bounded_and_following_record_retained(self):
        result = self.sample('2026-01-01 12:00:00 /' + 'x' * 1000000 + ': Huge FOUND\n'
                             + '2026-01-01 12:00:00 /missing: Safe FOUND\n')
        self.assertEqual(len(result['recent']), 1)
        self.assertEqual(result['recent'][0]['signature'], 'Safe')

    def test_malformed_records_ignored(self):
        self.assertEqual(self.sample('not a detection\n')['recent'], [])
