#!/usr/bin/env python3
"""Print v7 entities without creating a clearance."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from app.services.speech.ner import extract_atc
if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('text');parser.add_argument('--model',help='v7 directory; defaults to RADAR_NER_MODEL')
    args=parser.parse_args()
    print(json.dumps(extract_atc(args.text,args.model),ensure_ascii=False,indent=2))
