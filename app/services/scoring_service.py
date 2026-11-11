from collections import defaultdict
DIMENSIONS=("sanguine","choleric","melancholic","phlegmatic")
SCORING_VERSION="provisional-0.1.0"
def calculate_temperament_scores(questions,responses):
    response_map={r.question_id:r.raw_value for r in responses}
    totals,weights=defaultdict(float),defaultdict(float)
    for q in questions:
        if q.dimension not in DIMENSIONS or q.id not in response_map:continue
        x=response_map[q.id]
        if q.reverse_scored:x=6-x
        w=float(q.weight or 1.0)
        totals[q.dimension]+=x*w;weights[q.dimension]+=w
    result={}
    for d in DIMENSIONS:
        if not weights[d]:result[d]=None;continue
        mean=totals[d]/weights[d]
        result[d]={"raw_mean":round(mean,2),"normalized_score":round((mean-1)/4*100,1)}
    return result
def describe_score(score):
    if score is None:return "Insufficient responses."
    if score>=70:return "More frequently endorsed in this questionnaire; treat as a reflective tendency."
    if score>=40:return "Moderately endorsed; context may influence this tendency."
    return "Less frequently endorsed; this does not mean the tendency is absent."
