"""Acceptance regressions for durable sparse learning, not NLP tests."""
from __future__ import annotations
import copy, hashlib, json, random, sqlite3, subprocess, sys, tempfile, unittest
from pathlib import Path
from datetime import timedelta
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from memory_core import Context,Memory,Policy,ValidationError,fingerprint,iso
from test_memory import BASE,ev,A

class SparseLearningTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'m.sqlite3';self.m=Memory(self.path)
    def tearDown(self):self.m.close();self.tmp.cleanup()
    def put(self,n,day,kind='feedback',value=1,**kw):
        return self.m.observe(A,ev(n,kind,value,day=day,**kw),now=BASE+timedelta(days=day,hours=1))
    def state(self,day=20000):return self.m.get(A,now=BASE+timedelta(days=day))['items'][0]
    def test_quarterly_forty_one_positive(self):
        for n in range(41):self.put(n,n*90)
        s=self.state();self.assertGreater(s['stable'],.5);self.assertEqual(s['familiarity_count'],41);self.assertEqual(s['long_evidence']['groups'],41)
    def test_quarterly_forty_one_negative_unknown(self):
        for n in range(41):self.put(n,n*90,value=-1)
        self.assertLess(self.state()['stable'],-.5)
    def test_quarterly_negative_reverses_positive(self):
        self.put(1,0,'explicit',.9)
        for n in range(1,42):self.put(n+1,n*90,value=-1)
        self.assertLess(self.state()['stable'],-.5)
    def test_quarterly_positive_reverses_negative(self):
        self.put(1,0,'explicit',-.9)
        for n in range(1,42):self.put(n+1,n*90)
        self.assertGreater(self.state()['stable'],.5)
    def test_semiannual_feedback(self):
        for n in range(21):self.put(n,n*180)
        self.assertGreater(self.state()['stable'],.5)
    def test_annual_feedback(self):
        for n in range(11):self.put(n,n*365)
        self.assertGreater(self.state()['stable'],.5)
    def test_irregular_gaps(self):
        day=0;rng=random.Random(913)
        for n in range(17):day+=rng.randint(65,300);self.put(n,day,value=.8)
        self.assertGreater(self.state()['stable'],.5)
    def test_slow_pending_survives_silence(self):
        for n,day in enumerate([0,365,730]):self.put(n,day)
        self.assertEqual(len(self.state()['long_evidence']['pending']),3)
        self.put(5,3650);self.assertGreater(self.state()['stable'],.5)
    def test_short_expiry_does_not_clear_slow(self):
        self.put(1,0)
        s=self.state(100);self.assertIsNone(s['candidate']);self.assertEqual(len(s['long_evidence']['pending']),1)
    def test_slow_survives_pruning_and_restart(self):
        for n in range(3):self.put(n,n*365)
        self.m.prune_evidence(A,iso(BASE+timedelta(days=1000)));self.m.close();self.m=Memory(self.path)
        self.put(5,1095);self.assertGreater(self.state()['stable'],.5)
    def test_single_bad_episode_does_not_flip_long_history(self):
        for n in range(40):self.put(n,n*90)
        v=self.state()['stable'];self.put(99,3650,value=-1);self.assertEqual(v,self.state()['stable'])
    def test_lifetime_positive_count_does_not_block_reversal(self):
        for n in range(1000):self.put(n,n)
        for n in range(1,13):self.put(1000+n,1000+n*90,value=-1)
        self.assertLess(self.state()['stable'],-.5)
    def test_no_confidence_freeze(self):
        for n in range(100):self.put(n,n)
        for n in range(100,1100):self.put(n,n,value=-1)
        self.assertLess(self.state()['stable'],-.95)
    def test_mixed_sparse_does_not_claim_like(self):
        for n in range(40):self.put(n,n*90,value=(-1)**n)
        self.assertIsNone(self.state()['stable'])
    def test_mixed_known_preference_surfaces_uncertainty(self):
        self.put(999,0,'explicit',.9)
        for n in range(1,9):self.put(n,n*90,value=(-1)**n)
        packet=self.m.compile(A,['food'],now=BASE+timedelta(days=1000))
        self.assertIn('uncertainty',packet['items'][0])
    def test_slow_window_is_bounded(self):
        for n in range(100):self.put(n,n*90,value=(-1)**n)
        s=self.state();self.assertEqual(s['long_evidence']['groups'],100);self.assertLessEqual(len(s['long_evidence']['pending']),16)
    def test_nonreal_and_neutral_contact_not_positive_votes(self):
        for n in range(1,10):self.put(n,n*90,mode='joke')
        for n in range(10,20):self.put(n,n*90,'mention')
        s=self.state();self.assertIsNone(s['stable']);self.assertEqual(s['long_evidence']['groups'],0)
    def test_positive_and_negative_mass_separate(self):
        for n,val in enumerate([1,-.8,1,-.8]):self.put(n,n*90,value=val)
        e=self.state()['long_evidence'];self.assertEqual(e['positive_mass'],2);self.assertEqual(e['negative_mass'],1.6)
    def test_fast_and_slow_do_not_double_apply(self):
        self.put(999,0,'explicit',.9)
        for n in range(1,5):self.put(n,n,value=-1)
        self.assertAlmostEqual(self.state()['stable'],.14);self.assertEqual(self.state()['long_evidence']['pending'],[])
    def test_mixed_to_consistent_adapts(self):
        for n in range(20):self.put(n,n*90,value=(-1)**n)
        for n in range(20,40):self.put(n,n*90)
        self.assertGreater(self.state()['stable'],.5)
    def test_explicit_correction_resets_slow_batch(self):
        for n in range(3):self.put(n,n*90)
        self.put(9,300,'correct',-.8)
        self.assertEqual(self.state()['long_evidence']['pending'],[])
        self.put(10,400);self.assertEqual(self.state()['stable'],-.8)
    def test_forget_deletes_slow_evidence(self):
        self.put(1,0);self.m.forget(A,'food','food:cutlet',now=BASE+timedelta(days=1))
        self.assertEqual(self.m.get(A)['items'],[])
        r=self.put(2,90);self.assertEqual(r['reason'],'forgotten_requires_explicit_relearn')
    def test_slow_export_restore(self):
        for n in range(3):self.put(n,n*365)
        with Memory(Path(self.tmp.name)/'copy.db') as dst:
            dst.restore_empty(A,self.m.export_snapshot(A))
            dst.observe(A,ev(5,'feedback',1,day=1095),now=BASE+timedelta(days=1096))
            self.assertGreater(dst.get(A)['items'][0]['stable'],.5)
    def test_new_snapshot_invalid_slow_mass_rejected(self):
        self.put(1,0);snap=self.m.export_snapshot(A);snap['data']['states'][0]['long_evidence']['positive_mass']=-1;snap['sha256']=fingerprint(snap['data'])
        with Memory(Path(self.tmp.name)/'copy.db') as dst:
            with self.assertRaises(ValidationError):dst.restore_empty(A,snap)
    def test_noisy_but_consistent_sparse_forms_preference(self):
        values=([1,1,-1,1,1,1,1,1,1,1])*4
        for n,v in enumerate(values):self.put(n,n*90,value=v)
        self.assertGreater(self.state()['stable'],.5)
    def test_neutral_explicit_remains_distinct_unknown(self):
        self.put(1,0,'correct',0);self.assertEqual(self.state()['stable'],0)
    def test_receipts_are_full_sha256_blobs(self):
        self.put(1,0);self.assertEqual(self.m.conn.execute('SELECT MIN(length(digest)),MAX(length(digest)) FROM receipts').fetchone()[:],(32,32))
        sql=self.m.conn.execute("SELECT sql FROM sqlite_master WHERE name='receipts'").fetchone()[0]
        self.assertIn('WITHOUT ROWID',sql)
    def test_exact_duplicate_after_prune_new_timestamp(self):
        e=ev(1,'feedback',1);self.m.observe(A,e,now=BASE+timedelta(days=1))
        self.m.prune_evidence(A,iso(BASE+timedelta(days=100)))
        e['observed_at']=iso(BASE+timedelta(days=500));e['event_id']='new-id'
        r=self.m.observe(A,e,now=BASE+timedelta(days=501));self.assertEqual(r['status'],'duplicate')
    def test_dense_scope_decodes_bounded_pool(self):
        for n in range(5000):self.put(n,0,'explicit',.2,concept=f'food:concept-{n}')
        p=self.m.compile(A,['food'],now=BASE+timedelta(days=1))
        self.assertLessEqual(self.m.last_compile_stats['decoded_states'],24)
        self.assertEqual(len(p['items'])+p['omitted_count'],5000)
    def test_unknown_overlay_count_and_expiry(self):
        self.put(1,0,'mention')
        self.put(2,1,'temporary',-1,expires_at=iso(BASE+timedelta(days=2)))
        p=self.m.compile(A,['food'],now=BASE+timedelta(days=1,hours=2))
        self.assertEqual((p['unknown_count'],len(p['items'])),(0,1))
        p=self.m.compile(A,['food'],now=BASE+timedelta(days=3))
        self.assertEqual((p['unknown_count'],len(p['items'])),(1,0))
    def test_session_overlay_unknown_does_not_leak_to_counts(self):
        self.put(1,0,'temporary',-1,expires_at=iso(BASE+timedelta(days=1)),session_id='a')
        p=self.m.compile(A,['food'],now=BASE+timedelta(hours=2),session_id='b')
        self.assertEqual((p['unknown_count'],p['omitted_count'],len(p['items'])),(1,0,0))
    def test_forget_updates_index_and_stats(self):
        self.put(1,0,'explicit',.9);self.m.forget(A,'food','food:cutlet')
        self.assertEqual(self.m.conn.execute('SELECT COUNT(*) FROM state_index').fetchone()[0],0)
        self.assertEqual(self.m.compile(A,['food'])['omitted_count'],0)
    def test_policy_invalid_window_and_agreement(self):
        for kwargs in ({'long_window_groups':2},{'agreement':.5},{'agreement':True},{'long_window_groups':False}):
            with self.assertRaises(ValidationError):Policy(**kwargs)
    def test_strength_less_than_one_not_forced_to_one(self):
        for n in range(8):self.put(n,n*90,value=.3)
        self.assertAlmostEqual(self.state()['stable'],.3)

if __name__=='__main__':unittest.main()
