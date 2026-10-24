"""Regressions discovered by actual data-volume testing; no LLM involved."""
from __future__ import annotations
import importlib.util, json, sys, tempfile, unittest
from pathlib import Path
from datetime import timedelta
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from memory_core import Memory,Context,ValidationError,canonical
from test_memory import BASE,ev
from memory import read_json
A=Context('regression-owner','user-a')
class ScaleRegressions(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.m=Memory(Path(self.tmp.name)/'m.sqlite3');self.now=BASE+timedelta(days=20)
 def tearDown(self):self.m.close();self.tmp.cleanup()
 def add(self,n,concept,value=.1,scope='food',kind='explicit'):
  return self.m.observe(A,ev(n,kind,value,concept=concept,scope=scope),now=self.now)
 def ids(self,p):return {(x['scope'],x['concept_id']) for x in p['items']}
 def test_old_strong_preference_survives_forty_later_weak_entries(self):
  self.add(1,'food:old',.9)
  for n in range(2,42):self.add(n,f'food:new-{n}',.1)
  self.assertIn(('food','food:old'),self.ids(self.m.compile(A,['food'],now=self.now)))
 def test_mentions_do_not_promote_weak_entries_above_old_strong(self):
  self.add(1,'food:old',.9)
  for n in range(2,42):self.add(n,f'food:new-{n}',.1)
  for n in range(42,142):self.add(n,f'food:new-{2+n%40}',kind='mention')
  self.assertIn(('food','food:old'),self.ids(self.m.compile(A,['food'],now=self.now)))
 def test_low_strength_requested_concept_is_still_readable(self):
  self.add(1,'food:exact',.1)
  for n in range(2,42):self.add(n,f'food:strong-{n}',.95)
  p=self.m.compile(A,['food'],now=self.now,concept_ids=['food:exact'])
  self.assertEqual(p['items'][0]['concept_id'],'food:exact')
 def test_requested_concept_cannot_escape_scope(self):
  self.add(1,'work:private',.8,'work');self.add(2,'food:ok',.5)
  p=self.m.compile(A,['food'],now=self.now,concept_ids=['work:private'])
  self.assertNotIn(('work','work:private'),self.ids(p))
 def test_request_does_not_invent_unknown_memory(self):
  self.add(1,'food:exists',.5)
  p=self.m.compile(A,['food'],now=self.now,concept_ids=['food:missing'])
  self.assertNotIn(('food','food:missing'),self.ids(p))
 def test_core_crowding_leaves_room_for_domain(self):
  for n in range(1,41):self.add(n,f'core:{n}',.9,'core')
  self.add(41,'food:target',.8)
  self.assertIn(('food','food:target'),self.ids(self.m.compile(A,['food'],now=self.now)))
 def test_multi_domain_each_has_representative(self):
  for n in range(1,41):self.add(n,f'food:{n}',.9)
  self.add(41,'work:target',.1,'work')
  self.assertIn(('work','work:target'),self.ids(self.m.compile(A,['food','work'],now=self.now)))
 def test_requested_dedup_and_budget(self):
  for n in range(1,20):self.add(n,f'food:{n}',.5)
  p=self.m.compile(A,['food'],now=self.now,concept_ids=['food:1','food:1'],max_items=4,max_chars=1800)
  self.assertEqual(len(self.ids(p)),len(p['items']));self.assertLessEqual(len(canonical(p)),1800)
  self.assertEqual(p['omitted_count']+len(p['items']),19)
 def test_bad_concept_list_rejected(self):
  for x in ([], 'food:1', [None], ['x']*101):
   with self.subTest(x=str(x)[:25]):
    with self.assertRaises(ValidationError):self.m.compile(A,['food'],now=self.now,concept_ids=x)
 def test_restored_old_database_uses_new_selection(self):
  self.add(1,'food:old',.9)
  for n in range(2,42):self.add(n,f'food:new-{n}',.1)
  snapshot=self.m.export_snapshot(A)
  with Memory(Path(self.tmp.name)/'copy.sqlite3') as dst:
   dst.restore_empty(A,snapshot)
   self.assertIn(('food','food:old'),self.ids(dst.compile(A,['food'],now=self.now)))
 def test_full_read_no_writes(self):
  self.add(1,'food:old',.9);r=self.m.revision(A)
  self.m.compile(A,['food'],now=self.now,concept_ids=['food:old'])
  self.assertEqual(self.m.revision(A),r)
 def test_configurable_json_budget(self):
  p=Path(self.tmp.name)/'data.json';p.write_text(json.dumps({'x':'a'*1000}))
  with self.assertRaises(ValueError):read_json(str(p),max_bytes=100)
  self.assertEqual(len(read_json(str(p),max_bytes=2000)['x']),1000)
 def test_nonfinite_input_still_rejected(self):
  p=Path(self.tmp.name)/'bad.json';p.write_text('{"x":NaN}')
  with self.assertRaises(ValueError):read_json(str(p),max_bytes=2000)
 def test_forgetting_removes_requested_concept(self):
  self.add(1,'food:old',.9);self.m.forget(A,'food','food:old',now=self.now)
  p=self.m.compile(A,['food'],now=self.now,concept_ids=['food:old'])
  self.assertNotIn(('food','food:old'),self.ids(p))
