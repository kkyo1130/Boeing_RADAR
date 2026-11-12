import unittest
from pathlib import Path
import tempfile
import json
import numpy as np
import cv2
from PIL import Image,ImageDraw
import torch
from mcp_character_ocr import segment,CharacterOCR,CharacterCNN,PREPROCESSING,LEGACY_PREPROCESSING
from mcp_window_readouts import detect_mcp_readouts
from evaluate_character_camera import make_plan

class CharacterTests(unittest.TestCase):
    def image(self,n,noise=False):
        image=Image.new('RGB',(36*n,48),(12,14,16));draw=ImageDraw.Draw(image)
        for i in range(n):draw.rectangle((i*36+10,15,i*36+25,33),fill=(255,175,55))
        if noise:draw.line((0,2,36*n-1,2),fill=(255,175,55),width=1)
        return image
    def test_noise_removed_without_removing_glyphs(self):
        plain=segment(self.image(3),'hdg');noisy=segment(self.image(3,True),'hdg')
        self.assertEqual(len(noisy[0]),3)
        for a,b in zip(plain[0],noisy[0]):self.assertTrue(np.array_equal(np.array(a),np.array(b)))
        self.assertIsNone(segment(self.image(2),'hdg'))
        self.assertIsNone(segment(self.image(4),'alt'))
        self.assertIsNone(segment(Image.new('RGB',(108,48)),'hdg'))
    def panel(self,heading='107',altitude='25900'):
        f=np.full((220,800,3),160,np.uint8)
        for x,w,text in [(20,180,'250'),(240,180,heading),(450,240,altitude)]:
            cv2.rectangle(f,(x,40),(x+w,95),(25,25,25),-1)
            cv2.putText(f,text,(x+20,80),cv2.FONT_HERSHEY_SIMPLEX,1,(245,245,245),2)
        return f
    def test_window_localizer_selects_heading_not_ias_and_rejects_partial(self):
        boxes=detect_mcp_readouts(self.panel())
        self.assertEqual(set(boxes),{'hdg','alt'})
        self.assertGreater(boxes['hdg'][0],240)
        self.assertGreater(boxes['alt'][0],450)
        self.assertEqual(detect_mcp_readouts(self.panel(heading='10')), {})
        self.assertEqual(detect_mcp_readouts(self.panel(altitude='2590')), {})
    def test_normalization_versions_are_explicit(self):
        squashed=Image.new('RGB',(108,48),(12,14,16));draw=ImageDraw.Draw(squashed)
        for i in range(3):draw.rectangle((i*36+8,15,i*36+28,22),fill=(255,175,55))
        current=segment(squashed,'hdg',PREPROCESSING)[0][0]
        old=segment(squashed,'hdg',LEGACY_PREPROCESSING)[0][0]
        self.assertEqual(current.size,(32,32));self.assertEqual(old.size,(32,32))
        self.assertFalse(np.array_equal(np.array(current),np.array(old)))
        with self.assertRaises(ValueError):segment(self.image(3),'hdg','unknown')
    def test_live_character_mode_cannot_weaken_panel_gates(self):
        from unittest.mock import patch
        import sys,io
        from contextlib import redirect_stderr
        import live_mcp_ocr
        for flags in (['--yolo-conf','.4'],['--yolo-stable-frames','2'],['--stable-frames','2'],['--manual']):
            with patch.object(sys,'argv',['live','--character-checkpoint','candidate.pt','--yolo-weights','panel.pt',*flags]),redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as err:live_mcp_ocr.main()
                self.assertEqual(err.exception.code,2)

    def test_camera_plan_excludes_seen_values_and_is_reproducible(self):
        excluded={('032','00600'),('264','28400')}
        a=make_plan(42,12,excluded);self.assertEqual(a,make_plan(42,12,excluded))
        self.assertEqual(len(set(h for h,v in a)),12)
        self.assertFalse({h for h,v in a}&{'032','264'})
        self.assertFalse({v for h,v in a}&{'00600','28400'})
    def test_temporal_report_resets_on_missing_and_does_not_use_truth_to_accept(self):
        from report_character_camera import temporal_metrics
        records=[]
        for value in ['123','123',None,'123','123','123']:
            records.append(dict(truth={'hdg':'123','alt':'123'},models={name:{kind:{'value':value} for kind in ('hdg','alt')} for name in ('v5','character')}))
        metrics=temporal_metrics(records)['character']['hdg']
        self.assertEqual(metrics['stable_outputs'],1);self.assertEqual(metrics['stable_correct'],1)
        for row in records:row['truth']['hdg']='999'
        changed=temporal_metrics(records)['character']['hdg']
        self.assertEqual(changed['stable_outputs'],1);self.assertEqual(changed['stable_correct'],0)

    def test_checkpoint_preprocessing_and_low_score_abstention(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'model.pt';model=CharacterCNN()
            for parameter in model.parameters():parameter.data.zero_()
            torch.save(dict(model=model.state_dict(),preprocessing=PREPROCESSING),p)
            ocr=CharacterOCR(p);result=ocr.infer_aligned(self.image(3),'hdg')
            self.assertIsNone(result['value']);self.assertEqual(result['reason'],'LOW_MODEL_SCORE')
            self.assertEqual(result['raw_value'],'000')
            self.assertIsNone(ocr.infer_aligned(self.image(2),'hdg')['raw_value'])
            torch.save(dict(model=model.state_dict(),preprocessing='other'),p)
            with self.assertRaises(ValueError):CharacterOCR(p)

if __name__=='__main__':unittest.main()
