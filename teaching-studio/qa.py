#!/usr/bin/env python3
"""Parallel QA + synthetic lesson trials for AnSpace Teaching Studio prototype.
20 scenarios are independent GitHub Actions matrix jobs, not 20 human classes.
No student PII, external content, or LLM API calls.
"""
import argparse
import csv
import json
import statistics
import sys
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
sys.path.insert(0, str(ROOT/"classroom-sim"))
from reflection import simulate, grade

POLICIES=[
 {"concept_clarifier":0,"pair_guidance":0,"ion_scaffold":0,"formative_feedback":0,"scan_rehearsal":0},
 {"concept_clarifier":1,"pair_guidance":1,"ion_scaffold":1,"formative_feedback":1,"scan_rehearsal":0},
 {"concept_clarifier":2,"pair_guidance":2,"ion_scaffold":3,"formative_feedback":3,"scan_rehearsal":0},
 {"concept_clarifier":2,"pair_guidance":2,"ion_scaffold":2,"formative_feedback":2,"scan_rehearsal":1},
 {"concept_clarifier":0,"pair_guidance":2,"ion_scaffold":3,"formative_feedback":1,"scan_rehearsal":0}
]
SURFACES=["desktop","projector","tablet","phone"]
REQUIRED_IDS={"opening","concept","rules","practice","application"}
REQUIRED_ASSESSMENT={"PHT","Wayground","H₂O₂"}

def load_source():
    lesson=json.loads((HERE/"lesson15.json").read_text(encoding="utf-8"))
    html=(HERE/"site-template.html").read_text(encoding="utf-8")
    return lesson,html

def validate_content(lesson,html):
    checks={}
    checks["proper_schema"]=lesson["schema"]=="teaching-studio.lesson.v1"
    sections=lesson["sections"]
    checks["five_stage_views"]=len(sections)==5 and {s["id"] for s in sections}==REQUIRED_IDS
    checks["four_KHBD_phases"]=set(lesson["phaseMinutes"])=={"opening","knowledge","practice","application"}
    checks["time_gap_is_explicit"]=sum(lesson["phaseMinutes"].values())+lesson["sourceGapMinutes"]==lesson["duration"]==45
    checks["knowledge_subduration_9_plus_16"]=sections[1]["minutes"]==9 and sections[2]["minutes"]==16
    checks["all_sections_have_teacher_task_evidence"]=all(all(s.get(k) for k in ("title","prompt","teacher","student","assessment","objective")) for s in sections)
    checks["objective_traceability"]=set(lesson["objectives"][0])>= {"id","text","evidence"} and {o["id"] for o in lesson["objectives"]}=={"K1","K2","K3"}
    checks["teacher_manually_navigates"]=all(token in html for token in ("id=\"prev\"","id=\"next\"","select(index+1)","select(index-1)"))
    checks["never_auto_advance"]=not any(token in html for token in ("setInterval(()=>select", "setTimeout(()=>select", "setInterval(select"))
    checks["speaker_and_teacher_views"]=all(t in html for t in ("id=\"projection-btn\"","id=\"teacher-panels\"","classList.toggle('projection'","id=\"teacher-btn\""))
    checks["keyboard_control"]=all(t in html for t in ("ArrowRight","ArrowLeft","Escape","focus-visible"))
    checks["responsive_layout"]= "@media(max-width:840px)" in html and "max-width:1500px" in html
    checks["offline_no_external_assets"]=not any(x in html.lower() for x in ("<script src=", "<link rel=\"stylesheet\" href=\"http", "<iframe"))
    checks["multiple_assignment_separation"]="nộp đầu tiết sau" in sections[-1]["teacher"].lower() or "nộp đầu tiết sau" in sections[-1]["student"].lower()
    checks["missing_source_flag"]=all(lesson["provenance"].get(k) for k in ("sgk","sgv","waygroundQuestions","sourceGap"))
    checks["tool_not_falsely_marked_production"]="bản mẫu nội bộ" in html.lower()
    checks["H2O2_correct_exception"]="−1" in sections[-1]["assessment"]
    checks["ionic_equation_correct"]="x + 4(−2) = −2" in html
    return checks

