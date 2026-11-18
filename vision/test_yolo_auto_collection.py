import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from contextlib import ExitStack,redirect_stdout
import io
import numpy as np
from PIL import Image
from yolo_auto_collection import SimilarFrames,collect_auto,atomic_json,predict_candidate
from review_yolo_camera import load_capture,load_reviews,export_reviewed,review_gui
from yolo_camera_data import load_dataset,disjoint
from mcp_yolo_gate import PanelGate

class Tensor:
    def __init__(self,value):self.value=value
    def cpu(self):return self
    def tolist(self):return self.value

class AutoTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
    def capture(self,name='raw'):
        import cv2
        output=self.root/name;weights=self.root/'old.pt';weights.write_bytes(b'unchanged')
        args=SimpleNamespace(yolo_weights=weights,yolo_conf=.5,yolo_stable_frames=2,yolo_device='cpu',yolo_imgsz=960,
            dedup_distance=.015,source='0',session='physical-session-1',split='train',count=2,auto_interval=2,condition='test conditions')
        class Camera:
            index=0
            def isOpened(self):return True
            def read(self):
                if self.index>=6:raise AssertionError('Target reached; must not request another frame')
                color=[10,10,10,10,80,80][self.index];self.index+=1
                return True,np.full((600,800,3),color,dtype=np.uint8)
            def release(self):pass
        class Model:
            names={0:'mcp'};index=0
            def predict(self,*a,**kw):
                self.index+=1;score=.9 if self.index<5 else .41
                boxes=SimpleNamespace(xyxy=Tensor([[100,100,500,220]]),conf=Tensor([score]),cls=Tensor([0]))
                return [SimpleNamespace(boxes=boxes)]
        camera=Camera()
        with ExitStack() as stack:
            stack.enter_context(patch.object(cv2,'VideoCapture',return_value=camera))
            stack.enter_context(patch.object(cv2,'waitKey',return_value=255))
            for method in ('imshow','putText','rectangle','destroyAllWindows'):stack.enter_context(patch.object(cv2,method))
            stack.enter_context(patch('yolo_auto_collection.time.monotonic',side_effect=[0,1,2,3,4,5,6]))
            stack.enter_context(redirect_stdout(io.StringIO()))
            result=collect_auto(args,output,model=Model())
        self.assertEqual(camera.index,6)
        self.assertEqual(weights.read_bytes(),b'unchanged')
        return output,result
    def decision(self,record,action='ACCEPTED',box=None):
        return dict(action=action,box=box or record['proposed_box'],method='HUMAN_DRAG',reviewed_at='2026-11-12T00:00:00Z',image_sha256=record['image_sha256'])
    def test_timed_capture_target_dedup_and_uncertainty_buckets(self):
        root,data=self.capture();rows=data['records']
        self.assertEqual(len(rows),2)
        self.assertEqual([r['category'] for r in rows],['candidates','needs_review'])
        self.assertTrue(all(r['review_status']=='PENDING' for r in rows))
        self.assertEqual(rows[1]['reason'],'LOW_OR_MISSING_PANEL_SCORE')
        self.assertEqual(list(root.rglob('*.txt')),[])
        self.assertFalse((root/'dataset.yaml').exists())
        with self.assertRaisesRegex(ValueError,'UNVERIFIED'):load_dataset(root)
    def test_near_duplicate_noise_and_scene_changes(self):
        f=SimilarFrames(.015);base=Image.new('RGB',(200,100),(70,70,70))
        self.assertFalse(f.duplicate(base));f.remember(base)
        self.assertTrue(f.duplicate(base))
        self.assertTrue(f.duplicate(Image.new('RGB',(200,100),(72,71,70))))
        self.assertFalse(f.duplicate(Image.new('RGB',(200,100),(120,120,120))))
    def test_failed_prediction_saved_as_review_not_truth(self):
        class Failed:
            def predict(self,*a,**kw):raise RuntimeError('offline')
        result=predict_candidate(Failed(),np.zeros((600,800,3)),PanelGate())
        self.assertEqual(result['category'],'needs_review');self.assertIsNone(result['proposed_box'])
        self.assertTrue(result['reason'].startswith('DETECTOR_ERROR'))
        class Missing:
            def predict(self,*a,**kw):return [SimpleNamespace(boxes=None)]
        self.assertEqual(predict_candidate(Missing(),np.zeros((600,800,3)),PanelGate())['category'],'needs_review')
    def test_no_export_until_every_label_reviewed_then_corrected_box_and_split(self):
        root,data=self.capture();capture,digest=load_capture(root);reviews=load_reviews(root,digest)
        records=capture['records'];out=self.root/'confirmed'
        reviews['decisions'][records[0]['id']]=self.decision(records[0],box=[120,120,520,240])
        atomic_json(root/'reviews.json',reviews)
        with self.assertRaisesRegex(ValueError,'Every image'):export_reviewed(root,out)
        self.assertFalse(out.exists())
        reviews['decisions'][records[1]['id']]=self.decision(records[1],action='REJECTED')
        atomic_json(root/'reviews.json',reviews)
        export_reviewed(root,out);result=load_dataset(out,{'train'})
        self.assertEqual(len(result['entries']),1)
        self.assertEqual(result['sessions'],{'physical-session-1':'train'})
        np.testing.assert_allclose(result['entries'][0]['box'],[120,120,520,240])
        self.assertTrue((root/records[1]['image_path']).exists()) # rejected source is never deleted
        with self.assertRaises(ValueError):export_reviewed(root,out)
    def test_gui_review_accept_redraw_and_export(self):
        import cv2
        root,data=self.capture();out=self.root/'confirmed'
        with ExitStack() as stack:
            stack.enter_context(patch.object(cv2,'waitKey',side_effect=[13,ord('r'),13]))
            stack.enter_context(patch.object(cv2,'selectROI',return_value=(30,40,400,120)))
            for method in ('imshow','rectangle','putText','destroyAllWindows'):stack.enter_context(patch.object(cv2,method))
            self.assertEqual(review_gui(root,out),out.resolve())
        result=load_dataset(out,{'train'});self.assertEqual(len(result['entries']),2)
        np.testing.assert_allclose(result['entries'][1]['box'],[30,40,430,160])
        audit=json.loads((out/'review_audit.json').read_text())
        self.assertEqual(audit['decisions']['00000']['method'],'HUMAN_ACCEPT')
        self.assertEqual(audit['decisions']['00001']['method'],'HUMAN_DRAG')
    def test_review_pause_resume_and_source_tamper(self):
        import cv2
        root,data=self.capture();out=self.root/'confirmed'
        with ExitStack() as stack:
            stack.enter_context(patch.object(cv2,'waitKey',side_effect=[13,ord('q')]))
            for method in ('imshow','rectangle','putText','destroyAllWindows'):stack.enter_context(patch.object(cv2,method))
            self.assertIsNone(review_gui(root,out))
        self.assertFalse(out.exists());self.assertEqual(len(json.loads((root/'reviews.json').read_text())['decisions']),1)
        with ExitStack() as stack:
            stack.enter_context(patch.object(cv2,'waitKey',return_value=ord('d')))
            for method in ('imshow','rectangle','putText','destroyAllWindows'):stack.enter_context(patch.object(cv2,method))
            review_gui(root,out)
        self.assertEqual(len(load_dataset(out)['entries']),1)
        record=data['records'][0];Image.new('RGB',(800,600),'white').save(root/record['image_path'])
        with self.assertRaisesRegex(ValueError,'changed'):load_capture(root)
    def test_invalid_review_box_or_missing_provenance_cannot_export(self):
        root,data=self.capture();capture,digest=load_capture(root);reviews=load_reviews(root,digest)
        for record in capture['records']:reviews['decisions'][record['id']]=self.decision(record)
        reviews['decisions']['00000']['box']=[-1,0,500,100]
        atomic_json(root/'reviews.json',reviews)
        with self.assertRaisesRegex(ValueError,'Invalid human'):export_reviewed(root,self.root/'bad')
        self.assertFalse((self.root/'bad').exists())
    def test_same_physical_session_export_never_crosses_train_test(self):
        root,data=self.capture();capture,digest=load_capture(root);reviews=load_reviews(root,digest)
        for record in capture['records']:reviews['decisions'][record['id']]=self.decision(record)
        atomic_json(root/'reviews.json',reviews);out=self.root/'train';export_reviewed(root,out)
        # Even a separately reviewed duplicate physical session cannot become held-out data.
        other=load_dataset(out)
        other=dict(other,root='other',hashes=set())
        with self.assertRaises(ValueError):disjoint([load_dataset(out),other])

    def test_exported_audit_and_labels_are_verified_again_before_training(self):
        root,data=self.capture();capture,digest=load_capture(root);reviews=load_reviews(root,digest)
        for record in capture['records']:reviews['decisions'][record['id']]=self.decision(record)
        atomic_json(root/'reviews.json',reviews);out=self.root/'confirmed';export_reviewed(root,out)
        label=out/'labels/train/00000.txt';original=label.read_text()
        label.write_text('0 0.5 0.5 0.5 0.2\n')
        with self.assertRaisesRegex(ValueError,'differs'):load_dataset(out)
        label.write_text(original);load_dataset(out)
        (out/'review_audit.json').unlink()
        with self.assertRaisesRegex(ValueError,'audit'):load_dataset(out)

    def test_missing_proposal_cannot_be_accepted_without_manual_box(self):
        import cv2
        root,data=self.capture();data['records'][1]['proposed_box']=None
        data['records'][1]['model_score']=None
        atomic_json(root/'capture_manifest.json',data)
        out=self.root/'confirmed'
        with ExitStack() as stack:
            # The second ENTER has no box and cannot accept; R must establish one.
            stack.enter_context(patch.object(cv2,'waitKey',side_effect=[13,13,ord('r'),13]))
            selection=stack.enter_context(patch.object(cv2,'selectROI',return_value=(40,50,400,120)))
            for method in ('imshow','rectangle','putText','destroyAllWindows'):stack.enter_context(patch.object(cv2,method))
            review_gui(root,out)
        selection.assert_called_once()
        self.assertEqual(len(load_dataset(out)['entries']),2)

    def test_capture_identifier_cannot_escape_export_directory(self):
        root,data=self.capture();data['records'][0]['id']='../../escape'
        atomic_json(root/'capture_manifest.json',data)
        with self.assertRaisesRegex(ValueError,'identifier'):export_reviewed(root,self.root/'confirmed')
        self.assertFalse((self.root/'confirmed').exists())

    def test_original_training_entrypoint_also_rejects_unreviewed_capture(self):
        from train_mcp_yolo import validate_dataset
        root,data=self.capture()
        with self.assertRaisesRegex(ValueError,'UNVERIFIED'):validate_dataset(root)

if __name__=='__main__':unittest.main()
