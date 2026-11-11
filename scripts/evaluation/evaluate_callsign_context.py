"""Paired replay with a pre-existing demo registry; never derive hints from clip gold."""
import hashlib
import importlib.util
import json
import random
import sys
import time
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))
from app.services.speech.context import callsign_context
from app.services.speech.local import LocalWhisper
from app.services.speech.ner import extract_atc
from app.services.structure_rules import normalize, parse_command
spec = importlib.util.spec_from_file_location('slot_eval', ROOT.parent / 'atc-slot-evaluation/scripts/evaluation/evaluate_atc_slots.py')
slot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(slot)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    import torch
    torch.set_num_threads(4)
    folder = ROOT / '.demo/context'
    folder.mkdir(parents=True, exist_ok=True)
    prior = ROOT.parent / 'atc-microphone-modes'
    config_path = prior / '.demo/config.json'
    registry = json.loads(config_path.read_text())['callsigns']
    context = callsign_context(registry, 3)
    assert context['enabled']
    manifest_path = prior / '.demo/real-atc/manifest.json'
    original = json.loads(manifest_path.read_text())
    # These three aliases were registered for a PREVIOUS demo using these clips.
    # This is a known-vocabulary replay, not an independent accuracy estimate.
    known_labels = [(['german wings seven papa'], [40]), (['lufthansa one kilo k'], [300]), (['speed bird eight two zero'], [80])]
    clips = []
    for row, (calls, headings) in zip(original, known_labels, strict=True):
        clips.append(dict(id=row['id'], cohort='registered_demo_replay', reference=row['text'],
                          CALLSIGN=calls, ALT=[], HDG=headings, path=str(prior / '.demo/real-atc' / row['file'])))
    gold_path = ROOT.parent / 'atc-slot-evaluation/docs/evaluation/atc-slot-gold-2026-11-10.json'
    gold = json.loads(gold_path.read_text())['rows']
    registered = {slot.call_key(a) for a in context['aliases']}
    rng = random.Random(20261112)
    for dataset, count in [('tower60', 6), ('altitude15', 3), ('heading13_diagnostic', 3)]:
        pool = [r for r in gold if r['set'] == dataset and r['CALLSIGN'] and not any(slot.call_key(c) in registered for c in r['CALLSIGN'])]
        assert len(pool) >= count, (dataset, len(pool))
        for row in rng.sample(pool, count):
            base = ROOT.parent / ('atc-unseen-whisper/.demo/unseen/audio' if dataset == 'tower60' else 'atc-slot-evaluation/.demo/slots/audio')
            clips.append({**row, 'cohort': 'outside_registry', 'path': str(base / (row['id']+'.wav'))})
    for row in gold:
        if row['set'] == 'tower60' and row['CALLSIGN'] == []:
            clips.append({**row, 'cohort': 'no_callsign', 'path': str(ROOT.parent / 'atc-unseen-whisper/.demo/unseen/audio' / (row['id']+'.wav'))})
    assert len(clips) == 23
    silence = folder / 'silence.wav'
    with wave.open(str(silence), 'wb') as out:
        out.setparams((1,2,16000,0,'NONE','not compressed'))
        out.writeframes(b'\x00\x00'*16000*3)
    clips.append(dict(id='synthetic-silence-3s', cohort='synthetic_silence', reference='', CALLSIGN=[], ALT=[], HDG=[], path=str(silence)))
    for row in clips:
        digest = sha(Path(row['path']))
        expected = row.get('audio_sha256') or next((x['sha256'] for x in original if x['id']==row['id']), None)
        if expected: assert digest == expected
        row['audio_sha256'] = digest
    model_path = ROOT.parent / 'atc-specialist-comparison/.demo/specialist/models/whisper-atc-turbo-ct2'
    bert = ROOT.parent / 'bert-hybrid-stt/.demo/bert-hybrid-model'
    plan = dict(context=context, registry=registry, config_sha256=sha(config_path), gold_sha256=sha(gold_path),
                manifest_sha256=sha(manifest_path), model_sha256=sha(model_path/'model.bin'), bert_sha256=sha(bert/'model.safetensors'),
                seed=20261112, caveat='Registered three clips are previous curated demo replay; 20 other real clips are regression negatives, not fresh accuracy test.',
                clips=[{k:v for k,v in r.items() if k!='path'} for r in clips])
    plan_path = folder/'plan.json'
    assert not (folder/'results.json').exists(), 'Do not overwrite an earlier experiment'
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2)+'\n')
    model = LocalWhisper(str(model_path))
    result = dict(plan=plan, plan_sha256=sha(plan_path), script_sha256=sha(Path(__file__)),
                  source_hashes={str(p.relative_to(ROOT)):sha(p) for p in (ROOT/'backend/app/services/speech').glob('*.py')}, rows=[])
    for clip in clips:
        for condition in ('without_context', 'with_context'):
            start = time.perf_counter()
            output = model.transcribe(clip['path'], callsign_context=context if condition == 'with_context' else None)
            raw = extract_atc(output['transcript'], bert, backend='bert-hybrid') if output['transcript'].strip() else dict(entities=[],issues=['NO_SPEECH'])
            predicted = dict(CALLSIGN=[],ALT=[],HDG=[])
            for entity in raw['entities']:
                kind = entity['label']
                if kind == 'CALLSIGN': predicted[kind].append(slot.call_key(entity['text']))
                elif kind in ('ALT','HDG'):
                    values, issues = parse_command(('maintain ' if kind=='ALT' else 'heading ')+normalize(entity['text']))
                    predicted[kind].append(values[kind] if not issues and set(values)=={kind} else 'UNRESOLVED')
            scores = {k:slot.scored([slot.call_key(c) for c in clip[k]] if k=='CALLSIGN' else clip[k], predicted[k]) for k in predicted}
            tokens = output['transcript'].split()
            spans = {slot.call_key(' '.join(tokens[i:j])) for i in range(len(tokens)) for j in range(i+1,len(tokens)+1)}
            result['rows'].append(dict(id=clip['id'],cohort=clip['cohort'],condition=condition,**output,
                                       entities=raw['entities'],issues=raw['issues'],predicted=predicted,scores=scores,
                                       gold_callsign_present=all(slot.call_key(c) in spans for c in clip['CALLSIGN']),
                                       registered_callsign_mentions=sorted(registered & spans), seconds=time.perf_counter()-start))
            (folder/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
            print(len(result['rows']), '/', len(clips)*2, clip['cohort'], condition, output['transcript'], flush=True)
    assert sha(plan_path)==result['plan_sha256']

if __name__ == '__main__':
    main()
