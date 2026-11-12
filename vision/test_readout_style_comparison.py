import json,tempfile,unittest
from pathlib import Path
from compare_readout_styles import compare

class StyleComparisonTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
    def experiment(self,name,blocked=2):
        root=self.root/name;root.mkdir()
        manifest=dict(plan=[['123','00123']],frames_per_setting=6,character_sha256='frozen',v5_sha256={'hdg':'a','alt':'b'},gate={'confidence':.5,'stable_frames':3},candidate_score_threshold=.75,yolo_imgsz=640,localizer_sha256='frozen',raw_jpeg_quality=70)
        (root/'manifest.json').write_text(json.dumps(manifest))
        rows=[]
        for i in range(6):
            row=dict(truth={'hdg':'123','alt':'00123'},models={})
            if i>=blocked:row['models']['character']={k:{'value':v} for k,v in row['truth'].items()}
            rows.append(row)
        (root/'frames.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
        metric=dict(scheduled=6,cropped=6-blocked,all_frame_raw_exact_accuracy=(6-blocked)/6,all_frame_accepted_exact_accuracy=(6-blocked)/6,accepted_accuracy=1.)
        (root/'summary.json').write_text(json.dumps(dict(results={'character':{'hdg':metric,'alt':metric}})))
        return root
    def test_same_model_same_plan_and_scores_can_be_kept(self):
        result=compare(self.experiment('before'),self.experiment('after'))
        self.assertTrue(result['keep_candidate']);self.assertEqual(len(result['checks']),12)
    def test_reduced_coverage_is_rejected_even_with_perfect_accepted_accuracy(self):
        result=compare(self.experiment('before'),self.experiment('after',3))
        self.assertFalse(result['keep_candidate'])
        self.assertTrue(any(not r['nondecreasing'] for r in result['checks'] if r['metric']=='crop_coverage'))
    def test_unchanged_low_performance_cannot_pass_requested_minimum(self):
        result=compare(self.experiment('before'),self.experiment('after'),min_exact=.9)
        self.assertFalse(result['keep_candidate'])
        self.assertTrue(any(not r['nondecreasing'] for r in result['checks'] if r['metric']=='minimum_all_frame_exact'))

    def test_incomplete_capture_or_changed_safety_cannot_be_compared(self):
        before=self.experiment('before');after=self.experiment('after')
        path=after/'frames.jsonl';path.write_text('\n'.join(path.read_text().splitlines()[:-1])+'\n')
        with self.assertRaisesRegex(ValueError,'Incomplete'):compare(before,after)
        manifest=json.loads((after/'manifest.json').read_text());manifest['gate']['confidence']=.4
        (after/'manifest.json').write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError,'Unpaired'):compare(before,after)

if __name__=='__main__':unittest.main()
