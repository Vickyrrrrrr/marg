"""Run named CI check groups with machine-readable results and Actions summaries."""
import argparse
import json
import os
from pathlib import Path
import py_compile
import subprocess
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
GROUPS = {
    'commercial-terms': 'test_commercial.py',
    'billing-stock': 'test_server.py',
    'pharmacy': 'test_pharmacy.py',
    'parties-invoices': 'test_parties.py',
    'payments': 'test_settlements.py',
    'financial-year': 'test_financial_year.py',
    'security': 'test_security.py',
    'recovery': 'test_recovery.py',
    'counter-checkout': 'test_checkout.py',
    'counter-recalls': 'test_workflows.py',
    'packaging': 'test_packaging.py',
}


def source_checks():
    assigned = set(GROUPS.values())
    actual = {p.name for p in (ROOT / 'tests').glob('test_*.py')}
    if assigned != actual:
        raise ValueError('Update CI test groups to cover every test module: ' + str(assigned ^ actual))
    package = json.loads((ROOT / 'package.json').read_text())
    lock = json.loads((ROOT / 'package-lock.json').read_text())['packages']['']
    for key in ('name', 'version', 'dependencies', 'devDependencies', 'optionalDependencies'):
        if package.get(key) != lock.get(key):
            raise ValueError('package.json and package-lock.json disagree on ' + key)
    scripts = sorted((ROOT / 'app').glob('*.js')) + sorted((ROOT / 'desktop').glob('*.cjs'))
    for path in scripts:
        subprocess.run(['node', '--check', str(path)], check=True, cwd=ROOT)
    python = [p for folder in ('backend', 'scripts', 'tests') for p in (ROOT / folder).glob('*.py')]
    for path in python:
        py_compile.compile(str(path), doraise=True)
    return {'javascript_files': len(scripts), 'python_files': len(python), 'test_modules': len(actual)}


def run(group, directory):
    start = time.monotonic()
    report = {'group': group, 'status': 'failed'}
    try:
        if group == 'source':
            report.update(source_checks())
            report['status'] = 'passed'
        else:
            suite = unittest.defaultTestLoader.discover(str(ROOT / 'tests'), pattern=GROUPS[group])
            result = unittest.TextTestRunner(verbosity=2).run(suite)
            report.update(tests=result.testsRun, failures=[{'test': t.id(), 'trace': trace} for t, trace in result.failures],
                          errors=[{'test': t.id(), 'trace': trace} for t, trace in result.errors],
                          skipped=[{'test': t.id(), 'reason': reason} for t, reason in result.skipped],
                          expected_failures=len(result.expectedFailures), unexpected_successes=len(result.unexpectedSuccesses))
            if result.testsRun and result.wasSuccessful() and not result.skipped and not result.expectedFailures:
                report['status'] = 'passed'
    except Exception as error:
        report['error'] = str(error)
    report['seconds'] = round(time.monotonic() - start, 3)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / (group + '.json')).write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    summary = os.environ.get('GITHUB_STEP_SUMMARY')
    if summary:
        with open(summary, 'a', encoding='utf-8') as output:
            output.write(f"### {group}\n\nStatus: **{report['status']}** · {report.get('tests', 'source')} checks · {report['seconds']} seconds\n\n")
    print(json.dumps({k: report[k] for k in ('group', 'status', 'seconds')}), flush=True)
    return report['status'] == 'passed'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--group', choices=['all', 'source', *GROUPS], required=True)
    parser.add_argument('--report-dir', type=Path, default=ROOT / 'reports')
    args = parser.parse_args()
    groups = ['source', *GROUPS] if args.group == 'all' else [args.group]
    results = [run(group, args.report_dir) for group in groups]
    return 0 if all(results) else 1


if __name__ == '__main__':
    raise SystemExit(main())
