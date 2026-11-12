#!/usr/bin/env python3
"""Print local NER entities without creating a clearance."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from app.services.speech.ner import extract_atc
if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('text');parser.add_argument('--model',help='local model directory; defaults to RADAR_NER_MODEL')
    parser.add_argument('--backend', choices=['v7','bert-hybrid'], help='defaults to RADAR_NER_BACKEND or v7')
    args=parser.parse_args()
    print(json.dumps(extract_atc(args.text,args.model,backend=args.backend),ensure_ascii=False,indent=2))