def build_site(out):
    lesson,html=load_source()
    data=json.dumps(lesson,ensure_ascii=False,separators=(",",":"))
    data=data.replace("</","<\\/")
    result=html.replace("__LESSON_DATA__",data)
    if "__LESSON_DATA__" in result: raise AssertionError("Placeholder not populated")
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(result,encoding="utf-8")
    return out

def run_scenario(i,out):
    if not 1<=i<=20:raise ValueError("Scenario out of range")
    lesson,html=load_source()
    checks=validate_content(lesson,html)
    policy=POLICIES[(i-1)%5]
    surface=SURFACES[(i-1)//5]
    s=simulate(2026111200+i,policy)
    judges=grade(s)
    checks.update({
      "simulated_students_38":len(s["students"])==38,
      "three_independent_rubric_categories":len(judges)==3 and len({j["judge"] for j in judges})==3,
      "simulated_time_45":s["time_minutes"]==45,
      "no_homework_pregrading":s["home_task_status"].startswith("assigned"),
      "correct_answers_5":all(len(p["answers"])==5 for p in s["students"]),
      "bounded_judge_scores":all(0<=j["score_10"]<=10 for j in judges),
      "all_three_not_exceed_each_requirement":s["all3"]<=min(s["requirements"].values()),
    })
    report={
       "scenario":i,"surface":surface,"policy":policy,"seed":s["seed"],
       "success":all(checks.values()),"checks_total":len(checks),"checks_passed":sum(checks.values()),
       "failures":[k for k,v in checks.items() if not v],
       "classroom":{"student_count":38,"basic":s["basic"],"strong":s["strong"],
          "all3_requirements":s["all3"],"K1":s["requirements"]["K1_concept_notation"],
          "K2_proxy":s["requirements"]["K2_four_rules_proxy"],"K3":s["requirements"]["K3_application"],
          "judge_scores":[j["score_10"] for j in judges],
          "judge_mean":round(statistics.mean(j["score_10"] for j in judges),2)},
       "test_limits":["No graphical browser automation","UI/device checks are static evidence only",
           "Learner and judge scores are synthetic","Five Wayground question stems not yet provided"]}
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"scenario":i,"surface":surface,"pass":report["success"],"passed":report["checks_passed"],"total":report["checks_total"],
                      "students_basic":s["basic"],"all3":s["all3"],"judges":report["classroom"]["judge_scores"]},ensure_ascii=False))
    if not report["success"]:raise AssertionError(report["failures"])
    return report

