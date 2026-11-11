"""Audit the complete paired evaluation and calculate corpus WER with paired bootstrap."""
import argparse
import json
from pathlib import Path
import random
import statistics

from compare_unseen_whisper import metrics, sha, words
from prepare_unseen_atc import ID, group



def error_types(reference, hypothesis):
    """Deterministic minimum-edit alignment; ties prefer match/substitution."""
    ref,hyp=words(reference),words(hypothesis)
    dp=[[0]*(len(hyp)+1) for _ in range(len(ref)+1)]
    for i in range(len(ref)+1):dp[i][0]=i
    for j in range(len(hyp)+1):dp[0][j]=j
    for i in range(1,len(ref)+1):
        for j in range(1,len(hyp)+1):
            dp[i][j]=min(dp[i-1][j-1]+(ref[i-1]!=hyp[j-1]),dp[i-1][j]+1,dp[i][j-1]+1)
    out={'substitutions':0,'deletions':0,'insertions':0};i,j=len(ref),len(hyp)
    while i or j:
        if i and j and dp[i][j]==dp[i-1][j-1]+(ref[i-1]!=hyp[j-1]):
            out['substitutions']+=ref[i-1]!=hyp[j-1];i-=1;j-=1
        elif i and dp[i][j]==dp[i-1][j]+1:out['deletions']+=1;i-=1
        else:out['insertions']+=1;j-=1
    return out


def summary(rows):
    m=[x['metrics'] for x in rows]
    operations=[error_types(x['reference'],x['transcript']) for x in rows]
    assert all(sum(o.values())==v['errors'] for o,v in zip(operations,m))
    errors=sum(x['errors'] for x in m);n=sum(x['reference_words'] for x in m)
    numeric_n=sum(x['numeric_reference_tokens'] for x in m)
    return {'n':len(rows),'errors':errors,'reference_words':n,'wer':errors/n,
        'error_types':{k:sum(o[k] for o in operations) for k in ('substitutions','deletions','insertions')},
        'lexical_wer':sum(x['lexical_errors'] for x in m)/sum(x['lexical_words'] for x in m),
        'exact_utterances':sum(x['exact'] for x in m),
        'median_utterance_wer':statistics.median(x['errors']/x['reference_words'] for x in m),
        'utterances_wer_over_100_percent':sum(x['errors']>x['reference_words'] for x in m),
        'numeric_token_error_rate':sum(x['numeric_errors'] for x in m)/numeric_n,
        'numeric_reference_tokens':numeric_n,
        'numeric_sequence_exact':sum(x['numeric_sequence_exact'] for x in m),
        'numeric_nonempty_count':sum(x['numeric_reference_tokens']>0 for x in m),
        'numeric_nonempty_exact':sum(x['numeric_sequence_exact'] for x in m if x['numeric_reference_tokens']>0),
        'median_seconds':statistics.median(x['seconds'] for x in rows),
        'total_seconds':sum(x['seconds'] for x in rows),
        'audio_seconds':sum(x['duration'] for x in rows)}


