#!/usr/bin/env python3
"""Synthetic ten-year structured events through the actual public APIs.
No LLM calls; no direct SQL insertion of state or history.
"""
from __future__ import annotations
import argparse, collections, gzip, hashlib, json, math, os, platform, random, sqlite3, sys, time
from datetime import datetime, timedelta, timezone
from pathlib import Path
try:
 import resource
except ImportError:
 resource = None
P=argparse.ArgumentParser();P.add_argument('--root',type=Path,required=True);P.add_argument('--out',type=Path,required=True);P.add_argument('--turns-per-day',type=int,default=100);P.add_argument('--seed',type=int,default=20261024);args=P.parse_args()
if args.turns_per_day != 100:
 raise SystemExit('This acceptance workload is validated at 100 turns/day. Define expiry expectations before changing cadence.')
sys.path.insert(0,str(args.root/'scripts'))
from memory_core import Context,Memory,canonical,iso
from host_adapter import LocalPreferenceHost
OUT=args.out;OUT.mkdir(parents=True,exist_ok=True);DB=OUT/'decade.sqlite3'
if DB.exists(): raise SystemExit('Refusing to overwrite existing database')
START=datetime(2026,10,24,tzinfo=timezone.utc);END=datetime(2036,10,24,tzinfo=timezone.utc)
DAYS=(END-START).days;TOTAL=DAYS*args.turns_per_day;rng=random.Random(args.seed)
A=Context('synthetic-owner','subject-a');B=Context('synthetic-owner','subject-b');C=Context('synthetic-owner','subject-a','project-isolated')
SCOPES=['food','casual','work','leisure','travel','shopping','learning','media','routines','devices']
counts=collections.Counter();checks=collections.Counter();failures=[];yearly=[];latencies=[];writes=[];packet_sizes=[]
began=time.perf_counter();m=Memory(DB)
labels={'food:anchor':'長期喜愛雞排（固定測試錨點）','food:changing':'飲食偏好變化測試','food:correction':'明確改口測試','style:length':'回覆長度','style:clarity':'說明清楚'}
def save_json(path,x):path.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
def pct(xs,p):
 s=sorted(xs);return s[max(0,math.ceil(len(s)*p)-1)] if s else None
def ensure(name,condition,info=None):
 checks[name]+=1
 if not condition and len(failures)<100:failures.append({'check':name,'info':info})
def event(event_id,at,scope,concept,kind='mention',value=None,**kwargs):
 e={'event_id':event_id,'evidence_id':'evidence-'+event_id,'scope':scope,'concept_id':concept,'label':labels.get(concept,concept),'kind':kind,'role':'user','mode':'real','observed_at':iso(at)}
 if kind not in ('mention','choice'):e['value']=value
 e.update(kwargs);return e

def audit_store(now,step):
 s=m.get(A,now=now);states={(x['scope'],x['concept_id']):x for x in s['items']}
 ensure('anchor_exact_in_store',states[('food','food:anchor')]['stable']==.85)
 ensure('historical_marker',states[('food','food:anchor')]['freshness']==('historical' if now-START>timedelta(days=365) else 'current'))
 ensure('casual_work_separation',states[('casual','style:length')]['stable']==-.8 and states[('work','style:length')]['stable']==.8)
 ensure('unknown_not_like',states[('food','food:unknown')]['stable'] is None)
 ensure('other_subject_isolation',m.get(B,['food'],now=now)['items'][0]['stable']==-.75)
 ensure('namespace_isolation',m.get(C,['food'],now=now)['items'][0]['stable']==-.35)
 sql=[];m.conn.set_trace_callback(sql.append);m.compile(A,['food'],now=now);m.conn.set_trace_callback(None)
 ensure('no_history_query',not any('journal' in x.lower() or 'receipts' in x.lower() for x in sql))
 ensure('sqlite_quick_check',m.conn.execute('PRAGMA quick_check').fetchone()[0]=='ok')
 return states

initial=[('core','style:clarity',.8),('food','food:anchor',.85),('food','food:correction',.8),('food','food:changing',.9),('casual','style:length',-.8),('work','style:length',.8)]
initial += [(scope,f'{scope}:item-{n:03}',(.05+(n%7)*.04)*(-1 if n%4==0 else 1)) for scope in SCOPES for n in range(30)]
for i,(scope,concept,value) in enumerate(initial):
 m.observe(A,event(f'init-{i}',START,scope,concept,'explicit',value),now=START);counts['initialization_writes']+=1
