import csv
import io
import json
import tempfile
import unittest
from contextlib import ExitStack,redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch,Mock
from PIL import Image
import numpy as np
from review_yolo_camera import load_capture,load_reviews,export_reviewed,review_gui
from yolo_auto_collection import atomic_json,signature
from yolo_camera_data import load_dataset,FIELDS
from finetune_yolo_camera import prepare
from yolo_final_test_policy import check_final_test
from yolo_gate_diagnostics import aggregate

class BlindTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);self.index=0
    def capture(self,name,split='train'):
        root=self.root/name;root.mkdir();(root/'candidates').mkdir();records=[]
        for i in range(2):
            self.index+=1;image=Image.new('RGB',(800,600),(self.index,30,40));rel=f'candidates/{i:05d}.png';image.save(root/rel)
            records.append(dict(id=f'{i:05d}',image_path=rel,image_sha256=signature(image),width=800,height=600,
                session_id=name,split=split,review_status='PENDING',category='candidates',proposed_box=[200,200,600,400],
                model_score=.98765,reason='OLD_PROPOSAL_SECRET',condition='fixture'))
        atomic_json(root/'collection.json',dict(mode='AUTO_CANDIDATES',session=name,split=split))
        atomic_json(root/'capture_manifest.json',dict(mode='AUTO_CANDIDATES',session=name,split=split,records=records))
        return root
    def approved(self,name,split='train',blind=True):
        root=self.capture(name,split);capture,digest=load_capture(root);work=self.root/(name+'_work')
        reviews=load_reviews(root,digest,blind=blind,review_dir=work if blind else None)
        for row in capture['records']:
            reviews['decisions'][row['id']]=dict(action='ACCEPTED',box=[100,100,500,220],
                method='BLIND_MANUAL' if blind else 'HUMAN_ACCEPT',reviewed_at='2026-11-12T00:00:00Z',image_sha256=row['image_sha256'])
        target=work/'reviews.json' if blind else root/'reviews.json';target.parent.mkdir(parents=True,exist_ok=True);atomic_json(target,reviews)
        out=self.root/(name+'_labels');export_reviewed(root,out,blind=blind,review_dir=work if blind else None)
        return out
    def synthetic(self):
        root=self.root/'synthetic';root.mkdir();rows=[]
        for split in ['train','val','test']:
            self.index+=1;ir=f'images/{split}/base.png';lr=f'labels/{split}/base.txt'
            for rel in [ir,lr]:(root/rel).parent.mkdir(parents=True,exist_ok=True)
            Image.new('RGB',(100,80),(self.index,90,100)).save(root/ir);(root/lr).write_text('0 .5 .5 .8 .3\n')
            rows.append(dict(source_path=ir,image_path=ir,label_path=lr,session_id='synthetic_'+split,split=split,x=0,y=0,width=1,height=1,condition='fixture'))
        with (root/'manifest.csv').open('w',newline='') as fp:
            writer=csv.DictWriter(fp,fieldnames=FIELDS);writer.writeheader();writer.writerows(rows)
        return root
    def test_blind_gui_never_shows_proposals_or_reuses_old_approvals(self):
        import cv2
        root=self.capture('train_near');capture,digest=load_capture(root)
        old=load_reviews(root,digest)
        for row in capture['records']:old['decisions'][row['id']]=dict(action='ACCEPTED',box=row['proposed_box'],method='HUMAN_ACCEPT',reviewed_at='old',image_sha256=row['image_sha256'])
        atomic_json(root/'reviews.json',old)
        before={str(p.relative_to(root)):p.read_bytes() for p in root.rglob('*') if p.is_file()}
        work=self.root/'blind_work';out=self.root/'blind_labels'
        with ExitStack() as stack:
            stack.enter_context(patch.object(cv2,'waitKey',side_effect=[13,ord('r'),13,ord('d')]))
            stack.enter_context(patch.object(cv2,'selectROI',return_value=(20,30,700,160)))
            texts=stack.enter_context(patch.object(cv2,'putText'))
            rectangles=stack.enter_context(patch.object(cv2,'rectangle'))
            for method in ('imshow','destroyAllWindows'):stack.enter_context(patch.object(cv2,method))
            review_gui(root,out,blind=True,review_dir=work)
        # The initial ENTER did not approve a proposal. Only the newly dragged rectangle was rendered.
        self.assertEqual(rectangles.call_count,1)
        self.assertEqual(rectangles.call_args.args[1:3],((20,30),(720,190)))
        for call in texts.call_args_list:
            self.assertNotIn('0.98765',call.args[1]);self.assertNotIn('OLD_PROPOSAL_SECRET',call.args[1]);self.assertNotIn('candidates',call.args[1])
        self.assertEqual({str(p.relative_to(root)):p.read_bytes() for p in root.rglob('*') if p.is_file()},before)
        meta=json.loads((out/'collection.json').read_text());self.assertEqual(meta['annotation_mode'],'BLIND')
        data=load_dataset(out);self.assertEqual(len(data['entries']),1)
        np.testing.assert_allclose(data['entries'][0]['box'],[20,30,720,190],atol=1e-4,rtol=0)
    def test_assisted_progress_cannot_be_copied_into_blind_work(self):
        root=self.capture('capture');_,digest=load_capture(root);work=self.root/'work';work.mkdir()
        atomic_json(work/'reviews.json',load_reviews(root,digest))
        with self.assertRaisesRegex(ValueError,'assisted'):load_reviews(root,digest,blind=True,review_dir=work)
        with self.assertRaises(ValueError):load_reviews(root,digest,blind=True,review_dir=root/'inside')
    def test_blind_export_requires_fresh_manual_method(self):
        root=self.capture('capture');capture,digest=load_capture(root);work=self.root/'work';work.mkdir()
        reviews=load_reviews(root,digest,blind=True,review_dir=work)
        for row in capture['records']:reviews['decisions'][row['id']]=dict(action='ACCEPTED',box=row['proposed_box'],method='HUMAN_ACCEPT',reviewed_at='old',image_sha256=row['image_sha256'])
        atomic_json(work/'reviews.json',reviews)
        with self.assertRaisesRegex(ValueError,'fresh manual'):export_reviewed(root,self.root/'out',blind=True,review_dir=work)
    def test_blind_training_uses_new_labels_and_retires_old_test(self):
        synthetic=self.synthetic();train=self.approved('near');val=self.approved('val','val');test=self.approved('new_test','test');old=self.approved('old_test','test',blind=False)
        weights=self.root/'old.pt';weights.write_bytes(b'original')
        config,out=prepare(synthetic,[train,val],test,weights,self.root/'model',blind_camera=True,diagnostic_tests=[old])
        meta=json.loads((out/'training_manifest.json').read_text());self.assertEqual(meta['evaluation_policy']['retired_tests'][0]['purpose'],'DIAGNOSTIC_ONLY')
        merged=load_dataset(out/'mixed');self.assertEqual(len(merged['entries']),7)
        self.assertEqual(sum(e['row']['split']=='test' for e in merged['entries']),1) # synthetic test only
        self.assertEqual(weights.read_bytes(),b'original')
        check_final_test(load_dataset(test),meta['evaluation_policy'])
        reused=load_dataset(test);reused['hashes']=load_dataset(old)['hashes']
        with self.assertRaisesRegex(ValueError,'DIAGNOSTIC_ONLY'):check_final_test(reused,meta['evaluation_policy'])
    def test_assisted_train_or_missing_retired_policy_is_blocked(self):
        synthetic=self.synthetic();train=self.approved('near',blind=False);val=self.approved('val','val');test=self.approved('new','test');old=self.approved('old','test',False)
        weights=self.root/'old.pt';weights.write_bytes(b'old')
        with self.assertRaisesRegex(ValueError,'blind labels'):prepare(synthetic,[train,val],test,weights,self.root/'out',blind_camera=True,diagnostic_tests=[old])
        self.assertFalse((self.root/'out').exists())
        with self.assertRaisesRegex(ValueError,'diagnostic-test'):prepare(synthetic,[train,val],test,weights,self.root/'out2',blind_camera=True)
    def test_confidence_distribution_quantiles_and_missing_are_separate(self):
        rows=[dict(prediction=[0,0,10,10],top_iou=1,top_score=s,accepted=False,accepted_iou=None,reason='LOW_OR_MISSING_PANEL_SCORE',gate_diagnostics={'all_failures':[]}) for s in [.2,.5,.9]]
        rows.append(dict(prediction=None,top_iou=0,top_score=None,accepted=False,accepted_iou=None,reason='LOW_OR_MISSING_PANEL_SCORE',gate_diagnostics={'all_failures':[]}))
        result=aggregate(rows)['confidence_distribution'];self.assertEqual(result['quantiles']['50'],.5)
        self.assertEqual(sum(b['count'] for b in result['bins']),3);self.assertEqual(result['missing_images'],1)

    def test_blind_pause_resume_uses_only_its_separate_work_file(self):
        import cv2
        root=self.capture('pause');work=self.root/'work';out=self.root/'labels'
        with ExitStack() as stack:
            stack.enter_context(patch.object(cv2,'waitKey',return_value=ord('q')))
            for method in ('imshow','destroyAllWindows','putText','rectangle'):stack.enter_context(patch.object(cv2,method))
            self.assertIsNone(review_gui(root,out,blind=True,review_dir=work))
        self.assertTrue((work/'reviews.json').exists());self.assertFalse((root/'reviews.json').exists());self.assertFalse(out.exists())
        with ExitStack() as stack:
            stack.enter_context(patch.object(cv2,'waitKey',side_effect=[ord('r'),13,ord('d')]))
            stack.enter_context(patch.object(cv2,'selectROI',return_value=(100,100,400,120)))
            for method in ('imshow','destroyAllWindows','putText','rectangle'):stack.enter_context(patch.object(cv2,method))
            review_gui(root,out,blind=True,review_dir=work)
        self.assertEqual(len(load_dataset(out)['entries']),1)

    def test_new_test_capture_only_never_loads_or_calls_detector(self):
        import cv2
        from yolo_auto_collection import collect_auto
        class Camera:
            index=0
            def isOpened(self):return True
            def read(self):self.index+=1;return True,np.full((100,200,3),80*self.index,dtype=np.uint8)
            def release(self):pass
        args=SimpleNamespace(capture_only=True,yolo_weights=None,yolo_conf=.5,yolo_stable_frames=3,
            yolo_device='cpu',yolo_imgsz=960,dedup_distance=.015,source='0',session='brand_new_test',split='test',
            count=2,auto_interval=2,condition='new independent session')
        output=self.root/'capture_only'
        with ExitStack() as stack:
            stack.enter_context(patch.object(cv2,'VideoCapture',return_value=Camera()))
            stack.enter_context(patch.object(cv2,'waitKey',return_value=255))
            for method in ('imshow','destroyAllWindows','putText','rectangle'):stack.enter_context(patch.object(cv2,method))
            stack.enter_context(patch('yolo_auto_collection.time.monotonic',side_effect=[0,2,4]))
            prediction=stack.enter_context(patch('yolo_auto_collection.predict_candidate',side_effect=AssertionError('must not predict')))
            stack.enter_context(redirect_stdout(io.StringIO()))
            data=collect_auto(args,output)
        prediction.assert_not_called()
        self.assertEqual(len(data['records']),2)
        self.assertTrue(all(r['proposed_box'] is None and r['model_score'] is None for r in data['records']))
        self.assertFalse((output/'manifest.csv').exists())

    def test_final_comparison_requires_policy_and_outputs_distribution(self):
        import sys
        import torch
        from compare_yolo_camera import main
        synthetic=self.synthetic();train=self.approved('near');val=self.approved('val','val');test=self.approved('final','test');oldtest=self.approved('oldtest','test',False)
        old=self.root/'old.pt';old.write_bytes(b'old')
        _,out=prepare(synthetic,[train,val],test,old,self.root/'model',blind_camera=True,diagnostic_tests=[oldtest])
        new=out/'fit/weights/best.pt';new.parent.mkdir(parents=True);new.write_bytes(b'new')
        boxes=SimpleNamespace(xyxy=torch.tensor([[100.,100.,500.,220.]]),conf=torch.tensor([.9]),cls=torch.tensor([0]))
        fake=SimpleNamespace(names={0:'mcp'},val=lambda **kw:SimpleNamespace(box=SimpleNamespace(mp=.8,mr=.9,map50=.7,map=.6)),predict=lambda *a,**kw:[SimpleNamespace(boxes=boxes)])
        argv=['compare','--final-test','--test',str(test),'--old',str(old),'--new',str(new),'--seen',str(synthetic),'--seen',str(train),'--seen',str(val),'--output',str(self.root/'report'),'--device','cpu']
        with patch.object(sys,'argv',argv),patch('ultralytics.YOLO',return_value=fake),redirect_stdout(io.StringIO()):main()
        report=json.loads((self.root/'report/comparison.json').read_text())
        self.assertEqual(report['evaluation_mode'],'FINAL_BLIND_INDEPENDENT')
        self.assertEqual(report['models']['new']['confidence_distribution']['detected_images'],2)
        self.assertIn('Independent blind final-test',(self.root/'report/diagnosis.md').read_text())

    def test_workflow_commands_keep_separate_paths_and_policy(self):
        from yolo_blind_workflow import command
        args=SimpleNamespace(action='review',batch='train_near',source='0',prepare_only=False,epochs=40,device='mps',max_frames=300)
        review=command(args);self.assertIn('--blind',review);self.assertIn('--review-dir',review)
        args.action='train';args.batch=None;train=command(args);self.assertIn('--blind-camera',train);self.assertIn('--diagnostic-test',train)
        self.assertEqual(train.count('--camera'),4)
        args.action='evaluate';self.assertIn('--final-test',command(args))
        args.action='collect-final';capture=command(args);self.assertIn('--capture-only',capture);self.assertNotIn('--yolo-weights',capture)
        args.action='video';video=command(args);self.assertNotIn('--gate-conf',video);self.assertNotIn('--stable-frames',video)

