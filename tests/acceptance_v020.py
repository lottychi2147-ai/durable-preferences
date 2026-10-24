#!/usr/bin/env python3
"""Independent product probes. Run unchanged against old and new skill roots.
Thresholds are engineering gates chosen before running, not psychological scales.
"""
from __future__ import annotations
import argparse,json,random,sys,tempfile,hashlib,platform,time
from datetime import datetime,timedelta,timezone
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
sys.path.insert(0,str(a.root/'scripts'))
from memory_core import Memory,Context,iso,canonical
BASE=datetime(2026,10,24,tzinfo=timezone.utc);CTX=Context('acceptance','subject-a')
cases=[]
def scenario(name,days,values,initial=None,threshold=None,expect_unknown=False):
    with tempfile.TemporaryDirectory() as td,Memory(Path(td)/'m.db') as m:
        def put(i,d,k,v):
            t=BASE+timedelta(days=d,seconds=1)
            e={'event_id':str(i),'evidence_id':'source-'+str(i),'scope':'food','concept_id':'food:target','label':'測試食物','role':'user','mode':'real','kind':k,'value':v,'observed_at':iso(t)}
            return m.observe(CTX,e,now=t)
        if initial is not None:put('init',-1,'explicit',initial)
        trace=[];first_formation=None;first_reversal=None
        for i,(d,v) in enumerate(zip(days,values)):
            r=put(i,d,'feedback',v);s=m._load(CTX,'food','food:target')
            if first_formation is None and s['stable'] is not None:first_formation={'event':i+1,'day':d}
            if initial and first_reversal is None and s['stable'] is not None and s['stable']*initial<0:first_reversal={'event':i+1,'day':d}
            trace.append({'event':i+1,'day':d,'value':v,'stable':s['stable'],'status':r['status'],'route':s.get('long_evidence',{}).get('last_route')})
        final=m.get(CTX,['food'],now=BASE+timedelta(days=max(days)+366))['items'][0]
        val=final['stable']
        passed=val is None if expect_unknown else (val is not None and (val>threshold if threshold>=0 else val<threshold))
        cases.append({'name':name,'passed':passed,'events':len(days),'intervals_days':sorted(set(y-x for x,y in zip(days,days[1:]))),'initial':initial,'stable':val,'familiarity_count':final['familiarity_count'],'gate':'unknown' if expect_unknown else ('>'+str(threshold) if threshold>=0 else '<'+str(threshold)),'first_formation':first_formation,'first_reversal':first_reversal,'trace':trace})

scenario('quarterly_positive_from_unknown',[i*90 for i in range(41)],[1]*41,threshold=.5)
scenario('quarterly_negative_from_unknown',[i*90 for i in range(41)],[-1]*41,threshold=-.5)
scenario('quarterly_negative_reverses_known_positive',[i*90 for i in range(41)],[-1]*41,initial=.9,threshold=-.5)
scenario('quarterly_positive_reverses_known_negative',[i*90 for i in range(41)],[1]*41,initial=-.9,threshold=.5)
for gap in (61,180,365):
    days=list(range(0,3653,gap));scenario('positive_every_'+str(gap)+'_days',days,[.8]*len(days),threshold=.5)
rng=random.Random(601);days=[];d=0
while d<3653:days.append(d);d+=rng.randint(70,330)
scenario('irregular_sparse_positive',days,[.8]*len(days),threshold=.5)
scenario('balanced_alternating_quarterly',[i*90 for i in range(40)],[(-1)**i for i in range(40)],expect_unknown=True)
scenario('only_three_annual_experiences',[0,365,730],[1]*3,expect_unknown=True)
scenario('dense_learning_still_works',list(range(4)),[1]*4,threshold=.5)
scenario('twelve_dense_negative_reversals',list(range(12)),[-1]*12,initial=.9,threshold=-.5)
scenario('hundred_positive_then_thousand_negative',list(range(1100)),[1]*100+[-1]*1000,threshold=-.95)
scenario('history_does_not_outvote_twelve_sparse_reversals',list(range(1000))+[1000+i*90 for i in range(1,13)],[1]*1000+[-1]*12,threshold=-.5)
scenario('one_bad_experience_does_not_erase_positive',list(range(40))+[4000],[1]*40+[-1],threshold=.8)
scenario('quarterly_positive_with_ten_percent_marked_sign_noise',[i*90 for i in range(40)],([1,1,-1,1,1,1,1,1,1,1])*4,threshold=.5)
result={'root':str(a.root),'core_sha256':hashlib.sha256((a.root/'scripts/memory_core.py').read_bytes()).hexdigest(),'passed':sum(c['passed'] for c in cases),'total':len(cases),'cases':cases,'limitations':['Structured signal inputs only. No natural-language classifier or live-model answer is tested.','Intervals 61/90/180/365 and irregular are pre-specified probes, not a guarantee for every user.','Thresholds are acceptance gates, not calibrated psychological measures.']}
a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2))
print(json.dumps({k:result[k] for k in ('passed','total','core_sha256')}))
for c in cases:print('PASS' if c['passed'] else 'FAIL',c['name'],c['stable'])
