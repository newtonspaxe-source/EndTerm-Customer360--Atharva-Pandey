from datetime import datetime, timedelta
from models import Event

class EventStream:
    """Event-time aware ingestion: deduplication + lateness/watermark metadata."""
    def __init__(self, allowed_lateness_minutes: int = 30):
        self.seen_event_ids=set(); self.max_event_time: datetime|None=None
        self.watermark: datetime|None=None
        self.allowed_lateness=timedelta(minutes=allowed_lateness_minutes)

    def process(self,event: Event):
        if event.event_id in self.seen_event_ids:
            return {"status":"duplicate","event":event,"is_late":False,"watermark":self.watermark}
        self.seen_event_ids.add(event.event_id)
        is_late=self.max_event_time is not None and event.event_time < self.max_event_time
        if self.max_event_time is None or event.event_time > self.max_event_time:
            self.max_event_time=event.event_time
        self.watermark=self.max_event_time-self.allowed_lateness
        return {"status":"accepted","event":event,"is_late":is_late,"watermark":self.watermark,
                "within_allowed_lateness": self.watermark is None or event.event_time >= self.watermark}
