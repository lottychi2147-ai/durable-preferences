"""Migration fixture uses schema 1 data; old algorithm is not needed to migrate."""
from __future__ import annotations
import hashlib,json,sqlite3,sys,tempfile,unittest
from pathlib import Path
from datetime import timedelta
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from memory_core import Context,Memory,ValidationError,fingerprint,iso,canonical
from migrate_v011 import migrate
from test_memory import BASE,A,ev

def legacy_fixture(path):
    c=sqlite3.connect(path)
    c.executescript('''
CREATE TABLE meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE subjects(owner TEXT,subject TEXT,namespace TEXT,revision INTEGER,PRIMARY KEY(owner,subject,namespace));
CREATE TABLE states(owner TEXT,subject TEXT,namespace TEXT,scope TEXT,concept TEXT,data TEXT,PRIMARY KEY(owner,subject,namespace,scope,concept));
CREATE TABLE receipts(owner TEXT,subject TEXT,namespace TEXT,digest TEXT,PRIMARY KEY(owner,subject,namespace,digest));
CREATE TABLE tombstones(owner TEXT,subject TEXT,namespace TEXT,key_hash TEXT,cutoff TEXT,active INTEGER,PRIMARY KEY(owner,subject,namespace,key_hash));
CREATE TABLE journal(id INTEGER PRIMARY KEY,owner TEXT,subject TEXT,namespace TEXT,scope TEXT,concept TEXT,at TEXT,payload TEXT);
''')
    policy={'min_groups':4,'candidate_days':60,'stale_days':365,'alpha':.35,'drift':.4}
    c.executemany('INSERT INTO meta VALUES(?,?)',[('schema','1'),('reducer','0.1.0'),('policy',canonical(policy)),('database_id','legacy-demo')])
    c.execute('INSERT INTO subjects VALUES(?,?,?,?)',(*A.values(),3))
    s={'scope':'food','concept_id':'food:cutlet','label':'雞排','stable':.9,'basis':'explicit','familiarity_count':41,'candidate':None,'last_feedback_day':'2026-01-01','overlays':[],'last_confirmed_at':iso(BASE),'last_applied_at':iso(BASE),'revision':1,'source_coverage':'aggregate_only'}
    c.execute('INSERT INTO states VALUES(?,?,?,?,?,?)',(*A.values(),'food','food:cutlet',canonical(s)))
    for tag,identifier in [('event','legacy-event'),('evidence','legacy-evidence')]:
        c.execute('INSERT INTO receipts VALUES(?,?,?,?)',(*A.values(),fingerprint(['food','food:cutlet',tag,identifier])))
    c.execute('INSERT INTO tombstones VALUES(?,?,?,?,?,?)',(*A.values(),fingerprint(['food','food:forgotten']),iso(BASE),1))
    c.commit();c.close()

class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.src=Path(self.tmp.name)/'old.db';self.dst=Path(self.tmp.name)/'new.db';legacy_fixture(self.src)
    def tearDown(self):self.tmp.cleanup()
    def test_migration_source_unchanged(self):
        before=hashlib.sha256(self.src.read_bytes()).hexdigest();migrate(self.src,self.dst)
        self.assertEqual(hashlib.sha256(self.src.read_bytes()).hexdigest(),before)
    def test_stable_and_gap_preserved(self):
        migrate(self.src,self.dst)
        with Memory(self.dst) as m:
            s=m.get(A)['items'][0];self.assertEqual(s['stable'],.9);self.assertEqual(s['familiarity_count'],41)
            self.assertTrue(s['long_evidence']['legacy_gap']);self.assertEqual(s['long_evidence']['groups'],0)
    def test_migrated_receipt_rejects_new_timestamp_replay(self):
        migrate(self.src,self.dst)
        with Memory(self.dst) as m:
            e=ev(5,'feedback',-1,day=100,evidence_id='legacy-evidence')
            self.assertEqual(m.observe(A,e,now=BASE+timedelta(days=101))['status'],'duplicate')
    def test_migrated_deletion_still_blocks_relearn(self):
        migrate(self.src,self.dst)
        with Memory(self.dst) as m:
            e=ev(5,'feedback',-1,day=100,concept='food:forgotten')
            self.assertEqual(m.observe(A,e,now=BASE+timedelta(days=101))['reason'],'forgotten_requires_explicit_relearn')
    def test_future_sparse_learning_after_migration(self):
        migrate(self.src,self.dst)
        with Memory(self.dst) as m:
            for n in range(1,13):m.observe(A,ev(n,'feedback',-1,day=n*90),now=BASE+timedelta(days=n*90+1))
            self.assertLess(m.get(A)['items'][0]['stable'],-.5)
    def test_no_overwrite_destination(self):
        self.dst.write_text('keep');
        with self.assertRaises(ValueError):migrate(self.src,self.dst)
        self.assertEqual(self.dst.read_text(),'keep')
    def test_live_open_legacy_requires_migration(self):
        with self.assertRaises(ValidationError):Memory(self.src)
    def test_migration_rebuilds_bounded_selection(self):
        migrate(self.src,self.dst)
        with Memory(self.dst) as m:
            p=m.compile(A,['food']);self.assertEqual(len(p['items']),1);self.assertEqual(p['omitted_count'],0)
    def test_snapshot_of_migrated_database_roundtrip(self):
        migrate(self.src,self.dst)
        with Memory(self.dst) as m:
            snap=m.export_snapshot(A)
            with Memory(Path(self.tmp.name)/'restored.db') as copy:
                copy.restore_empty(A,snap)
                t=BASE+timedelta(days=100)
                self.assertEqual(copy.compile(A,['food'],now=t),m.compile(A,['food'],now=t))
if __name__=='__main__':unittest.main()
