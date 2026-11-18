import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image, ImageDraw
from mcp_dataset import FIELDS, validate_dataset, disjoint, separate_output
from mcp_camera_presets import collection_plan, V6_TRAIN, V6_TEST
from finetune_camera_mcp import prepare, verify_plan
from mcp_preprocessing import prepare_camera_crop, normalize_aligned

class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.counter=0

    def dataset(self,name, splits=('train',),paired=True):
        root=self.root/name;root.mkdir();rows=[]
        for split in splits:
            for kind,text in [('hdg','123'),('alt','04500')]:
                self.counter+=1
                rel=f'{split}_{kind}.png'
                Image.new('RGB',(108 if kind=='hdg' else 180,48),(self.counter,20,30)).save(root/rel)
                rows.append(dict(image_path=rel,kind=kind,text=text,split=split,
                    session_id=f'{name}_{split}',source_image=split))
        self.write(root,rows);return root

    def write(self,root,rows):
        with (root/'labels.csv').open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=FIELDS);w.writeheader();w.writerows(rows)

    def test_presets_legacy_unchanged_and_v6_separate(self):
        old,n,s=collection_plan(True);self.assertEqual((len(old)*n,n,s),(120,15,'train'))
        for split,total in [('train',160),('test',40)]:
            plan,n,result=collection_plan(v6=split);self.assertEqual((len(plan)*n,n,result),(total,20,split))
        self.assertFalse(set(V6_TRAIN)&set(V6_TEST))
        with self.assertRaises(ValueError):collection_plan(True,'test')

    def test_bad_labels_missing_duplicate_and_incomplete(self):
        root=self.dataset('bad'); rows=validate_dataset(root,{'train'},True)['rows']
        for patch_value in ['12','360','１２３','-01']:
            changed=[dict(r) for r in rows];changed[0]['text']=patch_value;self.write(root,changed)
            with self.assertRaises(ValueError):validate_dataset(root,{'train'},True)
        self.write(root,rows+[rows[0]])
        with self.assertRaises(ValueError):validate_dataset(root,{'train'},True)
        self.write(root,rows[:1])
        with self.assertRaises(ValueError):validate_dataset(root,{'train'},True)
        self.write(root,rows);(root/rows[0]['image_path']).unlink()
        with self.assertRaises(ValueError):validate_dataset(root,{'train'},True)

    def test_cross_dataset_pixels_and_session_leakage(self):
        a=self.dataset('a');b=self.dataset('b',('test',))
        da=validate_dataset(a,{'train'},True);db=validate_dataset(b,{'test'},True)
        disjoint([da,db])
        with self.assertRaises(ValueError):disjoint([da,da])
        rows=db['rows'];rows[0]['session_id']=rows[1]['session_id']='a_train';self.write(b,rows)
        with self.assertRaises(ValueError):disjoint([da,validate_dataset(b,{'test'},True)])
        rows[0]['session_id']=rows[1]['session_id']='b_test';self.write(b,rows)
        (b/rows[0]['image_path']).write_bytes((a/da['rows'][0]['image_path']).read_bytes())
        with self.assertRaises(ValueError):disjoint([da,validate_dataset(b,{'test'},True)])

    def test_merge_multiple_batches_preserves_base_and_excludes_camera_test(self):
        base=self.dataset('base',('train','val','test'));a=self.dataset('old');b=self.dataset('new');test=self.dataset('heldout',('test',))
        initial=self.root/'v5';initial.mkdir()
        for kind in ('hdg','alt'):(initial/f'{kind}_best.pt').write_bytes(b'unchanged')
        base_rows=validate_dataset(base,{'train','val','test'})['rows']
        extras=['crop_x1','crop_y1','crop_x2','crop_y2']
        for row in base_rows:row.update(dict(zip(extras,['10','20','118','68'])))
        with (base/'labels.csv').open('w',newline='') as fp:
            writer=csv.DictWriter(fp,fieldnames=FIELDS+extras);writer.writeheader();writer.writerows(base_rows)
        merged=prepare(base,[a,b],initial,self.root/'v6',test)
        with (merged/'labels.csv').open() as fp:
            output_rows=list(csv.DictReader(fp))
        self.assertEqual(output_rows[0]['crop_x1'],'10')
        self.assertEqual(output_rows[-1]['crop_x1'],'')
        data=validate_dataset(merged,{'train','val','test'})
        self.assertEqual(len(data['rows']),10)
        self.assertEqual(sum(r['split']=='train' for r in data['rows']),6)
        self.assertFalse(any('heldout' in r['source_image'] for r in data['rows']))
        self.assertEqual((initial/'hdg_best.pt').read_bytes(),b'unchanged')
        with self.assertRaises(ValueError):prepare(base,[a,b],initial,self.root/'v6',test)
        with self.assertRaises(ValueError):separate_output(base/'nested',[base])
        with self.assertRaises(ValueError):separate_output(self.root,[base])

    def test_crop_audit_preserves_truth_and_tracks_digit_confusion(self):
        from audit_camera_ocr import build
        dataset=self.dataset('diagnostic',('test',))
        rows=validate_dataset(dataset,{'test'},paired=True)['rows']
        comparison=self.root/'reports'
        for model in ('v5','v6'):
            folder=comparison/model;folder.mkdir(parents=True)
            with (folder/'predictions.csv').open('w',newline='') as fp:
                writer=csv.DictWriter(fp,fieldnames=['image_path','kind','truth','prediction'])
                writer.writeheader()
                for row in rows:writer.writerow(dict(image_path=row['image_path'],kind=row['kind'],truth=row['text'],prediction='9'+row['text'][1:]))
        original=(dataset/'labels.csv').read_bytes()
        summary=build(dataset,comparison,self.root/'audit')
        self.assertEqual(summary['samples'],2)
        self.assertEqual((dataset/'labels.csv').read_bytes(),original)
        self.assertEqual(summary['label_changes'],0)
        confusion=json.loads((self.root/'audit/confusions.json').read_text())
        self.assertEqual(len(confusion),4)
        self.assertTrue(all(r['position']==1 for r in confusion))

    def test_camera_validation_is_separate_and_preserves_synthetic_splits(self):
        from train_mcp_ocr_v2 import validation_rows
        base=self.dataset('base',('train','val','test'))
        train=self.dataset('camera');development=self.dataset('development',('test',))
        initial=self.root/'v5';initial.mkdir()
        for kind in ('hdg','alt'):(initial/f'{kind}_best.pt').write_bytes(b'original')
        merged=prepare(base,[train],initial,self.root/'candidate',camera_val=development)
        data=validate_dataset(merged,{'train','val','test'})
        self.assertEqual(sum(r['split']=='test' for r in data['rows']),2)
        self.assertEqual(sum(r['split']=='val' for r in data['rows']),4)
        for kind in ('hdg','alt'):
            selected=validation_rows(data['rows'],kind,True)
            self.assertEqual(len(selected),1)
            self.assertTrue(selected[0]['session_id'].startswith('camera_val:'))
        with self.assertRaises(ValueError):
            prepare(base,[train],initial,self.root/'bad',development,camera_val=development)
        self.assertFalse((self.root/'bad').exists())

    def test_same_camera_pixels_and_training_tensor(self):
        import numpy as np
        from camera_digit_preprocess import camera_to_amber
        from preprocess_mcp_ocr import align
        image=Image.new('RGB',(240,70),(12,14,16));draw=ImageDraw.Draw(image)
        for x in [20,90,160]:draw.rectangle((x,15,x+24,55),fill='white')
        actual=prepare_camera_crop(image,'hdg');self.assertIsNotNone(actual)
        expected=align(camera_to_amber(image),'hdg')
        self.assertTrue(np.array_equal(np.asarray(actual),np.asarray(expected)))
        path=self.root/'aligned.png';actual.save(path)
        with Image.open(path) as saved:
            self.assertTrue(np.array_equal(np.asarray(normalize_aligned(saved,'hdg')),np.asarray(normalize_aligned(actual,'hdg'))))

    def test_v6_runtime_uses_camera_contract_without_changing_default(self):
        import numpy as np
        from vision.ocr_v3_runtime import OCRv3
        image=Image.new('RGB',(240,70),(12,14,16));draw=ImageDraw.Draw(image)
        for x in [20,90,160]:draw.rectangle((x,15,x+24,55),fill='white')
        class StopModel:
            def __call__(self,tensor):
                self.tensor=tensor
                raise RuntimeError('tensor captured')
        model=StopModel();runtime=OCRv3.__new__(OCRv3)
        runtime.models={'hdg':model};runtime.preprocessing={'hdg':'camera_amber_align_v1'}
        with self.assertRaisesRegex(RuntimeError,'tensor captured'):runtime.infer(image,'hdg')
        expected=np.asarray(normalize_aligned(prepare_camera_crop(image,'hdg'),'hdg'),dtype='float32')/255
        self.assertTrue(np.array_equal(model.tensor.numpy()[0,0],expected))

    def test_collection_test_plan_40_pairs_and_ack_failure_blocks(self):
        import sys
        import numpy as np
        import cv2
        import collect_camera_mcp
        from contextlib import ExitStack, redirect_stdout
        import io
        def run(name,ready,keys):
            root=self.root/name
            class Camera:
                index=0
                def isOpened(self):return True
                def read(self):
                    self.index+=1
                    return True,np.full((100,300,3),self.index,dtype=np.uint8)
                def release(self):pass
            with ExitStack() as stack:
                stack.enter_context(patch.object(sys,'argv',['collect','--output',str(root),
                    '--display-id','tablet','--v6-plan','test','--session-id',name,'--auto-interval','0']))
                sync=stack.enter_context(patch('mcp_display_sync.DisplaySync')).return_value
                sync.ready.return_value=ready
                stack.enter_context(patch.object(cv2,'VideoCapture',return_value=Camera()))
                stack.enter_context(patch.object(cv2,'waitKey',side_effect=keys))
                for method in ('imshow','destroyAllWindows','rectangle','putText'):
                    stack.enter_context(patch.object(cv2,method))
                stack.enter_context(patch('auto_detect_mcp.detect_readouts',return_value={'hdg':(0,0,108,48),'alt':(110,0,180,48)}))
                stack.enter_context(patch('mcp_preprocessing.prepare_camera_crop',side_effect=lambda im,kind: im))
                stack.enter_context(patch('builtins.input',return_value=''))
                stack.enter_context(redirect_stdout(io.StringIO()))
                collect_camera_mcp.main()
            return root,sync
        root,sync=run('testsession',True,[32]*20+[ord('n')]+[32]*20)
        verify_plan(root,V6_TEST,'test')
        self.assertEqual(sync.set.call_args_list[0].args,('032','00600'))
        self.assertEqual(sync.set.call_args_list[-1].args,('264','28400'))
        blocked,_=run('blocked',False,[32,ord('q')])
        with (blocked/'labels.csv').open() as fp:self.assertEqual(len(list(csv.DictReader(fp))),0)
        run('blocked',False,[ord('q')])
        with (blocked/'labels.csv').open() as fp:self.assertEqual(len(list(csv.DictReader(fp))),0)
        run('blocked',True,[32,ord('q')])
        resumed=validate_dataset(blocked,{'test'},paired=True)
        self.assertEqual(len(resumed['rows']),2)


    def test_v6_cli_reserves_test_and_enforces_counts(self):
        import sys
        import io
        from contextlib import redirect_stdout
        from finetune_camera_mcp import main
        base=self.dataset('base',('train','val','test'))
        def batch(name,presets,n,split,v6):
            root=self.root/name;root.mkdir();rows=[]
            for i,(h,a) in enumerate(pair for pair in presets for _ in range(n)):
                for kind,text in [('hdg',h),('alt',a)]:
                    self.counter+=1;rel=f'{kind}_{i}.png'
                    color=(self.counter%256,(self.counter//256)%256,80)
                    Image.new('RGB',(108 if kind=='hdg' else 180,48),color).save(root/rel)
                    rows.append(dict(image_path=rel,kind=kind,text=text,split=split,session_id=name,source_image=str(i)))
            self.write(root,rows)
            if v6:(root/'collection.json').write_text(json.dumps(dict(plan='v6',split=split,session_id=name,preprocessing='camera_amber_align_v1')))
            return root
        old=batch('old',[('270','03000')],120,'train',False)
        new=batch('new',V6_TRAIN,20,'train',True)
        test=batch('heldout',V6_TEST,20,'test',True)
        initial=self.root/'v5';initial.mkdir()
        for kind in ('hdg','alt'):(initial/f'{kind}_best.pt').write_bytes(b'original')
        argv=['finetune','--v6','--base',str(base),'--camera',str(old),'--camera',str(new),
              '--real-test',str(test),'--init-checkpoints',str(initial),'--output',str(self.root/'v6'),'--epochs','12']
        with patch.object(sys,'argv',argv),patch('finetune_camera_mcp.subprocess.run') as run,redirect_stdout(io.StringIO()):
            main()
        self.assertEqual(run.call_count,2) # trainer + synthetic diagnostic, no held-out evaluation
        self.assertIn('--camera-preprocessing',run.call_args_list[0].args[0])
        merged=validate_dataset(self.root/'v6/merged_training_data',{'train','val','test'})
        self.assertEqual(sum(r['split']=='train' for r in merged['rows']),562) # 280 camera pairs + 2 base rows
        self.assertFalse(any(str(test) in arg for call in run.call_args_list for arg in call.args[0]))

    def test_plan_wrong_counts_rejected(self):
        root=self.dataset('short')
        with self.assertRaises(ValueError):verify_plan(root,V6_TRAIN,'train')

if __name__=='__main__':unittest.main()
