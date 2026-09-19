from models import Event


class TriggerRouter:

    SOURCE_TO_AGENT = {
        "web_app_events": "usage_agent",
        "support_logs": "support_agent",

        "card_payments": "transaction_agent",
        "instant_payments": "transaction_agent",
        "ach_wire": "transaction_agent",
        "core_banking_ledger": "transaction_agent",
        "trading_brokerage": "transaction_agent",

        "loan_kyc": "kyc_compliance_agent",

        # This is an input to life-event inference,
        # not a separate social agent.
        "social_signal_consented": "life_event_input",
    }

    def route(self, event: Event):

        agent = self.SOURCE_TO_AGENT.get(
            event.source_system,
            "unknown"
        )

        return {
            "event_id": event.event_id,
            "customer_id": event.customer_id,
            "source_system": event.source_system,
            "event_type": event.event_type,
            "target": agent,
        }