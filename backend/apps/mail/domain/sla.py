"""SLA deadline for a thread. PROJECT_SPECS §6.2 sla_due_at: last inbound + 24h; urgent 4h."""

from datetime import datetime, timedelta

URGENT = "urgent"
SLA_HOURS_DEFAULT = 24
SLA_HOURS_URGENT = 4


def sla_due(last_inbound_at: datetime, priority: str) -> datetime:
    hours = SLA_HOURS_URGENT if priority == URGENT else SLA_HOURS_DEFAULT
    return last_inbound_at + timedelta(hours=hours)