anchor_event=event('anchor-dedup',START+timedelta(microseconds=1),'food','food:unknown');m.observe(A,anchor_event,now=START+timedelta(microseconds=1));counts['initialization_writes']+=1
for ctx,val in ((B,-.75),(C,-.35)):
 m.observe(ctx,event('isolated-init',START,'food','food:anchor','explicit',val),now=START);counts['initialization_writes']+=1
header={'format':'structured-decade-events-v1','seed':args.seed,'start':iso(START),'end_exclusive':iso(END),'days':DAYS,'turns_per_day':args.turns_per_day,'context':A.as_dict(),'source':'synthetic host-labelled data, not natural-language LLM extraction'}
dataset=gzip.open(OUT/'synthetic_primary_events.jsonl.gz','wt',encoding='utf-8',compresslevel=1);dataset.write(json.dumps({'header':header},ensure_ascii=False)+'\n')
expected_correction=.8
try:
 for day in range(DAYS):
  session=f'session-{day}'
  for slot in range(args.turns_per_day):
   step=day*args.turns_per_day+slot;now=START+timedelta(days=day,seconds=slot*(86400/args.turns_per_day),microseconds=10)
   scope=SCOPES[slot%len(SCOPES)];concept=f'{scope}:item-{rng.randrange(30):03}';kind='mention';value=None;extra={}
   if slot==0:scope='food';concept='food:correction';kind='correct';value=.8 if (day//90)%2==0 else -.8;expected_correction=value
   elif slot==1:scope='food';concept='food:correction';kind='temporary';value=-1;extra={'expires_at':iso(now+timedelta(minutes=10)),'session_id':session}
   elif slot==2:scope='food';concept='food:unknown'
   elif slot==3:scope='food';concept='food:changing';kind='feedback';value=.9 if day<730 else -.9
   elif slot%10==4:kind='feedback';value=.3 if day%2==0 else -.3
   elif slot%10==5:kind='choice'
   elif slot%25==6:kind='explicit';value=.25 if day%3 else -.25
   e=event(f'd{day}-t{slot}',now,scope,concept,kind,value,**extra)
   t=time.perf_counter_ns();r=m.observe(A,e,now=now);dt=(time.perf_counter_ns()-t)/1e6
   if step%100==0:writes.append(dt)
   counts['primary_observe_calls']+=1;counts['primary_status_'+r['status']]+=1;counts['kind_'+kind]+=1
   ensure('primary_persisted',r['status'] in ('applied','consolidated','same_day_not_reinforced'),{'day':day,'slot':slot,'result':r})
   dataset.write(json.dumps(e,ensure_ascii=False,separators=(',',':'))+'\n')
   host=LocalPreferenceHost(m,A);t=time.perf_counter_ns();packet=host.before_reply([scope],session,now);dt=(time.perf_counter_ns()-t)/1e6
   if step%100==0:latencies.append(dt);packet_sizes.append(len(canonical(packet)))
   counts['primary_compile_calls']+=1
   ensure('bounded_packet',len(packet['items'])<=12 and len(canonical(packet))<=6000);ensure('identity',packet['context']==A.as_dict())
   by={(x['scope'],x['concept_id']):x for x in packet['items']};ensure('core_style_present',('core','style:clarity') in by)
   if scope=='food':
    ensure('anchor_default_packet',('food','food:anchor') in by and by[('food','food:anchor')]['stable']==.85,{'day':day,'keys':list(by)})
    if slot in (0,1):ensure('correction_next_read',('food','food:correction') in by and by[('food','food:correction')]['stable']==expected_correction)
    if slot==1:ensure('temporary_effective',by.get(('food','food:correction'),{}).get('effective')==-1)
    if slot==2:ensure('temporary_expired',by.get(('food','food:correction'),{}).get('effective')==expected_correction)
   if scope in ('casual','work'):
    ensure('style_in_packet',by.get((scope,'style:length'),{}).get('stable')==(-.8 if scope=='casual' else .8))
    ensure('style_no_cross_scope',all(x['scope'] in ('core',scope) for x in packet['items']))
  revision=m.revision(A);nonreal=event(f'attack-{day}',now,'food','food:anchor','correct',-1,mode=['joke','roleplay','quoted','hypothetical'][day%4])
  ensure('marked_nonreal_ignored',m.observe(A,nonreal,now=now)['status']=='ignored' and m.revision(A)==revision);counts['extra_nonreal_calls']+=1
  ensure('duplicate_after_prune_ignored',m.observe(A,anchor_event,now=now)['status']=='duplicate' and m.revision(A)==revision);counts['extra_duplicate_calls']+=1
  if day%30==29:
   result=m.prune_evidence(A,iso(now-timedelta(days=30)));counts['prune_calls']+=1;counts['journal_rows_pruned']+=result['journal_rows_removed'];audit_store(now,step)
  if day%30==0:m.close();m=Memory(DB);counts['connection_reopens']+=1
  counts['new_session_ids']+=1
  if (day+1)%365==0 or day+1==DAYS:
   states=audit_store(now,step);m.conn.execute('PRAGMA wal_checkpoint(TRUNCATE)')
   row={'day':day+1,'primary_turns':(day+1)*args.turns_per_day,'time':iso(now),'db_bytes':DB.stat().st_size,'states':m.conn.execute('SELECT COUNT(*) FROM states').fetchone()[0],'receipts':m.conn.execute('SELECT COUNT(*) FROM receipts').fetchone()[0],'journal':m.conn.execute('SELECT COUNT(*) FROM journal').fetchone()[0],'anchor_stable':states[('food','food:anchor')]['stable'],'anchor_freshness':states[('food','food:anchor')]['freshness'],'changing_stable':states[('food','food:changing')]['stable'],'elapsed_seconds':round(time.perf_counter()-began,3),'sampled_compile_p50_ms':pct(latencies[-365:],.5),'sampled_compile_p95_ms':pct(latencies[-365:],.95)}
   yearly.append(row);save_json(OUT/'progress.json',{'checkpoints':yearly,'failures':failures,'counts':dict(counts)});print(json.dumps(row,ensure_ascii=False),flush=True)
 dataset.close();ensure('final_integrity',m.conn.execute('PRAGMA integrity_check').fetchone()[0]=='ok')
 export_started=time.perf_counter();snapshot=m.export_snapshot(A);snap_path=OUT/'decade_snapshot.json';save_json(snap_path,snapshot);snapshot_seconds=time.perf_counter()-export_started
 packet=m.compile(A,['food','casual'],session_id=session,now=now);save_json(OUT/'final_packet.json',packet);m.conn.execute('PRAGMA wal_checkpoint(TRUNCATE)')
 summary={'status':'pass' if not failures else 'fail','test_type':'structured_state_and_host_packet_scale_simulation','period':header,'primary_turns':TOTAL,'counts':dict(counts),'checks':dict(checks),'failures':failures,'checkpoints':yearly,'performance':{'wall_seconds_including_export':time.perf_counter()-began,'write_sample_n':len(writes),'write_p50_ms':pct(writes,.5),'write_p95_ms':pct(writes,.95),'compile_sample_n':len(latencies),'compile_p50_ms':pct(latencies,.5),'compile_p95_ms':pct(latencies,.95),'packet_chars_max_sampled':max(packet_sizes),'process_peak_rss_mib':(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024 if resource is not None else None)},'storage':{'database_bytes_after_checkpoint':DB.stat().st_size,'snapshot_bytes':snap_path.stat().st_size,'snapshot_sha256':hashlib.sha256(snap_path.read_bytes()).hexdigest(),'snapshot_export_wall_seconds':snapshot_seconds,'states':m.conn.execute('SELECT COUNT(*) FROM states').fetchone()[0],'receipts':m.conn.execute('SELECT COUNT(*) FROM receipts').fetchone()[0],'journal_rows':m.conn.execute('SELECT COUNT(*) FROM journal').fetchone()[0],'dataset_gzip_bytes':(OUT/'synthetic_primary_events.jsonl.gz').stat().st_size},'environment':{'python':sys.version,'sqlite':sqlite3.sqlite_version,'platform':platform.platform(),'cpu_count':os.cpu_count(),'synchronous':'NORMAL','journal_mode':'WAL'},'limitations':['No LLM calls, model activation, semantic classification or end-to-end personalized answers tested.','One local single-writer process; no distributed sync or physical power-loss durability test.','Inputs have host-provided ground-truth role/mode/scope.','Ten years is simulated calendar time and stated synthetic volume, not an observed decade.','Journal pruning keeps provenance summary-only; deduplication receipts continue growing.','Latency is local instrumented API latency, not an SLA.']}
 save_json(OUT/'scale_result.json',summary);print('FINISHED',summary['status'],TOTAL,'turns',len(failures),'failures',flush=True)
except BaseException as e:
 dataset.close();save_json(OUT/'interrupted.json',{'error':repr(e),'counts':dict(counts),'failures':failures});raise
finally:m.close()
