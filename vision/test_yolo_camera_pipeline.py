import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from yolo_camera_data import FIELDS,load_dataset,disjoint,bbox_xyxy
from finetune_yolo_camera import prepare
from mcp_yolo_gate import PanelGate,detect_panel_readouts,iou

class YoloTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.index=0
    def data(self,name,splits):
        root=self.root/name;root.mkdir();rows=[]
        for split in splits:
            self.index+=1
            ir=f'images/{split}/a.png';lr=f'labels/{split}/a.txt'
            for rel in (ir,lr):(root/rel).parent.mkdir(parents=True,exist_ok=True)
            Image.new('RGB',(100,80),(self.index,50,70)).save(root/ir)
            (root/lr).write_text('0 0.5 0.5 0.8 0.3\n')
            rows.append(dict(source_path=ir,image_path=ir,label_path=lr,session_id=name+'_'+split,split=split,x=10,y=28,width=80,height=24,condition='fixture'))
        self.write(root,rows);return root
    def write(self,root,rows):
        with (root/'manifest.csv').open('w',newline='') as fp:
            w=csv.DictWriter(fp,fieldnames=FIELDS);w.writeheader();w.writerows(rows)
    def test_labels_sessions_and_pixel_duplicates(self):
        a=self.data('a',['train']);b=self.data('b',['test']);da=load_dataset(a);db=load_dataset(b)
        disjoint([da,db])
        with self.assertRaises(ValueError):disjoint([da,da])
        rows=[e['row'] for e in db['entries']];rows[0]['session_id']='a_train';self.write(b,rows)
        with self.assertRaises(ValueError):disjoint([da,load_dataset(b)])
        for label in ['1 .5 .5 .8 .3','0 .5 .5 2 .3','0 nan .5 .8 .3','0 .5 .5 0 .3','']:
            (a/'labels/train/a.txt').write_text(label)
            with self.assertRaises(ValueError):load_dataset(a)
    def test_missing_path_and_duplicate_pixels_rejected(self):
        a=self.data('a',['train']);b=self.data('b',['test'])
        (b/'images/test/a.png').write_bytes((a/'images/train/a.png').read_bytes())
        with self.assertRaises(ValueError):disjoint([load_dataset(a),load_dataset(b)])
        (a/'labels/train/a.txt').unlink()
        with self.assertRaises(ValueError):load_dataset(a)
    def test_merge_preserves_synthetic_splits_and_reserves_test(self):
        base=self.data('base',['train','val','test']);train=self.data('camera',['train']);val=self.data('val',['val']);test=self.data('held',['test'])
        initial=self.root/'old.pt';initial.write_bytes(b'original')
        config,out=prepare(base,[train,val],test,initial,self.root/'new')
        merged=load_dataset(out/'mixed');self.assertEqual(len(merged['entries']),5)
        self.assertEqual(initial.read_bytes(),b'original')
        self.assertNotIn('held',str(config.read_text()))
        with self.assertRaises(ValueError):prepare(base,[train,val],test,initial,out)
    def test_gate_low_ambiguous_clipped_motion_and_recovery(self):
        gate=PanelGate(.5,3)
        def c(score=.9,box=None):return {'class':0,'score':score,'box':box or [100,100,500,220]}
        self.assertIsNone(gate.select([c(.41)],800,600)[0])
        self.assertEqual(gate.select([c(),c(.7,[100,350,500,470])],800,600)[1],'AMBIGUOUS_PANELS')
        self.assertIsNone(gate.select([c(box=[0,100,500,220])],800,600)[0])
        for _ in range(2):self.assertIsNone(gate.select([c()],800,600)[0])
        self.assertIsNotNone(gate.select([c()],800,600)[0])
        self.assertIsNone(gate.select([c(box=[300,300,700,420])],800,600)[0])
        self.assertIsNone(gate.select([],800,600)[0])
        self.assertEqual(gate.count,0)
        self.assertEqual(iou([0,0,10,10],[0,0,10,10]),1)
    def test_detector_exception_never_falls_back(self):
        import numpy as np
        class Broken:
            def predict(self,*args,**kw):raise RuntimeError('disconnected')
        boxes,reason=detect_panel_readouts(Broken(),np.zeros((100,200,3)),PanelGate(),lambda frame:self.fail('should not receive rejected frame'))
        self.assertEqual(boxes,{})
        self.assertTrue(reason.startswith('DETECTOR_ERROR'))

    def test_collection_boxes_full_frame_and_keeps_session_split(self):
        import sys
        import cv2
        import numpy as np
        import collect_yolo_camera
        from contextlib import ExitStack,redirect_stdout
        import io
        root=self.root/'captured'
        class Camera:
            index=0
            def isOpened(self):return True
            def read(self):
                self.index+=1;return True,np.full((80,100,3),self.index,dtype=np.uint8)
            def release(self):pass
        with ExitStack() as stack:
            stack.enter_context(patch.object(sys,'argv',['collect','--output',str(root),'--session','real_test_1','--split','test','--count','2']))
            stack.enter_context(patch.object(cv2,'VideoCapture',return_value=Camera()))
            stack.enter_context(patch.object(cv2,'waitKey',side_effect=[32,32]))
            stack.enter_context(patch.object(cv2,'selectROI',return_value=(10,20,80,30)))
            for method in ('imshow','destroyAllWindows','putText'):stack.enter_context(patch.object(cv2,method))
            stack.enter_context(patch('collect_yolo_camera.time.monotonic',side_effect=[0,0,3,3]))
            stack.enter_context(redirect_stdout(io.StringIO()))
            collect_yolo_camera.main()
        data=load_dataset(root,{'test'});self.assertEqual(len(data['entries']),2)
        self.assertEqual(data['sessions'],{'real_test_1':'test'})
        for entry in data['entries']:
            for actual,expected in zip(entry['box'],[10,20,90,50]):self.assertAlmostEqual(actual,expected)

    def test_panel_readouts_only_after_gate_and_never_partial(self):
        import torch
        import numpy as np
        from types import SimpleNamespace
        from unittest.mock import Mock
        boxes=SimpleNamespace(xyxy=torch.tensor([[100,100,500,220]]),conf=torch.tensor([.9]),cls=torch.tensor([0]))
        model=SimpleNamespace(predict=lambda *a,**k:[SimpleNamespace(boxes=boxes)])
        readouts=Mock(return_value={'hdg':(20,20,100,40),'alt':(180,20,150,40)})
        gate=PanelGate(.5,3);frame=np.zeros((600,800,3))
        for _ in range(2):self.assertEqual(detect_panel_readouts(model,frame,gate,readouts)[0],{})
        readouts.assert_not_called()
        found,reason=detect_panel_readouts(model,frame,gate,readouts)
        self.assertEqual(found['hdg'],(120,120,100,40));self.assertIsNone(reason)
        readouts.return_value={'hdg':(20,20,100,40)}
        self.assertEqual(detect_panel_readouts(model,frame,gate,readouts)[0],{})

    def test_generic_coco_weights_cannot_be_used_as_panel_detector(self):
        from mcp_yolo_gate import validate_detector
        from types import SimpleNamespace
        validate_detector(SimpleNamespace(names={0:'mcp'}))
        with self.assertRaises(ValueError):validate_detector(SimpleNamespace(names={0:'person',1:'bicycle'}))

    def test_comparison_reports_metrics_iou_and_overlays_on_same_test(self):
        import sys,json,torch
        from types import SimpleNamespace
        from contextlib import redirect_stdout
        import io
        from compare_yolo_camera import main
        base=self.data('base',['train','val']);held=self.data('held',['test'])
        old=self.root/'old.pt';old.write_bytes(b'old');new=self.root/'new.pt';new.write_bytes(b'new')
        boxes=SimpleNamespace(xyxy=torch.tensor([[10.,28.,90.,52.]]),conf=torch.tensor([.9]),cls=torch.tensor([0]))
        fake=SimpleNamespace(names={0:'mcp'},val=lambda **kw:SimpleNamespace(box=SimpleNamespace(mp=.8,mr=.9,map50=.7,map=.6)),
            predict=lambda *a,**kw:[SimpleNamespace(boxes=boxes)])
        argv=['compare','--test',str(held),'--old',str(old),'--new',str(new),'--seen',str(base),'--output',str(self.root/'report'),'--device','cpu']
        before=load_dataset(held)['fingerprint']
        with patch.object(sys,'argv',argv),patch('ultralytics.YOLO',return_value=fake),redirect_stdout(io.StringIO()):main()
        report=json.loads((self.root/'report/comparison.json').read_text())
        self.assertEqual(report['models']['new']['mAP50_95'],.6)
        self.assertAlmostEqual(report['models']['new']['mean_top1_iou'],1)
        self.assertEqual(report['delta']['mAP50'],0)
        self.assertTrue((self.root/'report/new/overlays/00000.jpg').exists())
        self.assertEqual(load_dataset(held)['fingerprint'],before)

if __name__=='__main__':unittest.main()
