# recommender.py
from math import isfinite

DEFAULT_TARGET = 60.0

SAMPLE_RESOURCES = {
    "CO1": [
        {"title":"CO1 Basics - Video Playlist","type":"video","url":"https://www.youtube.com/watch?v=dQw4w9WgXcQ","notes":"Watch basics first (30-40 min)"},
        {"title":"CO1 Practice Sheet","type":"pdf","url":"https://example.com/co1-practice.pdf","notes":"Solve 10 problems"},
    ],
    "CO2": [
        {"title":"CO2 Lecture Notes","type":"text","url":"https://example.com/co2notes","notes":"Read and summarize"},
    ],
    "CO3": [
        {"title":"CO3 Mini Project","type":"text","url":"https://example.com/co3project","notes":"Implement small project"},
    ]
}

def percent(obt, mx):
    return (obt / mx * 100.0) if mx and isfinite(mx) and mx>0 else 0.0

def analyze_co(i1_pct, i2_pct, target=DEFAULT_TARGET):
    avg = (i1_pct + i2_pct)/2.0
    gap = round(max(0, target - avg),2)
    if gap <= 0:
        severity="no_gap"
    elif gap <= 10:
        severity="low"
    elif gap <= 25:
        severity="medium"
    else:
        severity="high"
    return {"avg": round(avg,2), "gap": gap, "severity":severity}

def generate_learning_plan(co_key, severity):
    plan = []
    if severity=="no_gap":
        plan.append("Maintain performance: weekly revision + advanced problems.")
        plan.append("Suggested: timed quizzes & peer teaching.")
    elif severity=="low":
        plan.append("2-week focused revision: small practice sets + revision notes.")
        plan.append("Suggested: 3 short quizzes and 2 revision sessions.")
    elif severity=="medium":
        plan.append("3–4 week plan: strengthen fundamentals + guided practice.")
        plan.append("Suggested: weekly quiz, extra practice assignments, 1 mini-project.")
    else:
        plan.append("Intensive 4+ week plan: re-learn basics, daily practice, mentor sessions.")
        plan.append("Suggested: daily homework, weekly tests, mini-project.")
    resources = SAMPLE_RESOURCES.get(co_key, [])
    return {"plan":plan, "resources":resources}

def analyze_marks_dict(marks_row):
    i1_c1 = percent(marks_row.get("i1_co1_obt",0), marks_row.get("i1_co1_max",1))
    i2_c1 = percent(marks_row.get("i2_co1_obt",0), marks_row.get("i2_co1_max",1))
    i1_c2 = percent(marks_row.get("i1_co2_obt",0), marks_row.get("i1_co2_max",1))
    i2_c2 = percent(marks_row.get("i2_co2_obt",0), marks_row.get("i2_co2_max",1))
    i1_c3 = percent(marks_row.get("i1_co3_obt",0), marks_row.get("i1_co3_max",1))
    i2_c3 = percent(marks_row.get("i2_co3_obt",0), marks_row.get("i2_co3_max",1))
    c1 = analyze_co(i1_c1, i2_c1)
    c2 = analyze_co(i1_c2, i2_c2)
    c3 = analyze_co(i1_c3, i2_c3)
    return {"CO1":c1,"CO2":c2,"CO3":c3}
