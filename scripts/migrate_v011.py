#!/usr/bin/env python3
"""Copy a v0.1.x SQLite store to v0.2.0; never edit the source file.

Discarded historical feedback cannot be reconstructed. Existing stable values,
short candidates, watermarks and exact 256-bit deduplication hashes are retained.
The new slow accumulator starts empty and advertises legacy_gap=True.
"""
from __future__ import annotations
import argparse, json, os, sqlite3, tempfile
from pathlib import Path
from memory_core import Memory, Context, Policy, SCHEMA_VERSION, REDUCER_VERSION, canonical


def migrate(source: str | Path, output: str | Path) -> dict:
    source, output = Path(source).expanduser().resolve(), Path(output).expanduser().resolve()
    if not source.is_file(): raise ValueError('source database does not exist')
    if source == output or output.exists(): raise ValueError('output must be a new file; source is never modified')
    output.parent.mkdir(parents=True, exist_ok=True)
    fd, tempname=tempfile.mkstemp(prefix=output.name+'.migrating-',dir=output.parent);os.close(fd)
    temp=Path(tempname)
    old=None;dst=None
    try:
        old=sqlite3.connect(source.as_uri()+'?mode=ro',uri=True)
        meta=dict(old.execute('SELECT key,value FROM meta'))
        if meta.get('schema')!='1' or meta.get('reducer')!='0.1.0':
            raise ValueError('only schema=1 / reducer=0.1.0 (packages 0.1.0 and 0.1.1) is supported')
        dst=sqlite3.connect(temp)
        old.backup(dst);old.close();old=None
        dst.create_function('sha256_blob',1,lambda value: bytes.fromhex(value) if isinstance(value,str) and len(value)==64 else None)
        with dst:
            dst.execute('CREATE TABLE receipt_contexts(id INTEGER PRIMARY KEY,owner TEXT NOT NULL,subject TEXT NOT NULL,namespace TEXT NOT NULL,UNIQUE(owner,subject,namespace))')
            dst.execute('INSERT INTO receipt_contexts(owner,subject,namespace) SELECT DISTINCT owner,subject,namespace FROM receipts')
            dst.execute('CREATE TABLE receipts_new(context_id INTEGER NOT NULL,digest BLOB NOT NULL CHECK(length(digest)=32),PRIMARY KEY(context_id,digest)) WITHOUT ROWID')
            dst.execute('INSERT INTO receipts_new SELECT c.id,sha256_blob(r.digest) FROM receipts r JOIN receipt_contexts c USING(owner,subject,namespace)')
            dst.execute('DROP TABLE receipts');dst.execute('ALTER TABLE receipts_new RENAME TO receipts')
            policy=Policy(**json.loads(meta['policy']))
            for key,value in [('schema',str(SCHEMA_VERSION)),('reducer',REDUCER_VERSION),('policy',canonical(policy.as_dict()))]:
                dst.execute('UPDATE meta SET value=? WHERE key=?',(value,key))
            rows=list(dst.execute('SELECT owner,subject,namespace,scope,concept,data FROM states'))
            for owner,subject,namespace,scope,concept,data in rows:
                state=json.loads(data)
                state['long_evidence']=Memory._long_evidence(legacy_gap=True)
                dst.execute('UPDATE states SET data=? WHERE owner=? AND subject=? AND namespace=? AND scope=? AND concept=?',(canonical(state),owner,subject,namespace,scope,concept))
        dst.close();dst=None
        with Memory(temp) as memory:
            with memory.transaction():
                for row in rows:
                    owner,subject,namespace,scope,concept,_=row
                    ctx=Context(owner,subject,namespace)
                    state=memory._load(ctx,scope,concept)
                    memory._validate_state(state,memory.revision(ctx))
                    memory._save(ctx,state)
            n=memory.conn.execute('SELECT COUNT(*) FROM receipts').fetchone()[0]
            if memory.conn.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('integrity check failed')
            memory.conn.execute('PRAGMA wal_checkpoint(TRUNCATE)')
            memory.conn.execute('VACUUM')
            memory.conn.execute('PRAGMA wal_checkpoint(TRUNCATE)')
        if output.exists(): raise ValueError('output appeared during migration; refusing overwrite')
        os.replace(temp,output)
        return {'status':'migrated','source':str(source),'output':str(output),'states':len(rows),'receipts':n,
                'schema_version':SCHEMA_VERSION,'reducer_version':REDUCER_VERSION,
                'limitation':'Expired or deleted old feedback is not reconstructed; slow evidence starts empty with legacy_gap=true.'}
    finally:
        if old is not None:old.close()
        if dst is not None:dst.close()
        for p in (temp,Path(str(temp)+'-wal'),Path(str(temp)+'-shm')):
            if p.exists():p.unlink()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',required=True);p.add_argument('--output',required=True)
    a=p.parse_args()
    try:print(json.dumps(migrate(a.source,a.output),ensure_ascii=False));return 0
    except (ValueError,OSError,sqlite3.Error) as e:print(json.dumps({'status':'error','message':str(e)},ensure_ascii=False));return 2
if __name__=='__main__':raise SystemExit(main())