def bootstrap(pairs, count=10000):
    rng=random.Random(20261110);diff=[]
    for _ in range(count):
        sample=[rng.choice(pairs) for _ in pairs]
        numerator=sum(b['metrics']['errors']-a['metrics']['errors'] for a,b in sample)
        denominator=sum(a['metrics']['reference_words'] for a,b in sample)
        diff.append(numerator/denominator)
    diff.sort()
    return {'method':'paired recording-group percentile bootstrap; one utterance per group',
        'seed':20261110,'draws':count,'difference':'specialist minus generic WER',
        'lower_95':diff[int(count*.025)],'upper_95':diff[int(count*.975)-1]}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--plan',type=Path,required=True);p.add_argument('--results',type=Path,required=True)
    p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--communication',type=Path,required=True)
    p.add_argument('--fallback',type=Path)
    a=p.parse_args();plan=json.loads(a.plan.read_text());r=json.loads(a.results.read_text())
    assert r['plan_sha256']==sha(a.plan)
    clips={c['id']:c for c in plan['clips']};assert len(clips)==60
    prior_ids=set()
    for item in plan['prior_files']:
        path=a.communication/item['path'];assert sha(path)==item['sha256']
        prior_ids.update(ID.findall(path.read_text(errors='replace')))
    assert len(prior_ids)==plan['prior_ids']
    assert not {group(i) for i in prior_ids}.intersection(c['group'] for c in clips.values())
    assert len({c['group'] for c in clips.values()})==60
    assert len({c['sha256'] for c in clips.values()})==60
    assert len({tuple(words(c['reference'])) for c in clips.values()})==60
    for c in clips.values():assert sha(a.plan.parent/c['file'])==c['sha256']
    expected={(i,m) for i in clips for m in ['generic','specialist']}
    assert len(r['rows'])==120 and {(x['id'],x['model']) for x in r['rows']}==expected
    for x in r['rows']:
        c=clips[x['id']]
        assert x['audio_sha256']==c['sha256'] and x['reference']==c['reference']
        assert x['metrics']==metrics(x['reference'],x['transcript'])
    by={(x['id'],x['model']):x for x in r['rows']}
    pairs=[(by[(i,'generic')],by[(i,'specialist')]) for i in clips]
    out={'source':json.loads(a.source.read_text()),'plan':plan,'exclusion_audit':{'verified_prior_files':len(plan['prior_files']),'verified_prior_ids':len(prior_ids),'selected_recording_overlap':0},'experiment':r,
        'summary':{m:summary([x for x in r['rows'] if x['model']==m]) for m in ['generic','specialist']},
        'paired_bootstrap':bootstrap(pairs),
        'pair_counts':{'specialist_better':sum(b['metrics']['errors']<a['metrics']['errors'] for a,b in pairs),
                       'tie':sum(b['metrics']['errors']==a['metrics']['errors'] for a,b in pairs),
                       'specialist_worse':sum(b['metrics']['errors']>a['metrics']['errors'] for a,b in pairs)},
        'limits':['Unseen in audited local selected training/evaluation records; not proof of exclusion from Whisper pretraining.',
                  'Specialist declares ATCO2+ATCOSIM fine-tuning; exact training file manifest unavailable.',
                  'Numeric metric is ordered number-word token comparison across the whole utterance, not callsign/ALT/HDG value accuracy.',
                  'Same-corpus TWR sample, not new airport or speaker-disjoint guarantee; no new microphone capture.',
                  'No downstream NER, server adoption or operational accuracy evaluation.']}
    if a.fallback:
        follow=json.loads(a.fallback.read_text())
        assert follow['primary_sha256']==sha(a.results) and follow['plan_sha256']==sha(a.plan)
        selected={x['id'] for x in r['rows'] if x['metrics']['errors']>x['metrics']['reference_words']}
        expected_follow={(i,m) for i in selected for m in ['generic','specialist']}
        assert len(follow['rows'])==len(expected_follow)
        assert {(x['id'],x['model']) for x in follow['rows']}==expected_follow
        for x in follow['rows']:
            assert x['reference']==clips[x['id']]['reference']
            assert x['metrics']==metrics(x['reference'],x['transcript'])
            x['duration']=clips[x['id']]['duration']
        follow['summary']={m:summary([x for x in follow['rows'] if x['model']==m]) for m in ['generic','specialist']}
        follow['primary_same_subset']={m:summary([x for x in r['rows'] if x['id'] in selected and x['model']==m]) for m in ['generic','specialist']}
        out['posthoc_fallback']=follow
        print('POSTHOC',json.dumps(follow['summary'],indent=2))
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:out[k] for k in ('summary','paired_bootstrap','pair_counts')},indent=2))

if __name__=='__main__':main()
