"""Benign correctness checks for owned loopback recovery and retained evidence."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from separate_processes import Worker,study,verify_records


class SeparateProcesses(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.summary,cls.raw=study()

    def test_native_recovery_and_replay(self):
        self.assertTrue(verify_records(self.summary,self.raw))
        self.assertEqual(self.summary['postcompletion_checks'],20)

    def test_summary_tamper_rejects(self):
        summary=copy.deepcopy(self.summary);summary['postcompletion_checks']=19
        with self.assertRaises(ValueError):verify_records(summary,self.raw)

    def test_snapshot_tamper_rejects(self):
        raw=copy.deepcopy(self.raw)
        row=next(x for x in raw['rpc'] if x['phase']=='late-descendants' and x['request']['op']=='use')
        row['answer']['allow']=True
        with self.assertRaises(ValueError):verify_records(self.summary,raw)

    def test_process_alias_rejects(self):
        raw=copy.deepcopy(self.raw)
        raw['worker_starts'][1]['pid']=raw['worker_starts'][0]['pid']
        with self.assertRaises(ValueError):verify_records(self.summary,raw)

    def test_missing_postcompletion_coordinate_rejects(self):
        raw=copy.deepcopy(self.raw)
        index=next(i for i,x in enumerate(raw['rpc']) if x['phase']=='late-descendants' and x['request']['op']=='use')
        raw['rpc'].pop(index)
        with self.assertRaises(ValueError):verify_records(self.summary,raw)

    def test_worker_rejects_invalid_clock_and_stays_usable(self):
        with tempfile.TemporaryDirectory() as tmp:
            worker=Worker(Path(tmp)/'gateway.sqlite',0)
            try:
                for clock in (-1,True,'21'):
                    with self.assertRaises(ValueError):worker.rpc({'op':'ingest','clock':clock,'events':[]})
                self.assertIsInstance(worker.rpc({'op':'stats'}),dict)
            finally:worker.close()


if __name__=='__main__':unittest.main()
