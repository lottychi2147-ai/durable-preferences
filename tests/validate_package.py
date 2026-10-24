"""Local package/CLI/install checks. Not the official skills-ref validator."""
from __future__ import annotations
import ast
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]

def run():
    checks=[]
    def record(name,condition):
        if not condition: raise AssertionError(name)
        checks.append({"check":name,"status":"pass"})
    text=(ROOT/"SKILL.md").read_text(encoding="utf-8")
    record("SKILL.md YAML frontmatter delimiters",text.startswith("---\n") and "\n---\n" in text[4:])
    front=text.split("---",2)[1]
    name=re.search(r"^name:\s*(.+)$",front,re.M).group(1)
    record("name matches directory and allowed characters",name==ROOT.name and re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*",name) is not None and len(name)<=64)
    description=front.split("description:",1)[1].split("compatibility:",1)[0].replace(">-","").strip()
    record("description length",0<len(description)<=1024)
    record("progressive disclosure: SKILL.md under 500 lines",len(text.splitlines())<500)
    for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)",text):
        if not target.startswith(("https://","http://","#")):
            record("reference exists: "+target,(ROOT/target).is_file())
    for file in ROOT.rglob("*.py"):
        ast.parse(file.read_text(encoding="utf-8"),filename=str(file))
    record("all Python files parse",True)
    for file in (ROOT/"assets").glob("*.json"):
        json.loads(file.read_text(encoding="utf-8"))
    record("JSON assets parse",True)
    record("no bundled live database",not any(ROOT.rglob("*.sqlite3")))
    with tempfile.TemporaryDirectory() as temp:
        parent=Path(temp)/"skills"
        cmd=[sys.executable,str(ROOT/"scripts/install_skill.py"),"--target",str(parent)]
        dry=subprocess.run(cmd,capture_output=True,text=True)
        record("installer dry run does not copy",dry.returncode==0 and not parent.exists())
        installed=subprocess.run(cmd+["--apply"],capture_output=True,text=True)
        target=parent/ROOT.name
        record("installer copies full package",installed.returncode==0 and (target/"scripts/memory.py").exists())
        again=subprocess.run(cmd+["--apply"],capture_output=True,text=True)
        record("installer refuses overwrite",again.returncode!=0)
        cli=subprocess.run([sys.executable,str(target/"scripts/memory.py"),"--db",str(Path(temp)/"private/state.sqlite3"),"--owner","demo","--subject","a","compile","--scopes","food"],capture_output=True,text=True)
        record("installed CLI works with blank external store",cli.returncode==0 and json.loads(cli.stdout)["items"]==[])
    return {"validator":"local structural / install smoke checks; not skills-ref", "passed":len(checks),"checks":checks}

if __name__=="__main__":
    result=run();print(json.dumps(result,ensure_ascii=False,indent=2))
