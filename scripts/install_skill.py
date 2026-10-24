"""Copy this skill to an explicitly selected skill directory; dry-run by default."""
from __future__ import annotations
import argparse
import json
import shutil
from pathlib import Path


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--target",required=True,help="Parent skills directory, e.g. ~/.agents/skills")
    p.add_argument("--apply",action="store_true",help="Actually copy; never overwrites an existing skill")
    a=p.parse_args();source=Path(__file__).resolve().parents[1]
    dest=Path(a.target).expanduser().resolve()/source.name
    if dest==source or source in dest.parents:
        p.error("destination cannot be within source")
    if dest.exists(): p.error("destination already exists; no overwrite performed")
    result={"source":str(source),"destination":str(dest),"status":"dry_run"}
    if a.apply:
        dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copytree(source,dest,ignore=shutil.ignore_patterns("__pycache__","*.pyc","*.sqlite3","*.sqlite3-wal","*.sqlite3-shm","local-run"))
        result["status"]="copied"
    result["note"]="Files only. Host discovery/activation and persistent DB configuration are separate."
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=="__main__":main()
