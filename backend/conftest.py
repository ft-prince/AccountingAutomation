import pytest
from rest_framework.test import APIClient

from apps.accounts.factories import MembershipFactory
from apps.accounts.models import Role


@pytest.fixture
def db_ready(db: None) -> None:
    """Alias for pytest-django's `db`; later phases extend this with seed data."""


@pytest.fixture
def org_a(db):  # type: ignore[no-untyped-def]
    return MembershipFactory(role=Role.OWNER)


@pytest.fixture
def org_b(db):  # type: ignore[no-untyped-def]
    return MembershipFactory(role=Role.OWNER)


def client_for(membership) -> APIClient:  # type: ignore[no-untyped-def]
    c = APIClient()
    c.force_login(membership.user)
    return c


@pytest.fixture
def client_a(org_a):  # type: ignore[no-untyped-def]
    return client_for(org_a)


@pytest.fixture
def client_b(org_b):  # type: ignore[no-untyped-def]
    return client_for(org_b)


@pytest.fixture
def viewer_client(org_a):  # type: ignore[no-untyped-def]
    m = MembershipFactory(org=org_a.org, role=Role.VIEWER)
    return client_for(m)
