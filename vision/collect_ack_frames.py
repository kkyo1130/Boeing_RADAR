"""Collect all scheduled browser-camera frames after a selected display render ACK.
No OCR outputs are labels. Raw failures are retained for detection/OCR evaluation.
"""
import argparse
import hashlib
import json
import shutil
import time
from pathlib import Path
try:from .mcp_display_sync import DisplaySync
except ImportError:from mcp_display_sync import DisplaySync


def fresh_frame(image, metadata, after, max_age=6):
    info=json.loads(metadata.read_text());raw=image.read_bytes()
    if info['request_started'] < after or time.time()-info['request_started']>max_age:return None
    if hashlib.sha256(raw).hexdigest()!=info['sha256']:return None
    return raw,info


def collect(plan, output, stream, condition, role='train', frames=3, base='http://127.0.0.1:5179'):
    if output.exists():raise ValueError('Fresh session directory required')
    output.mkdir(parents=True);(output/'frames').mkdir()
    sync=DisplaySync(base,'training',1.0);records=[];seen=set()
    manifest=dict(condition=condition,role=role,plan=plan,frames_per_value=frames,
                  label_source='operator_authorized_simulated_display_render_ack',independent_frames=False)
    (output/'session.json').write_text(json.dumps(manifest,indent=2))
    try:
        with (output/'frames.jsonl').open('w') as log:
            for group,(heading,altitude) in enumerate(plan):
                sync.set(f'{heading:03d}',f'{altitude:05d}');deadline=time.monotonic()+20
                while not sync.ready():
                    if time.monotonic()>deadline:raise TimeoutError('Display ACK missing; collection stopped')
                    time.sleep(.1)
                threshold=time.time()+1;deadline=time.monotonic()+30;saved=0
                while saved<frames:
                    if time.monotonic()>deadline:raise TimeoutError('No new synchronized camera frame')
                    if shutil.disk_usage(output).free < 64*1024**2:raise OSError('Low disk; capture stopped')
                    try:item=fresh_frame(stream/'latest.jpg',stream/'latest.json',threshold)
                    except (OSError,ValueError):item=None
                    if item and sync.ready():
                        raw,info=item
                        if info['sha256'] not in seen:
                            path=f'frames/{group:03d}_{saved:02d}.jpg';(output/path).write_bytes(raw)
                            row=dict(path=path,hdg=f'{heading:03d}',alt=f'{altitude:05d}',group=group,
                                     condition=condition,role=role,display_seq=sync.command['seq'],**info)
                            log.write(json.dumps(row)+'\n');log.flush();records.append(row);seen.add(info['sha256']);saved+=1
                            threshold=info['request_started']+.25
                    time.sleep(.15)
                print(json.dumps(dict(group=group+1,total=len(plan),heading=heading,altitude=altitude,frames=saved)),flush=True)
    finally:
        sync.set('270','03000')
        (output/'collection_result.json').write_text(json.dumps(dict(saved=len(records),scheduled=len(plan)*frames,restored_command=[270,3000]),indent=2))
    return records

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--plan',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--stream',type=Path,default=Path('.demo/vision-stream'));p.add_argument('--condition',required=True);p.add_argument('--role',choices=['train','development','final'],default='train');p.add_argument('--frames',type=int,default=3);a=p.parse_args()
    collect(json.loads(a.plan.read_text()),a.output,a.stream,a.condition,a.role,a.frames)
