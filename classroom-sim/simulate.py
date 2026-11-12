#!/usr/bin/env python3
"""KHBD 15.1 classroom simulation: 38 synthetic pupils, scripted teacher, 3 rubric judges.
No external model calls, no personal data, no connection to game/Production.
The five Paper Mode questions are SKILL PROXIES; their original stems were absent in the supplied KHBD.
"""
import argparse
import csv
import json
import random
import statistics
from pathlib import Path

SKILLS = ("concept", "notation", "rules", "neutral", "ions", "application")
GROUPS = [("fast", 8), ("typical", 20), ("support", 10)]
BASE = {
    "fast":    (.74, .69, .70, .67, .57, .55),
    "typical": (.46, .42, .43, .39, .29, .25),
    "support": (.22, .19, .23, .18, .11, .10),
}
CORRECT = ("B", "C", "B", "A", "C")
QUESTION_SKILLS = ("concept", "notation", "neutral", "ions", "application")
STAGES = [
    {"name": "Mo dau", "start": 0, "minutes": 4},
    {"name": "Hinh thanh kien thuc", "start": 4, "minutes": 25},
    {"name": "Luyen tap", "start": 29, "minutes": 12},
    {"name": "Giao van dung va cung co", "start": 41, "minutes": 4},
]


def bounded(x):
    return max(0.02, min(0.98, x))


def succeeds(rng, mastery, effort=1.0):
    return rng.random() < bounded(.20 + .76 * mastery * effort)


def learn(pupil, key, gain):
    pupil["skills"][key] = bounded(pupil["skills"][key] + gain * (1 - pupil["skills"][key]))


def make_class(rng):
    pupils = []
    for group, n in GROUPS:
        for _ in range(n):
            sid = len(pupils) + 1
            skills = {key: bounded(base + rng.uniform(-.11, .11)) for key, base in zip(SKILLS, BASE[group])}
            pupils.append({
                "id": "HS%02d" % sid,
                "group": group,
                "skills": skills,
                "effort": bounded(rng.uniform(.80, 1.07)),
                "collaboration": bounded(rng.uniform(.42, .96) + (.08 if group == "fast" else 0)),
                "participation": False,
                "pht1": {},
                "pht2": {},
                "answers": [],
                "correct_count": 0,
                "requirements": {},
                "competencies": {},
                "qualities": {},
            })
    return pupils


