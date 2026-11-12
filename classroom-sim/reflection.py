#!/usr/bin/env python3
"""Adaptive, evidence-traced rehearsal loop for KHBD B15/T1.
Synthetic pupils and rubric judges; NOT 42 independent LLM agents.
Never overwrites the uploaded original KHBD. No real student data.
"""
import argparse
import csv
import json
import random
import statistics
from pathlib import Path

from simulate import make_class, CORRECT

SLOTS = {"opening":4, "concept":9, "rules":16, "paper":12, "handoff":4}
LIMITS = {"concept_clarifier":2,"pair_guidance":2,"ion_scaffold":3,
          "formative_feedback":3,"scan_rehearsal":1}
CHANGE_NOTES = {
 "concept_clarifier": ("HĐ 2.1", "Thêm câu truy vấn so sánh số oxi hóa và điện tích ion trong H₂O; thay một phần thời gian kết luận, không tăng 9 phút."),
 "pair_guidance": ("HĐ 2.1", "Giao nhiệm vụ cho hai vai trong mỗi cặp: giải thích và kiểm tra dấu/số; giữ thời lượng 2 phút cá nhân + 2 phút cặp."),
 "ion_scaffold": ("HĐ 2.2", "Trước khi tính SO₄²⁻, HS nói rõ tổng số oxi hóa bằng điện tích ion; dùng 45 giây trong phần chuẩn hóa hiện có."),
 "formative_feedback": ("HĐ 3", "Sau thống kê QR, yêu cầu HS giải thích một lựa chọn sai và thử sửa trước khi công bố lời giải; rút thời gian công bố đáp án đơn thuần."),
 "scan_rehearsal": ("HĐ 3", "Cho HS thử tư thế giơ thẻ trong lúc phát thẻ QR để giảm lỗi quét; không tăng 12 phút.")
}

def clip(x):
    return max(.02,min(.98,x))

def learn(p,k,delta):
    p["skills"][k]=clip(p["skills"][k]+delta*(1-p["skills"][k]))

def chance(r,p,k,t):
    return r[t] < clip(.13+.83*p["skills"][k]*p["effort"])

