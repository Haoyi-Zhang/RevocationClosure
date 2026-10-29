"""Reject inconsistent retained integrated evidence before producing a table."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from integrated_closure import verify

HERE = Path(__file__).resolve().parent
SOURCE = HERE / 'results' / 'integrated-closure'


class IntegratedEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=HERE)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.summary = deepcopy(json.loads((SOURCE / 'summary.json').read_text(encoding='utf-8')))
        for row in self.summary['cases']:
            name = f"{row['cohort']}-{row['policy']}"
            (self.root / name).mkdir()
            (self.root / name / 'inputs.json').write_bytes((SOURCE / name / 'inputs.json').read_bytes())

    def save(self):
        (self.root / 'summary.json').write_text(json.dumps(self.summary), encoding='utf-8')
        for row in self.summary['cases']:
            name = f"{row['cohort']}-{row['policy']}"
            (self.root / name / 'result.json').write_text(json.dumps(row), encoding='utf-8')

    def closed_row(self):
        return next(x for x in self.summary['cases'] if x['cohort'] == 'common' and x['policy'] == 'append')

    def test_current_individual_decisions_match_counts(self):
        self.save()
        self.assertEqual(verify(self.root)['case_count'], 6)

    def test_changed_descendant_cannot_hide_behind_saved_counters(self):
        row = self.closed_row()
        row['processes'][-1]['result']['decisions'][0]['allow'] = True
        self.save()
        with self.assertRaisesRegex(ValueError, 'decision/counter'):
            verify(self.root)

    def test_changed_control_cannot_hide_behind_saved_counters(self):
        row = self.closed_row()
        row['processes'][-1]['result']['decisions'][2]['allow'] = False
        self.save()
        with self.assertRaisesRegex(ValueError, 'decision/counter'):
            verify(self.root)

    def test_matching_forged_count_still_violates_closed_outcome(self):
        row = self.closed_row()
        row['processes'][-1]['result']['decisions'][0]['allow'] = True
        row['late_descendant_allows'] = 1
        self.save()
        with self.assertRaisesRegex(ValueError, 'authorization outcome'):
            verify(self.root)

    def test_open_case_cannot_swap_live_and_expired_gateway_outcomes(self):
        row = next(x for x in self.summary['cases'] if x['cohort'] == 'saturated' and x['policy'] == 'append')
        rows = row['processes'][-1]['result']['decisions']
        rows[0]['allow'], rows[9]['allow'] = rows[9]['allow'], rows[0]['allow']
        self.save()
        with self.assertRaisesRegex(ValueError, 'authorization outcome'):
            verify(self.root)

    def test_truthy_non_boolean_is_rejected(self):
        row = self.closed_row()
        row['processes'][-1]['result']['decisions'][2]['allow'] = 1
        self.save()
        with self.assertRaisesRegex(ValueError, 'decision types'):
            verify(self.root)

    def test_duplicate_case_cannot_preserve_reported_denominator(self):
        self.summary['cases'].append(deepcopy(self.closed_row()))
        self.save()
        with self.assertRaisesRegex(ValueError, 'case denominator'):
            verify(self.root)

    def test_duplicate_child_cannot_preserve_product_size(self):
        row = self.closed_row()
        name = f"{row['cohort']}-{row['policy']}"
        plan_path = self.root / name / 'inputs.json'
        plan = json.loads(plan_path.read_text(encoding='utf-8'))
        plan['children'][1] = deepcopy(plan['children'][0])
        plan_path.write_text(json.dumps(plan), encoding='utf-8')
        decisions = row['processes'][-1]['result']['decisions']
        for start in range(0, 15, 3):
            decisions[start+1] = deepcopy(decisions[start])
        self.save()
        with self.assertRaisesRegex(ValueError, 'decision product'):
            verify(self.root)

    def test_cli_rejects_before_overwriting_table(self):
        self.closed_row()['processes'][-1]['result']['decisions'][0]['allow'] = True
        self.save()
        table = self.root / 'table.tex'
        table.write_text('do not overwrite on failed verification', encoding='utf-8')
        run = subprocess.run([sys.executable, '-B', str(HERE/'integrated_closure.py'),
                              '--out', str(self.root), '--verify', '--table', str(table)],
                             capture_output=True, text=True, timeout=20)
        self.assertNotEqual(run.returncode, 0)
        self.assertIn('decision/counter mismatch', run.stderr)
        self.assertEqual(table.read_text(encoding='utf-8'), 'do not overwrite on failed verification')


if __name__ == '__main__':
    unittest.main()
