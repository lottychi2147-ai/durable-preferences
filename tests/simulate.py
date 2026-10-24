"""Reproducible structured-input simulation. NOT live LLM evaluation."""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
import json
import math
import random
import statistics
import sys
import tempfile
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from memory_core import Context, Memory, canonical, iso
from host_adapter import LocalPreferenceHost
START=datetime(2026,1,1,tzinfo=timezone.utc)


def percentile(values,p):
    ordered=sorted(values)
    return ordered[max(0,math.ceil(len(ordered)*p)-1)] if ordered else None


def event(seq,time_at,*,kind="explicit",value=.8,scope="food",concept="food:chicken",
          role="user",mode="real",session=None,allow_relearn=False):
    e={"event_id":f"e-{seq}","evidence_id":f"source-{seq}","kind":kind,"scope":scope,
       "concept_id":concept,"label":concept,"observed_at":iso(time_at),"role":role,"mode":mode}
    if kind not in {"mention","choice"}: e["value"]=value
    if kind=="temporary": e.update(expires_at=iso(time_at+timedelta(minutes=30)),session_id=session)
    if allow_relearn: e["allow_relearn"]=True
    return e


def run_seed(seed,steps):
    rng=random.Random(seed)
    counters=Counter();latencies=[];trace=[]
    began=time.perf_counter()
    with tempfile.TemporaryDirectory() as tmp:
        path=Path(tmp)/"memory.sqlite3";m=Memory(path)
        subjects=[Context("synthetic-owner",f"user-{n}") for n in ("a","b")]
        expected={subjects[0]:.85,subjects[1]:-.75}
        tombstoned={c:False for c in subjects};anchor_events={}
        for n,c in enumerate(subjects):
            initial=[event(f"init-{n}-food",START,value=expected[c]),
                     event(f"init-{n}-anchor",START,value=.6,concept="food:anchor-noodles"),
                     event(f"init-{n}-core",START,value=.8,scope="core",concept="style:clear"),
                     event(f"init-{n}-casual",START,value=-.9,scope="casual",concept="style:length"),
                     event(f"init-{n}-work",START,value=.9,scope="work",concept="style:length")]
            for e in initial: m.observe(c,e,now=START)
            anchor_events[c]=initial[1]
        session="chat-0"
        for step in range(1,steps+1):
            now=START+timedelta(seconds=(3653*86400)*step/steps)
            c=rng.choice(subjects);x=rng.random();action="unrelated";prior=m.revision(c)
            if x<.57:
                counters["unrelated_turns"]+=1
            elif x<.69:
                action="contamination"
                role,mode=rng.choice([("assistant","real"),("user","joke"),("user","roleplay"),("user","quoted"),("user","hypothetical")])
                result=m.observe(c,event(f"attack-{step}",now,kind="correct",value=1,role=role,mode=mode),now=now)
                assert result["status"]=="ignored" and m.revision(c)==prior
                counters["filtered_signals"]+=1
            elif x<.77:
                action="duplicate";result=m.observe(c,anchor_events[c],now=now)
                assert result["status"]=="duplicate" and m.revision(c)==prior
                counters["duplicates_blocked"]+=1
            elif x<.83:
                action="temporary"
                result=m.observe(c,event(step,now,kind="temporary",value=-1,session=session),now=now)
                if tombstoned[c]: assert result["status"]=="ignored"
                counters["temporary_attempts"]+=1
            elif x<.88:
                action="correction";value=rng.choice([-.95,-.5,0,.5,.95])
                result=m.observe(c,event(step,now,kind="correct",value=value,allow_relearn=tombstoned[c]),now=now)
                assert result["status"]=="applied"
                expected[c]=value;tombstoned[c]=False;counters["explicit_corrections"]+=1
            elif x<.93:
                action="mention";m.observe(c,event(step,now,kind="mention"),now=now);counters["mentions"]+=1
            elif x<.98:
                action="feedback"
                m.observe(c,event(step,now,kind="feedback",value=rng.choice([-1,1]),concept="food:changing-snack"),now=now)
                counters["feedback_signals"]+=1
            else:
                action="forget";m.forget(c,"food","food:chicken",now=now)
                expected[c]=None;tombstoned[c]=True;counters["forget_operations"]+=1
            if step%500==0:
                m.close();m=Memory(path);counters["database_reopens"]+=1
            if step%250==0:
                session=f"chat-{step//250}";counters["context_resets"]+=1
            if step%1000==0:
                m.prune_evidence(c,iso(now-timedelta(days=30)));counters["evidence_prunes"]+=1
            host=LocalPreferenceHost(m,c);mode="work" if step%2==0 else "casual"
            sql=[]
            if step%1000==0:m.conn.set_trace_callback(sql.append)
            t=time.perf_counter_ns();packet=host.before_reply(["food",mode],session,now)
            latencies.append((time.perf_counter_ns()-t)/1e6)
            if step%1000==0:
                m.conn.set_trace_callback(None)
                assert not any("journal" in q.lower() or "receipts" in q.lower() for q in sql)
                counters["read_path_history_checks"]+=1
            items={(i["scope"],i["concept_id"]):i for i in packet["items"]}
            chicken=items.get(("food","food:chicken"))
            if expected[c] is None:assert chicken is None
            else:assert chicken is not None and chicken["stable"]==expected[c]
            assert items[("food","food:anchor-noodles")]["stable"]==.6
            assert items[("core","style:clear")]["stable"]==.8
            assert items[(mode,"style:length")]["effective"]==(.9 if mode=="work" else -.9)
            assert ("casual" if mode=="work" else "work","style:length") not in items
            assert packet["context"]==c.as_dict()
            assert len(packet["items"])<=12 and len(canonical(packet))<=6000
            assert all(i["effective"] is None or -1<=i["effective"]<=1 for i in packet["items"])
            counters["state_and_packet_checks"]+=1
            if step in (1,steps//2,steps):
                trace.append({"step":step,"simulated_time":iso(now),"action":action,"revision":packet["revision"],
                              "subject":c.subject_id,"anchor":items[("food","food:anchor-noodles")],"packet_items":len(items)})
        endstate=m.export_snapshot(subjects[0])
        with Memory(Path(tmp)/"migrated.sqlite3") as dest:
            dest.restore_empty(subjects[0],endstate)
            a=m.compile(subjects[0],["food","casual"],now=now,session_id=session)
            b=dest.compile(subjects[0],["food","casual"],now=now,session_id=session)
            assert a==b;counters["cross_store_migrations"]+=1
        m.conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        db_size=path.stat().st_size;m.close()
    return {"seed":seed,"steps":steps,"simulated_days":3653,"status":"pass","counts":dict(counters),
            "wall_seconds":round(time.perf_counter()-began,4),"compile_p50_ms":round(statistics.median(latencies),4),
            "compile_p95_ms":round(percentile(latencies,.95),4),"db_bytes":db_size,"traces":trace}


def run(seeds=12,steps=10000):
    results=[]
    for seed in range(seeds):
        result=run_seed(seed,steps);results.append(result)
        print(f"seed {seed}: {steps} turns PASS, {result['wall_seconds']:.2f}s",flush=True)
    counts=Counter()
    for r in results:counts.update(r["counts"])
    return {"test_type":"deterministic_structured_signal_simulation","seeds":seeds,"turns_per_seed":steps,
            "total_turns":seeds*steps,"simulated_days_per_seed":3653,"all_pass":all(r["status"]=="pass" for r in results),
            "counts":dict(counts),"results":results,
            "limitations":["No external LLM calls; source/mode labels are synthetic ground truth.",
                           "Ten years is a simulated clock, not a ten-year study.",
                           "Host adapters are local test harnesses, not real ChatGPT/Claude/DeepSeek installations.",
                           "Measured latency applies to this environment and small active preference sets only."]}

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--seeds",type=int,default=12);p.add_argument("--steps",type=int,default=10000)
    p.add_argument("--output",default=str(ROOT/"reports/simulation.json"));a=p.parse_args()
    if not 1<=a.seeds<=100 or not 1<=a.steps<=100000:p.error("seeds 1-100; steps 1-100000")
    result=run(a.seeds,a.steps);out=Path(a.output);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
