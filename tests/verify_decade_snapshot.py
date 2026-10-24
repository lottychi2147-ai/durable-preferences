#!/usr/bin/env python3
"""Verify a full decade snapshot through a NEW Python CLI process."""
import argparse,json,hashlib,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from memory_core import Memory,Context,timestamp,canonical
p=argparse.ArgumentParser();p.add_argument('--run-dir',type=Path,required=True);a=p.parse_args();d=a.run_dir
snapshot=d/'decade_snapshot.json';dst=d/'restored-v020.sqlite3'
if dst.exists():raise SystemExit('refusing to overwrite restore target')
ctx=Context('synthetic-owner','subject-a');packet=json.loads((d/'final_packet.json').read_text());now=timestamp(packet['read_at']);session='session-3652'
cmd=[sys.executable,str(ROOT/'scripts/memory.py'),'--db',str(dst),'--owner',ctx.owner_id,'--subject',ctx.subject_id,'restore-empty','--input',str(snapshot)]
t=time.perf_counter();proc=subprocess.run(cmd,capture_output=True,text=True);elapsed=time.perf_counter()-t
report={'command':cmd,'returncode':proc.returncode,'stdout':proc.stdout,'stderr':proc.stderr,'restore_seconds':elapsed,'snapshot_bytes':snapshot.stat().st_size}
if proc.returncode:raise SystemExit(proc.stderr)
with Memory(d/'decade.sqlite3') as src, Memory(dst) as copy:
    x=src.get(ctx,now=now)['items'];y=copy.get(ctx,now=now)['items']
    def normalized(items):return [{k:v for k,v in s.items() if k!='source_coverage'} for s in items]
    same=normalized(x)==normalized(y)
    a1=src.compile(ctx,['food','casual'],now=now,session_id=session);a2=copy.compile(ctx,['food','casual'],now=now,session_id=session)
    receipts1=src.conn.execute('SELECT COUNT(*) FROM receipts WHERE context_id=?',(src._receipt_context(ctx),)).fetchone()[0]
    receipts2=copy.conn.execute('SELECT COUNT(*) FROM receipts WHERE context_id=?',(copy._receipt_context(ctx),)).fetchone()[0]
    report.update(states=len(x),all_state_fields_equal_except_coverage=same,compiled_packet_equal=a1==a2,source_receipts=receipts1,restored_receipts=receipts2,integrity=copy.conn.execute('PRAGMA integrity_check').fetchone()[0])
    assert same and a1==a2 and receipts1==receipts2 and report['integrity']=='ok'
report['status']='pass';(d/'snapshot-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps(report,ensure_ascii=False))
