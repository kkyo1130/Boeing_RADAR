import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from mcp_yolo_gate import iou,PanelGate
from yolo_gate_diagnostics import aggregate,explain,annotation_provenance

class DiagnosticTests(unittest.TestCase):
    def test_iou_known_continuous_pixel_rectangles_and_invalid_inputs(self):
        self.assertEqual(iou([0,0,10,10],[0,0,10,10]),1)
        self.assertAlmostEqual(iou([0,0,10,10],[5,0,15,10]),1/3)
        self.assertEqual(iou([0,0,10,10],[2,2,7,7]),.25)
        self.assertEqual(iou([0,0,10,10],[10,0,20,10]),0)
        for bad in [None,[],[0,0,0,10],[10,0,0,10],[float('nan'),0,10,10],[0,0,float('inf'),10]]:
            self.assertEqual(iou([0,0,10,10],bad),0)
        a=[150,240,640,350];b=[170,250,650,355];before=deepcopy((a,b))
        self.assertEqual(iou(a,b),iou(b,a));self.assertEqual((a,b),before)
    def test_all_detected_localized_and_accepted_denominators(self):
        def row(pred,overlap,accepted=False,reason=None):
            return dict(prediction=pred,top_iou=overlap,top_score=.9 if pred else None,accepted=accepted,
                accepted_iou=overlap if accepted else None,reason=reason,gate_diagnostics={'all_failures':[]})
        result=aggregate([row([0,0,10,10],1,True),row([20,20,30,30],0,reason='AMBIGUOUS_PANELS'),row(None,0,reason='LOW_OR_MISSING_PANEL_SCORE')])
        self.assertEqual(result['image_count'],3);self.assertEqual(result['detected_image_count'],2)
        self.assertAlmostEqual(result['mean_top1_iou_all_images'],1/3)
        self.assertEqual(result['mean_top1_iou_detected_images'],.5)
        self.assertEqual(result['mean_top1_iou_localized_iou50'],1)
        self.assertEqual(result['accepted_mean_iou'],1)
        self.assertEqual(result['spatial_gate_coverage'],1/3)
    def test_no_detection_is_zero_all_mean_and_null_detected_mean(self):
        row=dict(prediction=None,top_iou=0,top_score=None,accepted=False,accepted_iou=None,reason='LOW_OR_MISSING_PANEL_SCORE',gate_diagnostics={'all_failures':['NO_MCP_DETECTION_AT_0_1']})
        result=aggregate([row]);self.assertEqual(result['mean_top1_iou_all_images'],0)
        self.assertIsNone(result['mean_top1_iou_detected_images']);self.assertIsNone(result['accepted_mean_iou'])
    def test_primary_confidence_rejection_does_not_hide_other_failed_checks(self):
        candidates=[{'class':0,'score':.49,'box':[0,10,500,100]}, {'class':0,'score':.4,'box':[200,250,700,400]}]
        diagnostic=explain(candidates,800,600)
        self.assertEqual(diagnostic['primary_reason'],'LOW_OR_MISSING_PANEL_SCORE')
        self.assertEqual(set(diagnostic['all_failures']),{'LOW_CONFIDENCE','AMBIGUOUS_PANELS','EDGE_CLIPPED'})
        self.assertFalse(diagnostic['accepted']);self.assertFalse(diagnostic['temporal_stability_evaluated'])
    def test_policy_and_operational_temporal_gate_are_unchanged(self):
        gate=PanelGate();policy=gate.policy()
        self.assertEqual((policy['confidence'],policy['candidate_floor'],policy['alternative_score'],policy['alternative_iou']),(.5,.1,.3,.5))
        self.assertEqual((policy['edge_margin_px'],policy['min_side_px'],policy['min_area_ratio'],policy['max_area_ratio']),(1,12,.003,.9))
        self.assertEqual((policy['stable_frames'],policy['stability_iou']),(3,.8));self.assertIsNone(policy['aspect_ratio_constraint'])
        candidates=[{'class':0,'score':.8,'box':[100,100,500,220]}]
        self.assertTrue(explain(candidates,800,600)['accepted'])
        self.assertIsNone(gate.select(candidates,800,600)[0]);self.assertIsNone(gate.select(candidates,800,600)[0])
        self.assertIsNotNone(gate.select(candidates,800,600)[0])
    def test_annotation_proposal_anchoring_is_reported_without_relabeling(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);source=root/'raw';source.mkdir()
            (root/'collection.json').write_text(json.dumps({'source_capture':str(source)}))
            (root/'review_audit.json').write_text(json.dumps({'decisions':{'00000':{'method':'HUMAN_ACCEPT'},'00001':{'method':'HUMAN_DRAG'}}}))
            (source/'collection.json').write_text(json.dumps({'weights_sha256':'oldhash'}))
            (source/'capture_manifest.json').write_text(json.dumps({'records':[{'id':'00000','proposed_box':[10,20,50,40]},{'id':'00001','proposed_box':[10,20,50,40]}]}))
            entries=[{'row':{'image_path':'images/test/00000.png'},'box':[10,20,50,40]}, {'row':{'image_path':'images/test/00001.png'},'box':[10,20,60,50]}]
            before=deepcopy(entries);result=annotation_provenance(root,entries)
            self.assertEqual(result['methods'],{'HUMAN_ACCEPT':1,'HUMAN_DRAG':1})
            self.assertEqual(result['labels_matching_proposal_iou_999'],1)
            self.assertEqual(result['source_weights_sha256'],'oldhash');self.assertEqual(entries,before)

    def test_validator_prediction_uses_split_relative_path_not_ambiguous_basename(self):
        from compare_yolo_camera import validation_prediction
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'labels').mkdir()
            (root/'labels/a_00000.txt').write_text('0 0.5 0.5 0.8 0.2 0.9\n')
            (root/'labels/b_00000.txt').write_text('0 0.2 0.2 0.1 0.1 0.8\n')
            entry={'row':{'image_path':'images/test/b/00000.png','split':'test'},'width':100,'height':100}
            result=validation_prediction(root,entry)
            self.assertEqual(result['score'],.8)
            for actual,expected in zip(result['box'],[15,15,25,25]):self.assertAlmostEqual(actual,expected)

if __name__=='__main__':unittest.main()
