import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class CoverageGateTests(unittest.TestCase):
    def test_gate_requires_helper_and_strict_line_and_branch_thresholds(self):
        good = dict(num_statements=100, covered_lines=91, num_branches=100, covered_branches=91)
        for counts, helper, success in [
            (good, True, True),
            (dict(good, covered_lines=90), True, False),
            (dict(good, covered_branches=90), True, False),
            (dict(good, num_statements=0), True, False),
            (dict(good, num_branches=0), True, False),
            (good, False, False),
        ]:
            with self.subTest(counts=counts, helper=helper), tempfile.TemporaryDirectory() as folder:
                report = Path(folder) / 'coverage.json'
                report.write_text(json.dumps({'totals': counts, 'files': {
                    'scripts/omarchy-clamav-control' if helper else 'other.py': {'summary': counts}
                }}))
                result = subprocess.run([sys.executable, str(ROOT / 'tests/check_coverage.py'), str(report)],
                                        capture_output=True, text=True)
                self.assertEqual(result.returncode, 0 if success else 1, result.stderr)
                self.assertIn('coverage', result.stdout.lower())


if __name__ == '__main__':
    unittest.main()
