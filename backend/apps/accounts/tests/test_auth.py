import pytest
from django.test import Client
from rest_framework.test import APIClient

from apps.accounts.factories import MembershipFactory, UserFactory

pytestmark = pytest.mark.django_db


def test_login_logout_me() -> None:
    m = MembershipFactory()
    c = APIClient()
    assert c.get("/api/auth/me").status_code == 403
    r = c.post("/api/auth/login", {"email": m.user.email, "password": "pw"}, format="json")
    assert r.status_code == 200
    me = c.get("/api/auth/me").json()
    assert me["user"]["email"] == m.user.email
    assert me["org"]["id"] == str(m.org_id)
    assert me["role"] == "owner"
    assert c.post("/api/auth/logout").status_code == 204
    assert c.get("/api/auth/me").status_code == 403


def test_bad_password_is_400_problem() -> None:
    u = UserFactory()
    r = APIClient().post("/api/auth/login", {"email": u.email, "password": "x"}, format="json")
    assert r.status_code == 400
    assert r.json()["status"] == 400


def test_csrf_rejected_when_cookie_missing() -> None:
    u = UserFactory()
    c = Client(enforce_csrf_checks=True)
    r = c.post(
        "/api/auth/login",
        {"email": u.email, "password": "pw"},
        content_type="application/json",
    )
    assert r.status_code == 403


def test_csrf_accepted_with_cookie_and_header() -> None:
    m = MembershipFactory()
    c = Client(enforce_csrf_checks=True)
    c.get("/api/auth/me")  # 403 but ensure_csrf_cookie still sets the cookie
    token = c.cookies["csrftoken"].value
    r = c.post(
        "/api/auth/login",
        {"email": m.user.email, "password": "pw"},
        content_type="application/json",
        HTTP_X_CSRFTOKEN=token,
    )
    assert r.status_code == 200


def test_session_expiry(settings) -> None:  # type: ignore[no-untyped-def]
    m = MembershipFactory()
    c = APIClient()
    c.post("/api/auth/login", {"email": m.user.email, "password": "pw"}, format="json")
    session = c.session
    session.set_expiry(-1)
    session.save()
    assert c.get("/api/auth/me").status_code == 403


def test_cookie_flags(settings) -> None:  # type: ignore[no-untyped-def]
    assert settings.SESSION_COOKIE_HTTPONLY is True
    assert settings.SESSION_COOKIE_SAMESITE == "Lax"