def one_session(seed):
    rng = random.Random(seed)
    pupils = make_class(rng)
    events = []
    events.append({"minute": 0, "actor": "teacher", "action": "NaCl/H2O opening questions; 45s independent thinking"})
    for p in pupils:
        p["participation"] = succeeds(rng, p["skills"]["concept"], p["effort"])
        learn(p, "concept", .11 if p["participation"] else .05)

    events.append({"minute": 4, "actor": "teacher", "action": "PHT1: 2m individual + 2m pair; inquiry and peer correction"})
    seating = pupils[:]
    rng.shuffle(seating)
    for a, b in zip(seating[::2], seating[1::2]):
        support = .10 * ((a["collaboration"] + b["collaboration"]) / 2)
        for p in (a, b):
            learn(p, "concept", .21 + support)
            learn(p, "notation", .25 + support)
    for p in pupils:
        s = p["skills"]
        p["pht1"] = {
            "definition": succeeds(rng, s["concept"], p["effort"]),
            "h2_h2o": succeeds(rng, (s["concept"] + s["notation"]) / 2, p["effort"]),
            "representation": succeeds(rng, s["notation"], p["effort"]),
        }
        if not p["pht1"]["representation"]:
            learn(p, "notation", .13)   # teacher addresses sign/order confusion

    events.append({"minute": 13, "actor": "teacher", "action": "SO2 worked example; PHT2 Fe, H2SO4, SO4(2-), fast-finisher NH4(+)"})
    for p in pupils:
        learn(p, "rules", .35)
        learn(p, "neutral", .32)
        learn(p, "ions", .26)
        learn(p, "application", .16)
        s = p["skills"]
        p["pht2"] = {
            "Fe": succeeds(rng, s["rules"], p["effort"]),
            "H2SO4": succeeds(rng, (s["rules"] + s["neutral"]) / 2, p["effort"]),
            "SO4_2minus": succeeds(rng, (s["rules"] + s["ions"]) / 2, p["effort"]),
            "NH4_plus": succeeds(rng, (s["rules"] + s["ions"]) / 2, p["effort"]) if p["group"] == "fast" or rng.random() < .25 else None,
        }
        if not p["pht2"]["SO4_2minus"]:
            learn(p, "ions", .17)   # reasoning on total = ionic charge
        if not p["pht2"]["H2SO4"]:
            learn(p, "neutral", .09)
    events.append({"minute": 25, "actor": "student", "action": "Typical misconception: setting sum of oxidation numbers for SO4(2-) to zero; teacher elicits peer counterexample"})

    events.append({"minute": 29, "actor": "teacher", "action": "Wayground Paper Mode: 5 skill-proxy items; display, scan, discuss wrong answers"})
    for p in pupils:
        for idx, key in enumerate(QUESTION_SKILLS):
            correct = succeeds(rng, p["skills"][key], p["effort"])
            answer = CORRECT[idx] if correct else rng.choice([x for x in "ABCD" if x != CORRECT[idx]])
            p["answers"].append(answer)
        p["correct_count"] = sum(a == b for a, b in zip(p["answers"], CORRECT))
    for p in pupils:
        if p["answers"][3] != CORRECT[3]:
            learn(p, "ions", .15)   # teacher feedback after item 4
    events.append({"minute": 41, "actor": "teacher", "action": "Assign H2O2 home transfer sheet; collect NEXT lesson; recap and dismiss at minute 45"})
    events.append({"minute": 45, "actor": "system", "action": "Lesson ended; H2O2 home assignment not scored"})

    for p in pupils:
        q = [a == b for a, b in zip(p["answers"], CORRECT)]
        h1, h2 = p["pht1"], p["pht2"]
        # Evidence-based indicators; simulation thresholds are not national grading standards.
        p["requirements"] = {
            "K1_concept_notation": (h1["definition"] and h1["representation"]) or (q[0] and q[1]),
            "K2_four_rules": h2["Fe"] and (h2["H2SO4"] or q[2]),
            "K3_apply_substance_molecule_ion": h2["H2SO4"] and h2["SO4_2minus"] and (q[3] or q[4]),
        }
        p["competencies"] = {
            "self_learning": p["effort"] >= .88 and sum(h1.values()) >= 1,
            "collaboration": p["collaboration"] >= .58 and p["participation"],
            "chemical_recognition": p["requirements"]["K1_concept_notation"],
            "application": p["requirements"]["K3_apply_substance_molecule_ion"],
            "problem_solving": (h2["H2SO4"] and h2["SO4_2minus"]) or p["correct_count"] >= 4,
        }
        p["qualities"] = {
            "diligence": p["effort"] >= .87,
            "honesty": rng.random() < bounded(.70 + .20 * p["effort"]),
            "responsibility": p["collaboration"] >= .58,
        }

    req_keys = tuple(pupils[0]["requirements"])
    comp_keys = tuple(pupils[0]["competencies"])
    qual_keys = tuple(pupils[0]["qualities"])
    counts = {
        "requirements": {k: sum(p["requirements"][k] for p in pupils) for k in req_keys},
        "competencies": {k: sum(p["competencies"][k] for p in pupils) for k in comp_keys},
        "qualities": {k: sum(p["qualities"][k] for p in pupils) for k in qual_keys},
    }
    all_three = sum(all(p["requirements"].values()) for p in pupils)
    basic = sum(p["correct_count"] >= 3 for p in pupils)
    strong = sum(p["correct_count"] >= 4 for p in pupils)
    questions = [sum(p["answers"][i] == CORRECT[i] for p in pupils) for i in range(5)]
    engagement = sum(p["participation"] for p in pupils) / 38
    # Three separate rubric-based perspectives, not independent model judgments.
    judge_scores = {
        "judge1_subject": round(min(10, 6.1 + 2.0 * counts["requirements"]["K1_concept_notation"] / 38 + 1.7 * counts["requirements"]["K2_four_rules"] / 38), 2),
        "judge2_pedagogy": round(min(10, 5.5 + 2.5 * engagement + 1.7 * counts["competencies"]["collaboration"] / 38), 2),
        "judge3_assessment": round(min(10, 5.5 + 2.0 * counts["requirements"]["K3_apply_substance_molecule_ion"] / 38 + 1.2 * basic / 38), 2),
    }
    return {
        "seed": seed, "pupils": pupils, "events": events, "questions_correct": questions,
        "requirements": counts["requirements"], "competencies": counts["competencies"],
        "qualities": counts["qualities"], "all_three": all_three,
        "basic_3plus": basic, "strong_4plus": strong,
        "question_accuracy": round(sum(questions) / 190, 5),
        "judges": judge_scores, "minutes": 45,
        "home_task_assessed": False,
    }


