from datetime import datetime, timezone
from pathlib import Path
import json, math, re, hashlib
from typing import Any


class LocalVectorIndex:
    """Small dependency-free semantic index for the prototype.
    It keeps embeddings alongside the source records and updates incrementally.
    """
    DIM = 128

    @classmethod
    def embed(cls, text: str) -> list[float]:
        vec = [0.0] * cls.DIM
        tokens = re.findall(r"[a-z0-9_]+", text.lower())
        for token in tokens:
            h = int(hashlib.sha256(token.encode()).hexdigest()[:8], 16)
            vec[h % cls.DIM] += 1.0
        norm = math.sqrt(sum(x*x for x in vec)) or 1.0
        return [x / norm for x in vec]

    @staticmethod
    def cosine(a: list[float], b: list[float]) -> float:
        return sum(x*y for x, y in zip(a, b))


class CustomerMemory:
    """Three-layer Customer 360 memory: working, episodic and semantic."""
    def __init__(self, customer_id: str, root: str = "memory"):
        self.customer_id = customer_id
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.episodic_path = self.root / f"{customer_id}_episodic.jsonl"
        self.semantic_path = self.root / "semantic_policy.json"
        self.index_path = self.root / f"{customer_id}_episodic.index.jsonl"

    def _read_jsonl(self, path: Path) -> list[dict[str, Any]]:
        if not path.exists(): return []
        out=[]
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                if line.strip(): out.append(json.loads(line))
        return out

    def retrieve_episodic(self, query: str = "", limit: int = 5) -> list[dict[str, Any]]:
        rows = self._read_jsonl(self.episodic_path)
        if not rows: return []
        q = LocalVectorIndex.embed(query or self.customer_id)
        scored=[]
        for row in rows:
            emb = row.get("embedding") or LocalVectorIndex.embed(json.dumps(row, sort_keys=True))
            scored.append((LocalVectorIndex.cosine(q, emb), row))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [{**row, "retrieval_score": round(score, 4)} for score, row in scored[:limit]]

    def write_episode(self, inferred_state: str, action: str, confidence: float,
                      evidence: list[str], event_ids: list[str] | None = None,
                      outcome: str | None = None) -> None:
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "customer_id": self.customer_id,
            "inferred_state": inferred_state,
            "action": action,
            "confidence": confidence,
            "evidence": evidence[:10],
            "event_ids": (event_ids or [])[:20],
            "outcome": outcome,
        }
        record["embedding"] = LocalVectorIndex.embed(json.dumps(record, sort_keys=True))
        with self.episodic_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
        with self.index_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"timestamp": record["timestamp"], "state": inferred_state,
                                "action": action, "embedding": record["embedding"]}) + "\n")

    def retrieve_semantic(self, query: str = "") -> dict[str, Any]:
        if not self.semantic_path.exists(): return {"description":"Shared policy memory", "rules":[]}
        with self.semantic_path.open("r", encoding="utf-8") as f: policy=json.load(f)
        if query and policy.get("rules"):
            q=LocalVectorIndex.embed(query)
            rules=[]
            for rule in policy["rules"]:
                score=LocalVectorIndex.cosine(q, LocalVectorIndex.embed(json.dumps(rule, sort_keys=True)))
                rules.append((score, rule))
            policy=dict(policy)
            policy["rules"]=[r for _,r in sorted(rules,key=lambda x:x[0],reverse=True)]
        return policy

    def seed_semantic_policy(self) -> None:
        if self.semantic_path.exists(): return
        policy={"description":"Shared policy memory for Customer 360 prototype","rules":[
            {"state":"medical_hardship","action":"support_intervention","action_subtype":"medical_hardship_payment_plan","human_review":True},
            {"state":"new_child_life_event","action":"personalized_offer","action_subtype":"childcare_savings_or_insurance_plan","human_review":True},
            {"state":"churn_risk","action":"proactive_retention_outreach","human_review":False},
            {"state":"potential_fraud_or_takeover","action":"compliance_fraud_hold","human_review":True},
        ]}
        with self.semantic_path.open("w", encoding="utf-8") as f: json.dump(policy,f,indent=2)