def simulate(seed, policy):
    rng=random.Random(seed)
    students=make_class(rng)
    for p in students:
        p["_r"]=[rng.random() for _ in range(32)]
        p["before"]=dict(p["skills"])
    events=[{"minute":0,"phase":"opening","evidence":"GV uses NaCl–H₂O question; pupils recall electron transfer vs polarization"}]
    for p in students:
        learn(p,"concept",.10+.045*policy["concept_clarifier"])
        p["participation"]=chance(p["_r"],p,"concept",0)
    events.append({"minute":4,"phase":"PHT1","evidence":"2-minute individual + 2-minute pair; teacher checks definition and notation"})
    for a,b in zip(students[::2],students[1::2]):
        for p in (a,b):
            peer=.04 if b["group"]=="fast" or a["group"]=="fast" else 0
            learn(p,"concept",.18+.04*policy["concept_clarifier"]+peer)
            learn(p,"notation",.19+.045*policy["pair_guidance"]+peer)
            p["pht1"]={
                "definition":chance(p["_r"],p,"concept",1),
                "representation":chance(p["_r"],p,"notation",2),
            }
            if not p["pht1"]["representation"]:
                learn(p,"notation",.10+.025*policy["formative_feedback"])
    events.append({"minute":13,"phase":"PHT2","evidence":"SO₂ modeled; Fe, H₂SO₄, SO₄²⁻; optional NH₄⁺ and explain ion sum"})
    for p in students:
        learn(p,"rules",.29)
        learn(p,"neutral",.26)
        learn(p,"ions",.18+.075*policy["ion_scaffold"])
        learn(p,"application",.12+.03*policy["ion_scaffold"])
        p["pht2"]={
            "Fe":chance(p["_r"],p,"rules",3),
            "H2SO4":chance(p["_r"],p,"neutral",4),
            "SO4_2minus":chance(p["_r"],p,"ions",5),
        }
        p["ion_misconception"]=not p["pht2"]["SO4_2minus"]
        if p["ion_misconception"]:
            learn(p,"ions",.10+.06*policy["ion_scaffold"])
            p["ion_recovery"]=chance(p["_r"],p,"ions",12)
        else:
            p["ion_recovery"]=True
    errors=sum(p["ion_misconception"] for p in students)
    recovered=sum(p["ion_recovery"] for p in students if p["ion_misconception"])
    events.append({"minute":29,"phase":"Wayground Paper","evidence":f"{errors}/38 pupils initially confuse ion total or miss SO₄²⁻ task; QR five skill-proxy items"})
    for p in students:
        p["answers"]=[]
        for i,k in enumerate(["concept","notation","neutral","ions","application"]):
            right=chance(p["_r"],p,k,6+i)
            p["answers"].append(CORRECT[i] if right else "ABCD"[("ABCD".index(CORRECT[i])+1+i)%4])
        p["correct_count"]=sum(a==b for a,b in zip(p["answers"],CORRECT))
        if p["answers"][3]!=CORRECT[3]:
            learn(p,"ions",.06+.045*policy["formative_feedback"])
            p["feedback_recovery"]=chance(p["_r"],p,"ions",13)
        else:
            p["feedback_recovery"]=True
        p["after"]=dict(p["skills"])
        q=[a==b for a,b in zip(p["answers"],CORRECT)]
        h1,h2=p["pht1"],p["pht2"]
        p["requirements"]={
            "K1_concept_notation": (h1["definition"] and h1["representation"]) or (q[0] and q[1]),
            "K2_four_rules_proxy": h2["Fe"] and (h2["H2SO4"] or q[2]),
            "K3_application": h2["H2SO4"] and h2["SO4_2minus"] and (q[3] or q[4]),
        }
        p["competencies"]={
            "self_learning":p["effort"]>=.87 and h1["definition"],
            "collaboration":p["collaboration"]>=.57 and p["participation"],
            "chemical_recognition":p["requirements"]["K1_concept_notation"],
            "application":p["requirements"]["K3_application"],
            "problem_solving":h2["H2SO4"] and h2["SO4_2minus"],
        }
        p["qualities"]={
            "diligence":p["effort"]>=.87,
            "honesty_observed_proxy":p["_r"][14] < clip(.62+.30*p["effort"]),
            "responsibility":p["collaboration"]>=.57,
        }
    events.append({"minute":41,"phase":"H₂O₂ homework/recap","evidence":"4 true/false statements assigned for NEXT lesson; not graded now"})
    events.append({"minute":45,"phase":"end","evidence":"45 minutes elapsed; teacher reflection begins"})
    req={k:sum(p["requirements"][k] for p in students) for k in students[0]["requirements"]}
    comp={k:sum(p["competencies"][k] for p in students) for k in students[0]["competencies"]}
    qual={k:sum(p["qualities"][k] for p in students) for k in students[0]["qualities"]}
    basic=sum(p["correct_count"]>=3 for p in students)
    strong=sum(p["correct_count"]>=4 for p in students)
    all3=sum(all(p["requirements"].values()) for p in students)
    correct_by_question=[sum(p["answers"][j]==CORRECT[j] for p in students) for j in range(5)]
    return {"seed":seed,"policy":dict(policy),"students":students,"events":events,
        "requirements":req,"competencies":comp,"qualities":qual,"all3":all3,
        "basic":basic,"strong":strong,"correct_by_question":correct_by_question,
        "mean_gain":round(statistics.mean(sum(p["after"][k]-p["before"][k] for k in p["before"])/6 for p in students),4),
        "misconceptions":errors,"ion_recovered":recovered,
        "feedback_recovered":sum(p["feedback_recovery"] for p in students if p["answers"][3]!=CORRECT[3]),
        "feedback_missed":sum(p["answers"][3]!=CORRECT[3] for p in students),
        "home_task_status":"assigned; not yet assessed",
        "time_minutes":sum(SLOTS.values())}