def csv_write(path, rows):
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def export(root, sessions):
    root.mkdir(parents=True, exist_ok=True)
    first = sessions[0]
    student_rows = []
    run_rows = []
    for i, s in enumerate(sessions, 1):
        for p in s["pupils"]:
            student_rows.append({
                "run": i, "student": p["id"], "baseline_group": p["group"],
                "pht1_correct": sum(p["pht1"].values()),
                "pht2_correct": sum(v is True for v in p["pht2"].values()),
                "paper_answers": "".join(p["answers"]), "paper_correct": p["correct_count"],
                **{k: int(v) for k, v in p["requirements"].items()},
                **{k: int(v) for k, v in p["competencies"].items()},
                **{k: int(v) for k, v in p["qualities"].items()},
            })
        run_rows.append({
            "run": i, "seed": s["seed"], "basic_3plus": s["basic_3plus"], "strong_4plus": s["strong_4plus"],
            "all_three_knowledge": s["all_three"], "question_accuracy": s["question_accuracy"],
            **s["requirements"], **s["judges"],
        })
    csv_write(root / "students_all_runs.csv", student_rows)
    csv_write(root / "runs.csv", run_rows)
    (root / "events_first_run.json").write_text(json.dumps(first["events"], ensure_ascii=False, indent=2), encoding="utf-8")
    k = ["basic_3plus", "strong_4plus", "all_three", "question_accuracy"]
    aggregate = {x: {"mean": round(statistics.mean(s[x] for s in sessions), 3),
                     "min": min(s[x] for s in sessions), "max": max(s[x] for s in sessions)}
                 for x in k}
    for x in first["requirements"]:
        aggregate[x] = {"mean": round(statistics.mean(s["requirements"][x] for s in sessions), 3),
                        "min": min(s["requirements"][x] for s in sessions),
                        "max": max(s["requirements"][x] for s in sessions)}
    report = {
        "status": "SIMULATED_NOT_OBSERVED", "lesson": "KHBD Bài 15, tiết 1 - Số oxi hóa",
        "duration_minutes": 45, "class_size": 38, "judge_count": 3,
        "runs": len(sessions), "seed_start": first["seed"], "base_profile": dict(GROUPS),
        "method": "Rule-based probabilistic agents; no LLM API calls, no real pupil data",
        "question_limitation": "Source did not include 5 full question stems; items model associated skills and prescribed answer key only",
        "after_class_H2O2": "Assigned at minute 41; cannot evaluate until next lesson",
        "aggregate": aggregate, "first_run": {
            "questions_correct": first["questions_correct"],
            "requirements": first["requirements"], "competencies": first["competencies"],
            "qualities": first["qualities"], "judges": first["judges"],
            "basic_3plus": first["basic_3plus"], "strong_4plus": first["strong_4plus"],
            "all_three": first["all_three"], "question_accuracy": first["question_accuracy"],
        },
    }
    (root / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        "# KHBD 15.1 – Classroom headless simulation", "",
        "38 synthetic students | 1 scripted teacher | 3 rubric judges | 45 minutes | %d runs" % len(sessions), "",
        "**This is synthetic simulation data, not a real classroom measurement or a validated prediction.**", "",
        "## First run", "",
        "| Indicator | Students / metric |", "|---|---:|",
        "| At least 3/5 paper items | %d/38 |" % first["basic_3plus"],
        "| At least 4/5 paper items | %d/38 |" % first["strong_4plus"],
        "| Meets all 3 knowledge requirements | %d/38 |" % first["all_three"],
    ]
    for key, n in first["requirements"].items():
        lines.append("| %s | %d/38 |" % (key, n))
    lines += ["", "## Across runs", "",
              "| Indicator | Mean | Min | Max |", "|---|---:|---:|---:|"]
    for key, stat in aggregate.items():
        lines.append("| %s | %s | %s | %s |" % (key, stat["mean"], stat["min"], stat["max"]))
    lines += ["", "## First-run rubric judges", ""]
    for key, score in first["judges"].items():
        lines.append("- %s: %s/10" % (key, score))
    lines += ["", "## Limits", "",
              "- Home H2O2 transfer task is not marked until the following lesson.",
              "- Question 1–5 full stems are absent from the attached KHBD and are therefore modeled by skill proxies.",
              "- This engine uses rules and seeded chance, not 42 LLMs; outcomes depend on assumptions and are not empirical evidence."]
    (root / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"runs": len(sessions), "first_run": report["first_run"],
                      "aggregate": aggregate, "output": str(root)}, ensure_ascii=False))


def self_test():
    a = one_session(151001)
    b = one_session(151001)
    assert a["questions_correct"] == b["questions_correct"]
    assert a["all_three"] == b["all_three"]
    assert len(a["pupils"]) == 38
    assert len(a["judges"]) == 3
    assert sum(s["minutes"] for s in STAGES) == 45
    assert all(len(p["answers"]) == 5 for p in a["pupils"])
    assert all(not p.get("home_task_assessed", False) for p in a["pupils"])
    assert a["home_task_assessed"] is False
    print("SELF-TEST PASSED")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=10)
    parser.add_argument("--seed", type=int, default=151001)
    parser.add_argument("--out", default="results")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
    if not (1 <= args.runs <= 1000):
        parser.error("--runs must be between 1 and 1000")
    export(Path(args.out), [one_session(args.seed + i) for i in range(args.runs)])
