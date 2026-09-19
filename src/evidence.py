from datetime import timedelta
from collections import Counter


class EvidenceExtractor:

    def __init__(self, state):
        self.state = state
        self.events = state.all_events

    def extract(self):

        evidence = {
            "financial": [],
            "support": [],
            "usage": [],
            "profile": [],
            "life_event_keywords": [],
            "temporal_patterns": []
        }

        for event in self.events:

            # all_Events stores Event Objects
            source = event.source_system
            event_type = event.event_type
            payload = event.payload

            # -----------------------------
            # TRANSACTION EVIDENCE
            # -----------------------------
            if source in {
                "card_payments",
                "instant_payments",
                "ach_wire",
                "core_banking_ledger",
                "trading_brokerage"
            }:

                merchant = str(
                    payload.get("merchant_name", "")
                ).lower()

                counterparty = str(
                    payload.get("counterparty_name", "")
                ).lower()

                transaction_type = str(
                    payload.get("transaction_type", "")
                ).lower()

                text = " ".join([
                    merchant,
                    counterparty,
                    transaction_type
                ])

                for keyword in [
                    "hospital",
                    "medical",
                    "pharmacy",
                    "clinic",
                    "doctor",
                    "health"
                ]:
                    if keyword in text:
                        evidence["life_event_keywords"].append(
                            f"Medical transaction keyword: {keyword}"
                        )

                if event_type in {
                    "withdrawal",
                    "outbound_transfer"
                }:
                    evidence["financial"].append(
                        f"{event_type}: "
                        f"{payload.get('amount')}"
                    )

            # -----------------------------
            # SUPPORT EVIDENCE
            # -----------------------------
            if source == "support_logs":

                raw_text = str(
                    payload.get("raw_text", "")
                ).lower()

                if raw_text:
                    evidence["support"].append(
                        raw_text[:300]
                    )

                for keyword in [
                    "medical",
                    "hospital",
                    "income",
                    "hardship",
                    "bill",
                    "financial",
                    "payment"
                ]:
                    if keyword in raw_text:
                        evidence["life_event_keywords"].append(
                            f"Support keyword: {keyword}"
                        )

            # -----------------------------
            # WEB / USAGE EVIDENCE
            # -----------------------------
            if source == "web_app_events":

                search_text = str(
                    payload.get("search_text", "")
                ).lower()

                if search_text:

                    evidence["usage"].append(
                        f"Search: {search_text}"
                    )

                    for keyword in [
                        "medical",
                        "hospital",
                        "hardship",
                        "loan",
                        "income",
                        "insurance",
                        "baby",
                        "daycare",
                        "education",
                        "competitor",
                        "transfer",
                        "close account"
                    ]:
                        if keyword in search_text:
                            evidence["life_event_keywords"].append(
                                f"Search keyword: {keyword}"
                            )

            # -----------------------------
            # KYC / PROFILE EVIDENCE
            # -----------------------------
            if source == "loan_kyc":

                old_value = payload.get("old_value")
                new_value = payload.get("new_value")

                if old_value is not None or new_value is not None:

                    evidence["profile"].append(
                        f"{event_type}: "
                        f"{old_value} -> {new_value}"
                    )

        return evidence