class Tensor:
    def __init__(self,value):self.value=value
    def cpu(self):return self
    def tolist(self):return self.value

class VideoTests(unittest.TestCase):
    def test_three_frame_gate_resets_after_low_score_and_never_calls_cnn(self):
        import cv2
        from validate_yolo_video import run
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);weights=root/'old.pt';weights.write_bytes(b'original')
            class Camera:
                index=0
                def isOpened(self):return True
                def read(self):self.index+=1;return True,np.zeros((600,800,3),dtype=np.uint8)
                def get(self,key):return self.index*33.3
                def release(self):pass
            class Model:
                names={0:'mcp'};index=0
                def predict(self,*args,**kw):
                    score=[.9,.9,.9,.4,.9,.9,.9][self.index];self.index+=1
                    return [SimpleNamespace(boxes=SimpleNamespace(xyxy=Tensor([[100,100,500,220]]),conf=Tensor([score]),cls=Tensor([0])))]
            detector=Mock(return_value={'hdg':(10,10,100,40),'alt':(150,10,150,40)})
            args=SimpleNamespace(weights=weights,source='0',output=root/'video',device='cpu',imgsz=960,max_frames=7,headless=True)
            with patch.object(cv2,'VideoCapture',return_value=Camera()),patch.object(cv2,'destroyAllWindows'),redirect_stdout(io.StringIO()):summary=run(args,model=Model(),readout_detector=detector)
            self.assertEqual(summary['three_frame_pass_count'],2);self.assertEqual(summary['eligible_count'],2)
            self.assertEqual(summary['policy']['confidence'],.5);self.assertEqual(summary['policy']['stable_frames'],3)
            self.assertFalse(summary['cnn_forwarded']);self.assertEqual(detector.call_count,2)
            with (args.output/'frames.csv').open() as fp:rows=list(csv.DictReader(fp))
            self.assertEqual([int(r['frame']) for r in rows if r['eligible_after_all_checks']=='True'],[3,7])
            self.assertEqual(rows[3]['consecutive_valid_frames'],'0')
            args.output=root/'failed_video';args.save_failure_frames=1
            with patch.object(cv2,'VideoCapture',return_value=Camera()),patch.object(cv2,'destroyAllWindows'),redirect_stdout(io.StringIO()):
                failed=run(args,model=Model(),readout_detector=lambda frame:{})
            self.assertEqual(failed['eligible_count'],0)
            self.assertEqual(failed['readout_failure_frames_saved'],1)
            self.assertEqual(len(list((args.output/'readout_failures').glob('*.png'))),1)
            evidence=json.loads(next((args.output/'readout_failures').glob('*.json')).read_text())
            self.assertEqual(evidence['reason'],'READOUTS_MISSING_OR_AMBIGUOUS')
            self.assertEqual(evidence['panel'],[100,100,500,220])


if __name__=='__main__':unittest.main()
