#!/usr/bin/env python3
"""Real API insertions, worst-case single-scope cardinality; no external LLM."""
import argparse,json,math,sqlite3,statistics,sys,time
from datetime import datetime,timedelta,timezone
from pathlib import Path
try:
 import resource
except ImportError:
 resource = None
p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();sys.path.insert(0,str(a.root/'scripts'))
from memory_core import Context,Memory,canonical,iso
out=a.out;out.mkdir(parents=True,exist_ok=True);db=out/'density.sqlite3'
if db.exists():raise SystemExit('Refusing to overwrite database')
ctx=Context('density-owner','subject-a');base=datetime(2026,10,24,tzinfo=timezone.utc);now=base+timedelta(days=3653)
rows=[];start=time.perf_counter();m=Memory(db)
def percentile(xs,p):return sorted(xs)[math.ceil(p*len(xs))-1]
def obs(i,v):
 t=base+timedelta(microseconds=i)
 return {'event_id':f'e-{i}','evidence_id':f's-{i}','scope':'food','concept_id':f'food:{i:05}','label':f'合成偏好 {i:05}','kind':'explicit','value':v,'role':'user','mode':'real','observed_at':iso(t)}
current=0
for total in (100,1000,10000,36530):
 t=time.perf_counter()
 for i in range(current,total):
  e=obs(i,.9 if i==0 else .01 if i==1 else .1);m.observe(ctx,e,now=now)
 elapsed=time.perf_counter()-t;current=total
 m.conn.execute('PRAGMA wal_checkpoint(TRUNCATE)')
 default=[];target=[];checks=[]
 for i in range(20):
  t=time.perf_counter_ns();q=m.compile(ctx,['food'],now=now);default.append((time.perf_counter_ns()-t)/1e6)
  t=time.perf_counter_ns();r=m.compile(ctx,['food'],now=now,concept_ids=['food:00001']);target.append((time.perf_counter_ns()-t)/1e6)
  checks.append(any(x['concept_id']=='food:00000' for x in q['items']) and r['items'][0]['concept_id']=='food:00001' and len(canonical(q))<=6000 and len(canonical(r))<=6000)
 row={'persisted_concepts':total,'new_insertion_seconds':elapsed,'default_compile_p50_ms':statistics.median(default),'default_compile_p95_ms':percentile(default,.95),'target_compile_p50_ms':statistics.median(target),'target_compile_p95_ms':percentile(target,.95),'samples_each':20,'last_compile_stats':getattr(m,'last_compile_stats',{}),'default_delivered':len(q['items']),'omitted_count':q['omitted_count'],'old_anchor_delivered':any(x['concept_id']=='food:00000' for x in q['items']),'target_delivered':r['items'][0]['concept_id']=='food:00001','checks_passed':all(checks),'database_bytes':db.stat().st_size,'elapsed_seconds':time.perf_counter()-start}
 rows.append(row);print(json.dumps(row,ensure_ascii=False),flush=True)
 result={'test':'synthetic single-user single-scope density','rows':rows,'api_calls_total':current,'limitations':['One scope packed with tens of thousands of synthetic concepts is a boundary load, not a claim about real user preference count.','Measured API read uses exact state data; no model answering is measured.','v0.2 compile uses an indexed bounded pool; full get listing remains unbounded. Large sets of concurrently active overlays need separate evaluation.']};(out/'density_result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
assert m.conn.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
m.close()