def grade(s):
    n=38
    policy=s["policy"]
    req=s["requirements"]; comp=s["competencies"]
    k1=req["K1_concept_notation"]/n
    k2=req["K2_four_rules_proxy"]/n
    k3=req["K3_application"]/n
    engagement=sum(p["participation"] for p in s["students"])/n
    ion_recovery_rate=s["ion_recovered"]/max(1,s["misconceptions"])
    feedback_recovery_rate=s["feedback_recovered"]/max(1,s["feedback_missed"])
    # Distinct rubric functions; each outputs criteria with observable evidence.
    g1={
       "scientific_correctness_4":3.8,
       "knowledge_objectives_2":round(2*(.3*k1+.35*k2+.35*k3),2),
       "misconception_handling_2":round(min(2,.45+1.35*ion_recovery_rate+.10*policy["ion_scaffold"]),2),
       "differentiated_practice_2":round(min(2,.9+.30*policy["pair_guidance"]+.16*policy["ion_scaffold"]),2),
    }
    g2={
       "four_activity_flow_2":1.9,
       "active_learning_3":round(min(3,.85+2*engagement+.22*policy["pair_guidance"]),2),
       "scaffolding_and_response_3":round(min(3,.65+1.2*ion_recovery_rate+.18*policy["ion_scaffold"]+.24*policy["pair_guidance"]),2),
       "time_and_materials_2":round(max(.3,min(2,1.75+.17*policy["scan_rehearsal"]-.08*max(0,sum(policy.values())-7))),2)
    }
    g3={
       "evidence_for_objectives_3":round(min(3,1.1+.8*(k1+k2+k3)/3+.20*policy["formative_feedback"]),2),
       "prepost_progress_2":round(min(2,.45+3*s["mean_gain"]),2),
       "use_feedback_to_adapt_3":round(min(3,.55+1.55*feedback_recovery_rate+.16*policy["formative_feedback"]),2),
       "competency_quality_evidence_2":round(min(2,.75+comp["collaboration"]/n+.10*policy["pair_guidance"]),2),
    }
    items=[]
    for name,parts in [("GK1_chuyen_mon",g1),("GK2_su_pham",g2),("GK3_danh_gia",g3)]:
        total=round(sum(parts.values()),2)
        items.append({"judge":name,"criteria":parts,"score_10":total,
             "evidence":{"K1":req["K1_concept_notation"],"K2_proxy":req["K2_four_rules_proxy"],
                         "K3":req["K3_application"],"basic":s["basic"],
                         "misconception_SO4":s["misconceptions"],"ion_recovered":s["ion_recovered"],
                         "feedback_recovered":s["feedback_recovered"],
                         "mean_gain":s["mean_gain"]}})
    return items

def value(s, judges):
    # Teacher objective combines all-knowledge achievement, basic attainment and quality.
    return .50*s["all3"]/38 + .20*s["basic"]/38 + .30*sum(j["score_10"] for j in judges)/30

def propose(s, judges, policy, blocked=None):
    blocked=set(blocked or ())
    req=s["requirements"]
    candidate=[]
    if req["K3_application"] < 27: candidate.append("ion_scaffold")
    if judges[2]["score_10"] < 8.0: candidate.append("formative_feedback")
    if req["K1_concept_notation"] < 30: candidate.append("concept_clarifier")
    if s["competencies"]["collaboration"] < 28: candidate.append("pair_guidance")
    if s["correct_by_question"][3] < 29: candidate.append("ion_scaffold")
    if s["basic"]<28: candidate.append("formative_feedback")
    candidate+=["pair_guidance","scan_rehearsal","concept_clarifier"]
    for key in candidate:
        if policy[key]<LIMITS[key] and key not in blocked:
            return key
    return None

def paired_accept(old, candidate, iteration):
    """Independent fixed holdout seeds; accept if evidence-weighted score doesn't decrease."""
    seeds=[990000+iteration*37+i for i in range(12)]
    old_vals=[];new_vals=[];old_k3=[];new_k3=[];old_all=[];new_all=[]
    for seed in seeds:
        s_old=simulate(seed,old);s_new=simulate(seed,candidate)
        old_vals.append(value(s_old,grade(s_old)))
        new_vals.append(value(s_new,grade(s_new)))
        old_k3.append(s_old["requirements"]["K3_application"])
        new_k3.append(s_new["requirements"]["K3_application"])
        old_all.append(s_old["all3"]);new_all.append(s_new["all3"])
    d=statistics.mean(new_vals)-statistics.mean(old_vals)
    # Prevent reward hacking: scores cannot justify lower achievement on held-out pupils.
    learning_not_worse=(statistics.mean(new_k3)>=statistics.mean(old_k3)
                        and statistics.mean(new_all)>=statistics.mean(old_all))
    return (d>=.001 and learning_not_worse),round(d,5)

