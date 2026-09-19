"""Data-layer style access control and PII masking for the prototype."""
import re
AGENT_SOURCES={
 "usage_agent":{"web_app_events"},
 "support_agent":{"support_logs"},
 "transaction_agent":{"card_payments","instant_payments","ach_wire","core_banking_ledger","trading_brokerage"},
 "kyc_compliance_agent":{"loan_kyc"},
}
def authorize(agent_name,source_system): return source_system in AGENT_SOURCES.get(agent_name,set())
def mask_pii(value):
    text=str(value)
    text=re.sub(r"\b\d{10,19}\b","[REDACTED_ID]",text)
    text=re.sub(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b","[REDACTED_EMAIL]",text,flags=re.I)
    return text
