"""A synthetic conversation-to-state demonstration, not a live LLM test.
Signal kinds below are manually labelled examples; no classifier is evaluated.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from memory_core import Context, Memory, ConflictError, atlas_html, iso
from host_adapter import LocalPreferenceHost


def run(output):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    base=datetime(2026,1,1,tzinfo=timezone.utc);ctx=Context("synthetic-owner","demo-user")
    steps=[]
    with tempfile.TemporaryDirectory() as temp:
        m=Memory(Path(temp)/"source.sqlite3");host=LocalPreferenceHost(m,ctx)
        def put(n,day,kind,value,concept="food:chicken-cutlet",scope="food",label="雞排",**kw):
            at=base+timedelta(days=day,seconds=n)
            e={"event_id":f"demo-{n}","evidence_id":f"user-message-{n}","kind":kind,
               "value":value,"scope":scope,"concept_id":concept,"label":label,"role":"user","mode":"real","observed_at":iso(at)}
            e.update(kw)
            return host.commit_user_signal(e,now=at)
        put(1,0,"explicit",.8)
        put(2,0,"explicit",1,"style:clear","core","說明要清楚")
        put(3,0,"explicit",-.8,"style:length","casual","回覆長度")
        put(4,0,"explicit",.9,"style:length","work","回覆長度")
        initial=host.before_reply(["food","casual"],"chat-a",base+timedelta(minutes=1))
        steps.append({"step":"明確長期喜好","synthetic_utterance":"我平常喜歡雞排；聊天簡短，工作詳細。","packet":initial})
        put(5,1,"temporary",-1,expires_at=iso(base+timedelta(days=2)),session_id="chat-a")
        steps.append({"step":"當下例外","synthetic_utterance":"今天中午吃過，今晚先不要雞排。","packet":host.before_reply(["food","casual"],"chat-a",base+timedelta(days=1,hours=1))})
        steps.append({"step":"新聊天不帶入舊 session 例外","packet":host.before_reply(["food","work"],"chat-b",base+timedelta(days=1,hours=2))})
        old=base+timedelta(days=3653)
        steps.append({"step":"十年後仍有底色，但標示歷史偏好","packet":host.before_reply(["food","casual"],"chat-c",old)})
        m.prune_evidence(ctx,iso(old))
        m.close();m=Memory(Path(temp)/"source.sqlite3");host=LocalPreferenceHost(m,ctx)
        steps.append({"step":"刪掉舊證據並重啟，偏好仍在","packet":host.before_reply(["food","casual"],"chat-d",old+timedelta(minutes=1))})
        state=m.get(ctx,["core","food","casual","work"],now=old)
        (output/"memory-atlas.html").write_text(atlas_html(state),encoding="utf-8")
        put(6,3654,"correct",-.9)
        corrected=host.before_reply(["food","casual"],"chat-e",base+timedelta(days=3654,hours=1))
        steps.append({"step":"明確改口立即生效","synthetic_utterance":"不是今天吃膩，我現在真的不喜歡雞排了。","packet":corrected})
        snapshot=m.export_snapshot(ctx)
        with Memory(Path(temp)/"destination.sqlite3") as dest:
            dest.restore_empty(ctx,snapshot)
            received=LocalPreferenceHost(dest,ctx).before_reply(["food","casual"],"chat-e",base+timedelta(days=3654,hours=1))
            assert received==corrected
            steps.append({"step":"另一個本地宿主讀到相同資料","packet_equal":received==corrected,"note":"不是跨廠商真實模型測試"})
        result=m.forget(ctx,"food","food:chicken-cutlet",now=base+timedelta(days=3655))
        try:m.restore_empty(ctx,snapshot)
        except ConflictError:blocked=True
        else:blocked=False
        assert blocked
        steps.append({"step":"忘記後舊備份不能覆蓋現有主體","forget":result,"old_restore_blocked":blocked,
                      "packet":host.before_reply(["food","casual"],"chat-f",base+timedelta(days=3655,hours=1))})
        m.close()
    record={"type":"synthetic_demo_not_llm_eval","steps":steps}
    (output/"transcript.json").write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding="utf-8")
    for step in steps:
        print("✓ "+step["step"])
    print("輸出："+str(output.resolve()))
    print("分類是手動標註，沒有呼叫任何模型；暫存資料庫已清除。")
    return record


if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--output",default=str(ROOT/"reports/demo"));a=p.parse_args();run(a.output)
