from pathlib import Path
import zipfile,gzip,shutil,json,subprocess,sys,sqlite3,time,hashlib,argparse
p=argparse.ArgumentParser();p.add_argument('--legacy-evidence',type=Path,required=True);p.add_argument('--baseline-root',type=Path,required=True);p.add_argument('--candidate-root',type=Path,required=True);p.add_argument('--out',type=Path,required=True);args=p.parse_args();out=args.out;out.mkdir(parents=True,exist_ok=True)
if (out/'legacy.sqlite3').exists():raise SystemExit('refusing existing output database')
with zipfile.ZipFile(args.legacy_evidence) as z:
 with z.open('results/decade/decade_snapshot.json.gz') as f,gzip.GzipFile(fileobj=f) as g,(out/'legacy-snapshot.json').open('wb') as dest:shutil.copyfileobj(g,dest)
cmd=[sys.executable,str(args.baseline_root/'scripts/memory.py'),'--db',str(out/'legacy.sqlite3'),'--owner','synthetic-owner','--subject','subject-a','restore-empty','--input',str(out/'legacy-snapshot.json')]
t=time.perf_counter();run=subprocess.run(cmd,capture_output=True,text=True);assert run.returncode==0,(run.stdout,run.stderr)
sys.path.insert(0,str(args.candidate_root/'scripts'))
from migrate_v011 import migrate
from memory_core import Memory,Context
before=hashlib.sha256((out/'legacy.sqlite3').read_bytes()).hexdigest();t2=time.perf_counter();m=migrate(out/'legacy.sqlite3',out/'migrated.sqlite3');migration_seconds=time.perf_counter()-t2
a=sqlite3.connect(out/'legacy.sqlite3');b=sqlite3.connect(out/'migrated.sqlite3')
oldstates=[json.loads(x[0]) for x in a.execute('SELECT data FROM states ORDER BY scope,concept')]
newstates=[json.loads(x[0]) for x in b.execute('SELECT data FROM states ORDER BY scope,concept')]
compatible=[{k:v for k,v in x.items() if k!='long_evidence'} for x in newstates]
def rolling(rows,isblob=False):
 h=hashlib.sha256();n=0
 for row in rows:
  x=row[0] if isblob else bytes.fromhex(row[0]);h.update(x);n+=1
 return n,h.hexdigest()
h1=rolling(a.execute('SELECT digest FROM receipts ORDER BY digest'))
h2=rolling(b.execute('SELECT digest FROM receipts ORDER BY digest'),True)
result={'status':'pass','migration':m,'migration_seconds':migration_seconds,'total_seconds':time.perf_counter()-t,'source_sha256_before':before,'source_sha256_after':hashlib.sha256((out/'legacy.sqlite3').read_bytes()).hexdigest(),'old_fields_equal':oldstates==compatible,'all_legacy_gaps_marked':all(x['long_evidence']['legacy_gap'] for x in newstates),'all_new_slow_accumulators_empty':all(x['long_evidence']['groups']==0 for x in newstates),'receipts_count_hash_equal':h1==h2,'receipts_count':h1[0],'receipts_sorted_stream_sha256':h1[1],'source_bytes':(out/'legacy.sqlite3').stat().st_size,'destination_bytes':(out/'migrated.sqlite3').stat().st_size,'sqlite_integrity':b.execute('PRAGMA integrity_check').fetchone()[0]}
a.close();b.close()
assert all(result[x] for x in ['old_fields_equal','all_legacy_gaps_marked','all_new_slow_accumulators_empty','receipts_count_hash_equal'])
assert result['source_sha256_before']==result['source_sha256_after'] and result['sqlite_integrity']=='ok'
(out/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(result,ensure_ascii=False))
