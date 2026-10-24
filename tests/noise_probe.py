#!/usr/bin/env python3
"""Exploratory signal-noise sweep; NOT a validated natural-language benchmark.
50% contradictory real-labelled feedback is deliberately uninformative.
Keep its false-certainty results, not only successful easy cases.
"""
from pathlib import Path
import argparse,json,random,sys,tempfile
from datetime import datetime,timedelta,timezone
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from memory_core import Memory,Context,iso
p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
base=datetime(2026,10,24,tzinfo=timezone.utc);ctx=Context('noise-probe','demo');rows=[]
for noise in (0.0,.1,.3,.5):
    samples=[]
    for seed in range(24):
        rng=random.Random(7000+seed)
        with tempfile.TemporaryDirectory() as td,Memory(Path(td)/'m.db') as m:
            for n in range(41):
                value=-1 if rng.random()<noise else 1;t=base+timedelta(days=n*90)
                m.observe(ctx,{'event_id':str(n),'evidence_id':str(n),'scope':'food','concept_id':'food:test','label':'合成食物','kind':'feedback','value':value,'role':'user','mode':'real','observed_at':iso(t)},now=t)
            state=m.get(ctx,now=t)['items'][0];packet=m.compile(ctx,['food'],now=t)
            samples.append({'seed':seed,'stable':state['stable'],'mixed_evidence':state.get('mixed_evidence',False),'packet_uncertainty':any('uncertainty' in i for i in packet['items'])})
    rows.append({'sign_flip_rate':noise,'seeds':24,'strong_positive':sum(x['stable'] is not None and x['stable']>.5 for x in samples),'strong_negative':sum(x['stable'] is not None and x['stable']<-.5 for x in samples),'unknown':sum(x['stable'] is None for x in samples),'mixed_flag':sum(x['mixed_evidence'] for x in samples),'samples':samples})
r={'kind':'exploratory_not_acceptance','rows':rows,'limitations':['Fixed reducer heuristic, no parameter tuning on this sweep.','At 50% sign-flips there is no reliable preference evidence; any strong conclusion demonstrates finite-sample/selection risk.','Does not measure natural-language classification or model answer quality.']}
a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,ensure_ascii=False,indent=2));print(json.dumps([{k:v for k,v in x.items() if k!='samples'} for x in rows]))
