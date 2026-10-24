"""Run reproducible unit tests and optional long-horizon simulations."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import io
import json
import platform
import sqlite3
import sys
import time
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tests"))

class RecordedResult(unittest.TextTestResult):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs);self.cases=[]
    def addSuccess(self,test):
        super().addSuccess(test);self.cases.append({"test":test.id(),"status":"pass"})
    def addFailure(self,test,err):
        super().addFailure(test,err);self.cases.append({"test":test.id(),"status":"fail","error":self._exc_info_to_string(err,test)})
    def addError(self,test,err):
        super().addError(test,err);self.cases.append({"test":test.id(),"status":"error","error":self._exc_info_to_string(err,test)})

def main():
    p=argparse.ArgumentParser();p.add_argument("--seeds",type=int,default=12);p.add_argument("--steps",type=int,default=10000)
    p.add_argument("--unit-only",action="store_true");p.add_argument("--output",default=str(ROOT/"reports/local-run"))
    args=p.parse_args();out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
    if not 1<=args.seeds<=100 or not 1<=args.steps<=100000:p.error("seeds 1-100; steps 1-100000")
    start=time.perf_counter();stream=io.StringIO()
    suite=unittest.defaultTestLoader.discover(str(ROOT/"tests"),pattern="test_*.py")
    result=unittest.TextTestRunner(stream=stream,verbosity=2,resultclass=RecordedResult).run(suite)
    (out/"unit-tests.txt").write_text(stream.getvalue(),encoding="utf-8");print(stream.getvalue(),end="")
    report={"at":datetime.now(timezone.utc).isoformat(),"python":sys.version,"platform":platform.platform(),
            "sqlite":sqlite3.sqlite_version,"tests":result.testsRun,"passed":sum(c["status"]=="pass" for c in result.cases),
            "failures":len(result.failures),"errors":len(result.errors),"cases":result.cases,
            "unit_wall_seconds":round(time.perf_counter()-start,4)}
    (out/"unit-tests.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    if not result.wasSuccessful():return 1
    if not args.unit_only:
        from simulate import run
        sim=run(args.seeds,args.steps)
        (out/"simulation.json").write_text(json.dumps(sim,ensure_ascii=False,indent=2),encoding="utf-8")
    return 0
if __name__=="__main__":raise SystemExit(main())
