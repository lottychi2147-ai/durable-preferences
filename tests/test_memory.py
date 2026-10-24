from __future__ import annotations

import copy
import importlib.util
import json
import math
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from memory_core import (AccessError, ConflictError, Context, Memory, Policy,
                         ValidationError, atlas_html, canonical, fingerprint, iso, timestamp)

BASE = datetime(2026, 1, 1, tzinfo=timezone.utc)
A = Context("test-owner", "user-a")
B = Context("test-owner", "user-b")


def ev(n=1, kind="explicit", value=.8, concept="food:cutlet", scope="food", day=0, **extras):
    t = BASE + timedelta(days=day, microseconds=n)
    e = {"event_id": f"event-{n}-{day}", "evidence_id": f"evidence-{n}-{day}", "kind": kind,
         "scope": scope, "concept_id": concept, "label": "雞排" if concept == "food:cutlet" else concept,
         "role": "user", "mode": "real", "observed_at": iso(t)}
    if kind not in {"mention", "choice"}:
        e["value"] = value
    e.update(extras)
    return e


class MemoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "memory.sqlite3"
        self.m = Memory(self.path)
        self.now = BASE + timedelta(days=100)

    def tearDown(self):
        self.m.close()
        self.temp.cleanup()

    def apply(self, e, ctx=A, **kw):
        return self.m.observe(ctx, e, now=kw.pop("now", self.now), **kw)

    def first(self, ctx=A, **kw):
        return self.m.get(ctx, now=kw.pop("now", self.now), **kw)["items"][0]

    def test_explicit_immediately_persists(self):
        self.assertEqual(self.apply(ev())["status"], "applied")
        self.assertEqual(self.first()["stable"], .8)

    def test_restart_preserves_state(self):
        self.apply(ev()); self.m.close(); self.m = Memory(self.path)
        self.assertEqual(self.first()["stable"], .8)

    def test_ten_year_silence_does_not_erase_stable(self):
        self.apply(ev())
        x = self.first(now=BASE + timedelta(days=3653))
        self.assertEqual(x["stable"], .8); self.assertEqual(x["freshness"], "historical")

    def test_unknown_is_distinct_from_neutral(self):
        self.apply(ev(kind="mention"))
        self.assertIsNone(self.first()["stable"])
        self.apply(ev(2, "explicit", 0))
        self.assertEqual(self.first()["stable"], 0)
        self.assertEqual(len(self.m.compile(A,["food"], now=self.now)["items"]), 1)

    def test_mention_does_not_create_liking(self):
        for i in range(1,101): self.apply(ev(i, "mention"))
        self.assertIsNone(self.first()["stable"])
        self.assertEqual(self.first()["familiarity_count"], 100)

    def test_repeated_choice_does_not_mean_liking(self):
        for i in range(1,101): self.apply(ev(i,"choice"))
        self.assertIsNone(self.first()["stable"])

    def test_assistant_cannot_reinforce(self):
        self.assertEqual(self.apply(ev(role="assistant"))["status"], "ignored")
        self.assertEqual(self.m.revision(A), 0)

    def test_joke_cannot_reinforce(self):
        for i in range(1,101): self.apply(ev(i,mode="joke"))
        self.assertEqual(self.m.get(A)["items"], [])

    def test_roleplay_cannot_reinforce(self):
        self.assertEqual(self.apply(ev(mode="roleplay"))["status"], "ignored")

    def test_hypothetical_cannot_reinforce(self):
        self.assertEqual(self.apply(ev(mode="hypothetical"))["status"], "ignored")

    def test_quoted_cannot_reinforce(self):
        self.assertEqual(self.apply(ev(mode="quoted"))["status"], "ignored")

    def test_tool_text_cannot_reinforce(self):
        self.assertEqual(self.apply(ev(role="tool"))["status"], "ignored")

    def test_event_dedup(self):
        e=ev(); self.apply(e); r=self.m.revision(A)
        self.assertEqual(self.apply(e)["status"], "duplicate"); self.assertEqual(self.m.revision(A),r)

    def test_source_dedup_with_new_event_id(self):
        e=ev(); self.apply(e)
        e.update(event_id="new-event", observed_at=iso(BASE+timedelta(days=1)))
        self.assertEqual(self.apply(e)["status"], "duplicate")

    def test_same_day_does_not_forge_four_independent_groups(self):
        for i in range(1,101): self.apply(ev(i,"feedback",1))
        s=self.first(now=BASE+timedelta(days=1))
        self.assertIsNone(s["stable"]); self.assertEqual(len(s["candidate"]["days"]),1)

    def test_four_days_consolidate_unknown(self):
        for d in range(4): self.apply(ev(d+1,"feedback",1,day=d))
        self.assertEqual(self.first()["stable"],1)
        self.assertEqual(self.first()["basis"],"consolidated")

    def test_single_bad_meal_does_not_erase_preference(self):
        self.apply(ev()); self.apply(ev(2,"feedback",-1,day=1))
        self.assertEqual(self.first()["stable"],.8)

    def test_repeated_bad_meals_can_change_preference(self):
        self.apply(ev())
        for d in range(1,13): self.apply(ev(d+1,"feedback",-1,day=d))
        self.assertAlmostEqual(self.first()["stable"], 1.8*.6**3-1)
        self.assertLess(self.first()["stable"],0)

    def test_feedback_day_not_reused_after_consolidation(self):
        for d in range(4): self.apply(ev(d+1,"feedback",1,day=d))
        self.apply(ev(99,"feedback",1,day=3))
        self.assertIsNone(self.first(now=BASE+timedelta(days=4))["candidate"])

    def test_sparse_feedback_accumulates_across_years(self):
        for d in (0,100,200,300): self.apply(ev(d+1,"feedback",1,day=d),now=BASE+timedelta(days=400))
        self.assertGreater(self.first(now=BASE+timedelta(days=400))["stable"], .5)

    def test_candidate_expires_but_stable_does_not(self):
        self.apply(ev()); self.apply(ev(2,"feedback",-1,day=1))
        s=self.first(now=BASE+timedelta(days=100))
        self.assertIsNone(s["candidate"]); self.assertEqual(s["stable"],.8)

    def test_mixed_feedback_does_not_claim_consensus(self):
        for d in range(10): self.apply(ev(d+1,"feedback",(-1)**d,day=d))
        self.assertIsNone(self.first()["stable"])

    def test_explicit_correction_immediate(self):
        self.apply(ev()); self.apply(ev(2,"correct",-.9,day=1))
        self.assertEqual(self.first()["stable"],-.9)
        self.assertEqual(self.first()["basis"],"corrected")

    def test_correction_clears_candidate(self):
        self.apply(ev(1,"feedback",1)); self.apply(ev(2,"correct",-1,day=1))
        self.assertIsNone(self.first(now=BASE+timedelta(days=2))["candidate"])

    def test_old_signal_cannot_override_correction(self):
        self.apply(ev(1,"correct",-1,day=20))
        self.assertEqual(self.apply(ev(2,"explicit",1,day=10))["reason"],"stale_or_equal_timestamp")
        self.assertEqual(self.first()["stable"],-1)

    def test_equal_timestamp_rejected(self):
        self.apply(ev())
        self.assertEqual(self.apply(ev(2,observed_at=ev()["observed_at"]))["reason"],"stale_or_equal_timestamp")

    def test_future_signal_rejected(self):
        with self.assertRaises(ValidationError): self.apply(ev(day=101))

    def test_temporary_does_not_modify_stable(self):
        self.apply(ev())
        self.apply(ev(2,"temporary",-1,day=1,expires_at=iso(BASE+timedelta(days=2))),now=BASE+timedelta(days=1,hours=1))
        x=self.first(now=BASE+timedelta(days=1,hours=2))
        self.assertEqual(x["stable"],.8); self.assertEqual(x["effective"],-1)

    def test_temporary_expires_without_new_revision(self):
        self.apply(ev())
        self.apply(ev(2,"temporary",-1,day=1,expires_at=iso(BASE+timedelta(days=2))),now=BASE+timedelta(days=1,hours=1))
        rev=self.m.revision(A)
        self.assertEqual(self.first(now=BASE+timedelta(days=2))["effective"],.8)
        self.assertEqual(self.m.revision(A),rev)

    def test_session_overlay_does_not_leak(self):
        self.apply(ev())
        self.apply(ev(2,"temporary",-1,day=1,expires_at=iso(BASE+timedelta(days=2)),session_id="chat-a"),now=BASE+timedelta(days=1,hours=1))
        n=BASE+timedelta(days=1,hours=2)
        self.assertEqual(self.first(session_id="chat-a",now=n)["effective"],-1)
        self.assertEqual(self.first(session_id="chat-b",now=n)["effective"],.8)

    def test_overlay_for_unknown_still_guides_current_request(self):
        self.apply(ev(1,"temporary",-1,expires_at=iso(BASE+timedelta(hours=1))),now=BASE+timedelta(minutes=1))
        x=self.first(now=BASE+timedelta(minutes=2))
        self.assertIsNone(x["stable"]); self.assertEqual(x["effective"],-1)

    def test_bad_overlay_lifetime_rejected(self):
        with self.assertRaises(ValidationError):
            self.apply(ev(1,"temporary",-1,expires_at=iso(BASE+timedelta(days=10))),now=BASE+timedelta(minutes=1))

    def test_owner_isolation(self):
        self.apply(ev()); other=Context("different-owner","user-a")
        self.assertEqual(self.m.get(other)["items"],[])

    def test_subject_isolation(self):
        self.apply(ev()); self.apply(ev(value=-.8),ctx=B)
        self.assertEqual(self.first(A)["stable"],.8); self.assertEqual(self.first(B)["stable"],-.8)

    def test_namespace_isolation(self):
        self.apply(ev()); other=Context(A.owner_id,A.subject_id,"project-private")
        self.assertEqual(self.m.get(other)["items"],[])

    def test_scope_isolation(self):
        self.apply(ev(scope="casual",concept="style:details",value=-1))
        self.apply(ev(scope="work",concept="style:details",value=1))
        self.assertEqual(self.m.compile(A,["work"],now=self.now)["items"][0]["effective"],1)
        self.assertEqual(self.m.compile(A,["casual"],now=self.now)["items"][0]["effective"],-1)

    def test_core_style_is_always_loaded(self):
        self.apply(ev(scope="core",concept="style:respectful",value=1))
        self.apply(ev(2))
        packet=self.m.compile(A,["food"],now=self.now)
        self.assertEqual({s["scope"] for s in packet["items"]},{"core","food"})

    def test_store_specific_complaint_does_not_generalize(self):
        self.apply(ev()); self.apply(ev(2,"explicit",-1,concept="store:shop-a-cutlet"))
        self.assertEqual(self.m._load(A,"food","food:cutlet")["stable"],.8)

    def test_compile_never_reads_history(self):
        self.apply(ev()); sql=[]; self.m.conn.set_trace_callback(sql.append)
        self.m.compile(A,["food"],now=self.now)
        self.m.conn.set_trace_callback(None)
        self.assertFalse(any("journal" in q.lower() or "receipts" in q.lower() for q in sql))

    def test_compile_budget_and_omission(self):
        for i in range(30): self.apply(ev(i+1,concept=f"food:{i}"))
        p=self.m.compile(A,["food"],now=self.now,max_items=4,max_chars=1800)
        self.assertLessEqual(len(p["items"]),4); self.assertLessEqual(len(canonical(p)),1800)
        self.assertEqual(p["omitted_count"]+len(p["items"]),30)

    def test_compile_budget_with_expiry(self):
        for i in range(4):
            self.apply(ev(i+1,"temporary",1,concept=f"food:{i}",expires_at=iso(BASE+timedelta(hours=1))),now=BASE+timedelta(minutes=1))
        for budget in range(800,2000,11):
            p=self.m.compile(A,["food"],now=BASE+timedelta(minutes=2),max_chars=budget)
            self.assertLessEqual(len(canonical(p)),budget)

    def test_read_does_not_reinforce(self):
        self.apply(ev()); snapshot=self.m.export_snapshot(A)
        for _ in range(100): self.m.compile(A,["food"],now=self.now)
        self.assertEqual(self.m.export_snapshot(A),snapshot)

    def test_stale_cas_rejected(self):
        self.apply(ev()); self.apply(ev(2,"correct",-1),expected_revision=1)
        with self.assertRaises(ConflictError): self.apply(ev(3,"correct",1),expected_revision=1)

    def test_forget_removes_state_and_journal(self):
        self.apply(ev()); self.m.forget(A,"food","food:cutlet",now=self.now)
        self.assertEqual(self.m.get(A)["items"],[])
        self.assertEqual(self.m.explain(A,"food","food:cutlet")["recent_structured_signals"],[])

    def test_old_snapshot_cannot_resurrect_forgotten_preference(self):
        self.apply(ev()); snap=self.m.export_snapshot(A)
        self.m.forget(A,"food","food:cutlet",now=self.now)
        with self.assertRaises(ConflictError): self.m.restore_empty(A,snap)

    def test_replay_old_event_with_new_id_blocked_after_forget(self):
        self.apply(ev()); self.m.forget(A,"food","food:cutlet",now=self.now)
        self.assertEqual(self.apply(ev(2,day=1))["reason"],"before_deletion_watermark")

    def test_passive_observation_cannot_relearn_forgotten_preference(self):
        self.apply(ev()); self.m.forget(A,"food","food:cutlet",now=self.now)
        r=self.apply(ev(2,"feedback",1,day=101),now=BASE+timedelta(days=102))
        self.assertEqual(r["reason"],"forgotten_requires_explicit_relearn")

    def test_explicit_authorized_relearn(self):
        self.apply(ev()); self.m.forget(A,"food","food:cutlet",now=self.now)
        r=self.apply(ev(2,"explicit",-.6,day=101,allow_relearn=True),now=BASE+timedelta(days=102))
        self.assertEqual(r["status"],"applied"); self.assertEqual(self.first()["stable"],-.6)

    def test_forget_is_not_raw_evidence_pruning(self):
        self.apply(ev()); self.m.prune_evidence(A,iso(self.now))
        self.assertEqual(self.first()["stable"],.8)
        self.assertEqual(self.first()["source_coverage"],"aggregate_only")

    def test_dedup_survives_evidence_pruning(self):
        e=ev(); self.apply(e); self.m.prune_evidence(A,iso(self.now))
        self.assertEqual(self.apply(e)["status"],"duplicate")

    def test_snapshot_migration_preserves_preference(self):
        self.apply(ev()); snap=self.m.export_snapshot(A)
        with Memory(Path(self.temp.name)/"new.sqlite3") as other:
            other.restore_empty(A,snap)
            self.assertEqual(other.get(A)["items"][0]["stable"],.8)
            self.assertEqual(other.observe(A,ev(),now=self.now)["status"],"duplicate")

    def test_snapshot_identity_mismatch_rejected(self):
        self.apply(ev())
        with Memory(Path(self.temp.name)/"new.sqlite3") as other:
            with self.assertRaises(AccessError): other.restore_empty(B,self.m.export_snapshot(A))

    def test_snapshot_corruption_rejected(self):
        self.apply(ev()); snap=self.m.export_snapshot(A); snap["data"]["states"][0]["stable"]=-1
        with self.assertRaises(ValidationError): self.m.restore_empty(A,snap)

    def test_snapshot_nan_rejected(self):
        self.apply(ev()); snap=self.m.export_snapshot(A); snap["data"]["states"][0]["stable"]=math.nan
        with self.assertRaises(ValueError): fingerprint(snap["data"])

    def test_bad_snapshot_state_rolls_back(self):
        self.apply(ev()); snap=self.m.export_snapshot(A)
        snap["data"]["states"][0]["stable"]=4; snap["sha256"]=fingerprint(snap["data"])
        with Memory(Path(self.temp.name)/"new.sqlite3") as other:
            with self.assertRaises(ValidationError): other.restore_empty(A,snap)
            self.assertEqual(other.revision(A),0)

    def test_policy_persisted_and_mismatch_rejected(self):
        path=Path(self.temp.name)/"policy.sqlite3"
        with Memory(path,Policy(min_groups=7)): pass
        with Memory(path) as other: self.assertEqual(other.policy.min_groups,7)
        with self.assertRaises(ConflictError): Memory(path,Policy(min_groups=4))

    def test_validation_score_limits(self):
        for x in [2,-2,True,float("inf"),float("nan"),"0.8",None]:
            with self.subTest(value=x):
                with self.assertRaises(ValidationError): self.apply(ev(value=x))
        self.assertEqual(self.m.revision(A),0)

    def test_naive_time_rejected(self):
        with self.assertRaises(ValidationError): self.apply(ev(observed_at="2026-01-01T00:00:00"))

    def test_unexpected_identity_in_payload_rejected(self):
        with self.assertRaises(ValidationError): self.apply(ev(owner_id="other-owner"))

    def test_sql_injection_in_identity_rejected(self):
        with self.assertRaises(ValidationError): Context("x'; DROP TABLE states;--","a")

    def test_atlas_escapes_user_label(self):
        self.apply(ev(label='<img src=x onerror="alert(1)">'))
        page=atlas_html(self.m.get(A,now=self.now))
        self.assertNotIn('<img src=x',page)
        self.assertIn('&lt;img',page)

    def test_candidate_direction_reset(self):
        self.apply(ev(1,"feedback",1)); self.apply(ev(2,"feedback",-1,day=1))
        c=self.first(now=BASE+timedelta(days=2))["candidate"]
        self.assertEqual(c["direction"],-1); self.assertEqual(len(c["days"]),1)

    def test_concurrent_writes_preserve_revisions(self):
        def work(worker):
            with Memory(self.path) as store:
                for i in range(20):
                    e=ev(worker*100+i+1,concept=f"food:w{worker}-{i}")
                    store.observe(A,e,now=self.now)
        with ThreadPoolExecutor(max_workers=4) as pool: list(pool.map(work,range(4)))
        self.assertEqual(self.m.revision(A),80)
        self.assertEqual(len(self.m.get(A)["items"]),80)

    def test_concurrent_cas_only_one_winner(self):
        self.apply(ev()); gate=threading.Barrier(2)
        def work(n):
            with Memory(self.path) as store:
                gate.wait()
                try:
                    store.observe(A,ev(n+2,"correct",-1),now=self.now,expected_revision=1)
                    return "ok"
                except ConflictError: return "conflict"
        with ThreadPoolExecutor(max_workers=2) as pool: outcomes=list(pool.map(work,range(2)))
        self.assertCountEqual(outcomes,["ok","conflict"])

    def test_cli_roundtrip_and_process_restart(self):
        base=[sys.executable,str(ROOT/"scripts/memory.py"),"--db",str(self.path),"--owner",A.owner_id,
              "--subject",A.subject_id,"--now",iso(self.now)]
        first=subprocess.run(base+["observe"],input=json.dumps(ev()),text=True,capture_output=True)
        self.assertEqual(first.returncode,0,first.stderr)
        second=subprocess.run(base+["compile","--scopes","food"],text=True,capture_output=True)
        self.assertEqual(second.returncode,0,second.stderr)
        self.assertEqual(json.loads(second.stdout)["items"][0]["effective"],.8)

    def test_cli_invalid_json_fails_without_write(self):
        base=[sys.executable,str(ROOT/"scripts/memory.py"),"--db",str(self.path),"--owner",A.owner_id,
              "--subject",A.subject_id,"observe"]
        p=subprocess.run(base,input="{nope}",text=True,capture_output=True)
        self.assertEqual(p.returncode,2)
        self.assertEqual(self.m.revision(A),0)

    def test_negative_control_unmounted_host_has_no_memory(self):
        self.apply(ev())
        unmounted_context=[]
        mounted_context=self.m.compile(A,["food"],now=self.now)["items"]
        self.assertEqual(unmounted_context,[])
        self.assertEqual(len(mounted_context),1)
        # This tests context delivery only, not whether a language model follows it.


if __name__ == "__main__":
    unittest.main(verbosity=2)