def reflect(s,judges,old_policy,iteration,blocked):
    key=propose(s,judges,old_policy,blocked)
    if key is None:
        return dict(old_policy), {"status":"no_change_available",
          "reason":"All interventions capped or rejected in this exact policy state; no repeated failed experiment."}
    next_policy=dict(old_policy);next_policy[key]+=1
    approved,paired_gain=paired_accept(old_policy,next_policy,iteration)
    note=CHANGE_NOTES[key]
    if not approved:
        next_policy=dict(old_policy)
    return next_policy, {"status":"trial_accepted" if approved else "trial_rejected",
      "action":key,"target_KHBD_section":note[0],"proposed_revision":note[1],
      "paired_holdout_gain":paired_gain,
      "reason":"Targets a specific weakness; evaluated against unchanged policy on 12 paired held-out cohorts",
      "source_preserved":True}

def strip_student(s):
    return {"seed":s["seed"],"policy":s["policy"],"requirements":s["requirements"],
            "competencies":s["competencies"],"qualities":s["qualities"],
            "basic":s["basic"],"strong":s["strong"],"all3":s["all3"],
            "correct_by_question":s["correct_by_question"],
            "mean_gain":s["mean_gain"],"misconceptions":s["misconceptions"],
            "ion_recovered":s["ion_recovered"],"feedback_recovered":s["feedback_recovered"],
            "home_task_status":s["home_task_status"],"time_minutes":s["time_minutes"]}

