import pytest

from apps.core.audit import AuditEvent, record

pytestmark = pytest.mark.django_db


def test_audit_event_is_append_only(org_a) -> None:  # type: ignore[no-untyped-def]
    ev = record(org_a.org, actor=org_a.user, entity=org_a, action="test", after={"x": 1})
    ev.action = "changed"
    with pytest.raises(ValueError, match="append-only"):
        ev.save()
    with pytest.raises(ValueError, match="append-only"):
        ev.delete()
    with pytest.raises(ValueError, match="append-only"):
        AuditEvent.objects.get(pk=ev.pk).delete()
    assert AuditEvent.objects.get(pk=ev.pk).action == "test"