def aggregate(inputs,out):
    out.mkdir(parents=True,exist_ok=True)
    files=sorted(inputs.glob("scenario-*.json"),key=lambda p:int(p.stem.split("-")[-1]))
    if len(files)!=20:
        raise RuntimeError(f"Expected 20 independent matrix artifacts, found {len(files)}")
    rows=[json.loads(f.read_text(encoding="utf-8")) for f in files]
    if {r["scenario"] for r in rows}!=set(range(1,21)):raise RuntimeError("Missing or duplicate scenario IDs")
    if not all(r["success"] for r in rows):raise RuntimeError("Some scenario failed")
    simple=[]
    for r in rows:
        m=r["classroom"]
        simple.append({"scenario":r["scenario"],"screen":r["surface"],
           "checks_passed":r["checks_passed"],"checks_total":r["checks_total"],"basic_38":m["basic"],
           "all3_38":m["all3_requirements"],"K1_38":m["K1"],"K2_proxy_38":m["K2_proxy"],"K3_38":m["K3"],
           "GK1":m["judge_scores"][0],"GK2":m["judge_scores"][1],"GK3":m["judge_scores"][2],"judge_mean":m["judge_mean"]})
    with (out/"scenarios_20.csv").open("w",encoding="utf-8-sig",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=list(simple[0]));writer.writeheader();writer.writerows(simple)
    averages={k:round(statistics.mean(r[k] for r in simple),2) for k in ("basic_38","all3_38","K1_38","K2_proxy_38","K3_38","GK1","GK2","GK3","judge_mean")}
    (out/"summary.json").write_text(json.dumps({"passed":20,"total":20,"all_pass":True,"averages":averages,
       "checks_each":rows[0]["checks_total"],"limits":rows[0]["test_limits"]},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    build_site(out/"AnSpace_Teaching_Studio_Demo.html")
    lines=["# AnSpace Teaching Studio – 20 parallel test reports","",
        "**20 independent Actions matrix jobs submitted with max-parallel: 20. Actual scheduling depends on GitHub runner availability.**",
        "**This verifies data contract, lesson flow, static UI structure and synthetic classroom simulation, not a real browser or real students.**","",
        "## Outcomes","",
        f"- Passed: {sum(r['success'] for r in rows)}/20 independent cases.",
        f"- Checks per case: {rows[0]['checks_total']}; all passed.",
        f"- Mean basic attainment: {averages['basic_38']}/38.",
        f"- Mean all three objectives: {averages['all3_38']}/38.",
        f"- Rubric mean GK1 / GK2 / GK3: {averages['GK1']}, {averages['GK2']}, {averages['GK3']}.",
        "",
        "## Scenarios","",
        "|Case|Screen profile|Passed checks|Basic|All 3|GK1|GK2|GK3|","|---:|---|---:|---:|---:|---:|---:|"]
    for r in simple:
        lines.append(f"|{r['scenario']}|{r['screen']}|{r['checks_passed']}/{r['checks_total']}|{r['basic_38']}/38|{r['all3_38']}/38|{r['GK1']}|{r['GK2']}|{r['GK3']}|")
    lines+=["","## Model limitations","",
        "- Screen profiles do NOT mean actual tests on corresponding devices.",
        "- A browser-based interaction and screenshot suite remains to be run before production.",
        "- The source lesson lacks five full Wayground question stems and SGK/SGV assets.",
        "- 3 rubric judges are algorithms, not separate AI language models.",
        "- No student identities or protected textbook files are uploaded.",
        "- KHBD original is not overwritten. Source leaves three minutes unallocated.",
        "",
        "## Product architecture",
        "",
        "1. Library: subject → topic → lesson → session.",
        "2. Lesson contract: objectives, four KHBD phases, source links, products, assessment and time.",
        "3. Presentation runtime: teacher-controlled navigation, projector-only content, private notes, pauseable timer, accessible keys.",
        "4. Activity plugins: bond comparison, charge notation, stepwise oxidation calculator, QR assessment reference, H₂O₂ homework.",
        "5. Simulation service: 38 probabilistic learner profiles and traceable three-judge rubric.",
        "6. Experience store: versioned results, change proposals, comparisons; never alter uploaded source.",
        "7. Data isolation: public static prototype; future private licensed learning materials in authenticated storage, real student data separated.",
        "8. Quality gates: source completeness, lesson traceability, browser E2E, accessibility, offline and privacy checks before publication.",
        ]
    (out/"REPORT_20_TESTS.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    print(json.dumps({"summary":"20/20 PASS","averages":averages},ensure_ascii=False))

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--scenario",type=int)
    p.add_argument("--out",type=Path)
    p.add_argument("--aggregate",type=Path)
    p.add_argument("--build",type=Path)
    a=p.parse_args()
    if a.aggregate:aggregate(a.aggregate,a.out)
    elif a.build:build_site(a.build)
    elif a.scenario:run_scenario(a.scenario,a.out)
    else:p.error("need scenario, build or aggregate")
