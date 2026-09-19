"""Deterministic specialist tool layer used by the Customer 360 agents."""
from datetime import timedelta

def windowed_usage(events, days=14):
    if not events: return {"count":0,"logins":0,"searches":0,"features":0,"sessions":0}
    latest=max(e.event_time for e in events); cutoff=latest-timedelta(days=days); w=[e for e in events if e.event_time>=cutoff]
    return {"count":len(w),"logins":sum(e.event_type=="login" for e in w),"searches":sum(e.event_type=="search_query" for e in w),"features":sum(e.event_type=="feature_used" for e in w),"sessions":sum(e.event_type=="session_duration" for e in w)}

def support_ticket_retrieval(events):
    return [e for e in events if e.event_type in {"ticket_created","ticket_resolved","call_transcript"}]

def sentiment_score(text):
    negative={"angry","furious","terrible","urgent","problem","issue","charged","denied","cannot","unable","lawsuit","attorney"}
    words=str(text).lower().split(); return round(sum(w.strip(".,!?;:") in negative for w in words)/max(1,len(words)),3)

def transaction_baseline(events):
    amounts=[float(e.payload.get("amount",0)) for e in events if isinstance(e.payload.get("amount"),(int,float))]
    return {"count":len(events),"total":sum(amounts),"average":sum(amounts)/len(amounts) if amounts else 0.0}

def kyc_lookup(events): return [e for e in events if e.source_system=="loan_kyc"]