def run(state_path, out_dir, lessons):
    if state_path.exists():
        history=json.loads(state_path.read_text(encoding="utf-8"))
    else:
        history={"schema":"khbd15-reflection-v2","source":"KHBD 15.1 (1).docx, read-only",
          "important_limitations":[
            "Synthetic agents only, not 42 independent language models.",
            "Wayground five question stems unavailable; skill proxy answers, no fidelity claim.",
            "Four-rule ability inferred from PHT proxies; no separate verbatim recall assessment.",
            "H2O2 homework cannot be scored until the next lesson.",
            "Judge scores are rubric formulas; they are not independent human or LLM opinions.",
            "Never infer real educational effectiveness from simulation alone."],
          "policy":{k:0 for k in LIMITS},"sessions":[]}
    for old_session in history["sessions"]:
        old_session.setdefault("rubric_version","v2.0_legacy")
    history["schema"]="khbd15-reflection-v2.1"
    for _ in range(lessons):
        i=len(history["sessions"])+1
        seed=151001+i*211
        old=dict(history["policy"])
        lesson=simulate(seed,old)
        judges=grade(lesson)
        baseline=simulate(seed,{k:0 for k in LIMITS})
        b_judges=grade(baseline)
        rejected={x["reflection"]["change_for_next_lesson"].get("action")
                  for x in history["sessions"]
                  if x["reflection"]["change_for_next_lesson"]["status"]=="trial_rejected"
                  and x["lesson_metrics"]["policy"]==old}
        after,rec=reflect(lesson,judges,old,i,rejected)
        history["sessions"].append({
            "lesson":i,"seed":seed,"rubric_version":"v2.1_evidence_guard","lesson_metrics":strip_student(lesson),
            "paired_baseline_metrics":strip_student(baseline),
            "judges":judges,"judge_mean":round(statistics.mean(j["score_10"] for j in judges),2),
            "score_delta_vs_baseline":round(value(lesson,judges)-value(baseline,b_judges),5),
            "reflection":{
                "strengths":["Bốn hoạt động và thời lượng của KHBD được giữ nguyên.",
                             "Có PHT 1, PHT 2, Paper Mode và giao bài H₂O₂ về nhà."],
                "weaknesses": [
                    f"{38-lesson['requirements']['K1_concept_notation']}/38 chưa đạt minh chứng khái niệm/biểu diễn.",
                    f"{38-lesson['requirements']['K2_four_rules_proxy']}/38 chưa đạt minh chứng 4 quy tắc (proxy).",
                    f"{38-lesson['requirements']['K3_application']}/38 chưa đạt minh chứng vận dụng.",
                    f"{lesson['misconceptions']}/38 nhầm/sai SO₄²⁻ ban đầu."
                ],
                "judge_feedback": [
                    f"{j['judge']}: {j['score_10']}/10; tiêu chí: "+", ".join(f"{k}={v}" for k,v in j["criteria"].items())
                    for j in judges
                ],
                "change_for_next_lesson":rec,
                "next_policy":after,
            },
            "events":lesson["events"],
        })
        history["policy"]=after
    out_dir.mkdir(parents=True,exist_ok=True)
    state_path.parent.mkdir(parents=True,exist_ok=True)
    state_path.write_text(json.dumps(history,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    rows=[]
    for x in history["sessions"]:
        row={"lesson":x["lesson"],"rubric_version":x.get("rubric_version","v2.0_legacy"),"seed":x["seed"],"all3":x["lesson_metrics"]["all3"],
            "basic":x["lesson_metrics"]["basic"],"strong":x["lesson_metrics"]["strong"],
            "K1":x["lesson_metrics"]["requirements"]["K1_concept_notation"],
            "K2_proxy":x["lesson_metrics"]["requirements"]["K2_four_rules_proxy"],
            "K3":x["lesson_metrics"]["requirements"]["K3_application"],
            "GK1":x["judges"][0]["score_10"],"GK2":x["judges"][1]["score_10"],
            "GK3":x["judges"][2]["score_10"],"judge_mean":x["judge_mean"],
            "change":x["reflection"]["change_for_next_lesson"].get("action","none"),
            "change_status":x["reflection"]["change_for_next_lesson"]["status"],
            "paired_holdout_gain":x["reflection"]["change_for_next_lesson"].get("paired_holdout_gain",0)}
        rows.append(row)
    with (out_dir/"every_lesson_scores.csv").open("w",newline="",encoding="utf-8-sig") as f:
        writer=csv.DictWriter(f,fieldnames=rows[0].keys());writer.writeheader();writer.writerows(rows)
    (out_dir/"experience_full.json").write_text(json.dumps(history,ensure_ascii=False,indent=2),encoding="utf-8")
    lines=["# Sổ tay rút kinh nghiệm – Bài 15.1","",
      "**Mô phỏng, không phải thực nghiệm. Bản KHBD Word gốc được bảo toàn.**",
      "**Lưu ý: điểm v2.0 legacy và v2.1 evidence_guard khác công thức, không so sánh trực tiếp.**","",
      "| Lần | Đạt cả 3/38 | Đạt ≥3/5 | GK1 | GK2 | GK3 | TB | Điều chỉnh cho lần sau |",
      "|---:|---:|---:|---:|---:|---:|---:|---|"]
    for x in history["sessions"]:
        met=x["lesson_metrics"];change=x["reflection"]["change_for_next_lesson"]
        lines.append(f"| {x['lesson']} | {met['all3']} | {met['basic']} | "+
             " | ".join(str(j["score_10"]) for j in x["judges"])+
             f" | {x['judge_mean']} | {change.get('action','none')} ({change['status']}) |")
    lines+=["","## Phân tích sau từng tiết",""]
    for x in history["sessions"]:
        ref=x["reflection"];change=ref["change_for_next_lesson"]
        lines+=[f"### Tiết {x['lesson']} – điểm TB {x['judge_mean']}/10 ({x.get('rubric_version','v2.0_legacy')})",
                "**Ưu điểm:** "+"; ".join(ref["strengths"]),"",
                "**Điểm cần khắc phục:** "+"; ".join(ref["weaknesses"]),"",
                "**Nhận xét từng giám khảo:**",""]
        lines+=["- "+v for v in ref["judge_feedback"]]
        lines+=["",f"**Đề xuất sau tiết:** {change.get('target_KHBD_section','—')}: {change.get('proposed_revision','Không có')}",
                f"**Quyết định:** {change['status']}; paired holdout gain = {change.get('paired_holdout_gain','—')}",
                ""]
    lines+=["## Nguyên tắc sử dụng","",
      "1. Những chỉnh sửa trên là **đề xuất bản KHBD tiếp theo**, không được tự ghi đè tệp DOCX gốc.",
      "2. Không làm thay đổi mục tiêu, bốn hoạt động và tổng thời lượng 45 phút.",
      "3. Thay đổi bị từ chối trong thử nghiệm đối chứng sẽ không áp dụng.",
      "4. Khi người dùng yêu cầu chỉnh KHBD, đọc lại sổ tay này, đối chiếu minh chứng và chỉ viết phần sửa được giải thích rõ.",
      "5. Không đồng nhất điểm mô phỏng với hiệu quả giảng dạy thực tế." ]
    (out_dir/"LESSON_REVIEW.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    amendments=["# Đề xuất chỉnh sửa KHBD 15.1 – sổ thay đổi","",
      "Tệp KHBD Word gốc là bản bất biến; mỗi đề xuất được truy vết về tiết và chỉ áp dụng trong mô phỏng nếu vượt qua kiểm tra đối chứng.",""]
    for x in history["sessions"]:
        c=x["reflection"]["change_for_next_lesson"]
        if c.get("status")=="trial_accepted":
            amendments += [f"## Sau tiết {x['lesson']}: {c.get('target_KHBD_section','')}",
               c.get("proposed_revision",""),
               f"Minh chứng: đạt đồng thời ba yêu cầu {x['lesson_metrics']['all3']}/38; GK1/GK2/GK3: "+", ".join(str(j['score_10']) for j in x["judges"]),
               f"Thử đối chứng theo cùng hồ sơ: chênh lệch chỉ số tổng hợp {c.get('paired_holdout_gain')}.",""]
    amendments += ["Không có thay đổi trực tiếp vào tài liệu KHBD đã tải lên; khi giáo viên yêu cầu chỉnh một mục, cần tạo bản sửa có lịch sử và so sánh với tài liệu gốc."]
    (out_dir/"KHBD15_CHANGELOG.md").write_text("\n".join(amendments)+"\n",encoding="utf-8")
    # Persist a compact human-readable index in git for future assistants/tools.
    index=out_dir.parent/"LATEST_LESSON_REVIEW.md"
    index.write_text("\n".join(lines)+"\n",encoding="utf-8")
    print(json.dumps({"lessons_total":len(history["sessions"]),
      "last":rows[-1],"policy_for_next":history["policy"],
      "state_file":str(state_path),"report":str(index)},ensure_ascii=False))
    return history

def self_test():
    zero={k:0 for k in LIMITS}
    a=simulate(151212,zero);b=simulate(151212,zero)
    assert strip_student(a)==strip_student(b)
    assert len(a["students"])==38 and len(grade(a))==3
    assert sum(SLOTS.values())==45
    assert all(0<=j["score_10"]<=10 for j in grade(a))
    assert all(len(p["answers"])==5 for p in a["students"])
    assert a["home_task_status"].startswith("assigned")
    newer=dict(zero);newer["ion_scaffold"]=1
    accepted,gain=paired_accept(zero,newer,1)
    assert isinstance(accepted,bool) and isinstance(gain,float)
    constrained=dict(zero)
    for k,cap in LIMITS.items():constrained[k]=cap
    constrained["scan_rehearsal"]=0
    assert propose(a,grade(a),constrained,{"scan_rehearsal"}) is None
    print("REFLECTION SELF-TEST PASSED")

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--lessons",type=int,default=5)
    parser.add_argument("--state",default="sim-experience/experience.json")
    parser.add_argument("--out",default="sim-experience/latest")
    parser.add_argument("--self-test",action="store_true")
    args=parser.parse_args()
    if args.self_test:self_test()
    if not 1<=args.lessons<=30:parser.error("lessons must be 1-30")
    run(Path(args.state),Path(args.out),args.lessons)
