"""Gate raw coverage counts, not the rounded combined percentage."""
import json
from pathlib import Path
import sys


def main(path):
    report = json.loads(Path(path).read_text())
    helper = report['files'].get('scripts/omarchy-clamav-control')
    if not helper:
        print('Coverage failed: extensionless helper missing')
        return 1
    passed = True
    for name, counts in [('TOTAL', report['totals']),
                         ('scripts/omarchy-clamav-control', helper['summary'])]:
        for label, covered, total in [('line', 'covered_lines', 'num_statements'),
                                      ('branch', 'covered_branches', 'num_branches')]:
            numerator, denominator = counts[covered], counts[total]
            ok = denominator > 0 and numerator * 100 > denominator * 90
            print(f'{name} {label} coverage: {numerator}/{denominator} ' +
                  (f'({100 * numerator / denominator:.2f}%)' if denominator else '(empty)'))
            passed = passed and ok
    return 0 if passed else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1]))
