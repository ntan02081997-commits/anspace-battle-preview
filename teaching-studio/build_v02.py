#!/usr/bin/env python3
"""Build and verify a source-grounded 45-min teaching presentation.
No paid dependencies; no real student data or protected textbook material.
"""
import json
import pathlib
import re
ROOT=pathlib.Path(__file__).resolve().parent
lesson=json.loads((ROOT/"pro-lesson-v02.json").read_text(encoding="utf8"))
tpl=(ROOT/"pro-template-v02.html").read_text(encoding="utf8")
slides=lesson["slides"]
assert len(slides)==30, "Expected 30 screens"
assert slides[0]["from"]==0 and slides[-1]["to"]==45
assert all(abs(slides[i]["to"]-slides[i+1]["from"])<.001 for i in range(len(slides)-1)), "Disjoint timeline"
assert all(s["teacher"] and s["evidence"] and s["body"] for s in slides)
assert len([s for s in slides if s["kind"]=="quiz"])==5
assert [s["correct"] for s in slides if s["kind"]=="quiz"]==[1,2,1,0,2]
assert all(s.get("sourceStatus") for s in slides if s["kind"]=="quiz")
assert sum((p["to"]-p["from"]) for p in lesson["timing"]["phases"])==45
assert [p["to"]-p["from"] for p in lesson["timing"]["phases"]]==[4,9,16,12,3,1]
assert "3 phút" in lesson["timing"]["unallocatedExplanation"]
assert tpl.count("__DECK__")==1
assert "setInterval(()=>select" not in tpl
assert "[hidden]{display:none!important}" in tpl
assert "id=\"teacher-panels\"" in tpl and "id=\"pop-btn\"" in tpl
assert not any(z in tpl.lower() for z in ["supabase.co","service_role","/rest/v1"])
data=json.dumps(lesson,ensure_ascii=False,separators=(",",":")).replace("</","<\\/")
out=tpl.replace("__DECK__",data)
assert "<script id=\"lesson-data\"" in out and "__DECK__" not in out
dist=ROOT/"dist";dist.mkdir(exist_ok=True)
(dist/"index.html").write_text(out,encoding="utf8")
(dist/"BUILD_REPORT.json").write_text(json.dumps({
    "ready":True,"version":lesson["version"],"screens":len(slides),
    "totalMinutes":slides[-1]["to"],"lesson":"Bài 15 Tiết 1",
    "quizDemoOnly":True,"sgkSgvProvided":False,
    "projector":"separate window, BroadcastChannel with localStorage fallback",
    "originalKHBDNotModified":True,
    "notes":"Not a browser E2E pass until exercised with real Chromium"
},ensure_ascii=False,indent=2)+"\n",encoding="utf8")
print("Build PASS: 30 screens, 45 min, 5 explicitly labelled sample questions")
