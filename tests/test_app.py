import re

import pytest
from fastapi.testclient import TestClient

from mqtt_admin.app import create_app
from mqtt_admin.config import Settings, _nets
from mqtt_admin.dynsec import DynSecError
from mqtt_admin.security import LoginLimiter, password_problem


class FakeDynSec:
    """Same surface as DynSec, backed by a dict."""

    def __init__(self):
        self.users = {
            "portal-svc": {"password": "svc", "roles": ["admin"]},
            "alice": {"password": "alice-old-password", "roles": ["portal-admin"]},
            "bob": {"password": "bob-old-password!", "roles": []},
        }

    def verify_login(self, u, p):
        return u in self.users and self.users[u]["password"] == p

    def get_client(self, u):
        c = self.users.get(u)
        return c and {"username": u, "roles": [{"rolename": r} for r in c["roles"]]}

    def list_clients(self):
        return [self.get_client(u) | {"textname": ""} for u in self.users]

    def list_roles(self):
        return ["admin", "portal-admin", "sensor-publisher"]

    def create_client(self, u, p, roles=(), textname=""):
        if u in self.users:
            raise DynSecError("Client already exists")
        self.users[u] = {"password": p, "roles": list(roles)}

    def delete_client(self, u):
        del self.users[u]

    def set_password(self, u, p):
        self.users[u]["password"] = p

    def set_enabled(self, u, enabled):
        pass

    def add_role(self, u, r):
        self.users[u]["roles"].append(r)

    def remove_role(self, u, r):
        self.users[u]["roles"].remove(r)


@pytest.fixture
def broker():
    return FakeDynSec()


def make_client(broker, ip="192.0.2.5"):
    settings = Settings(svc_password="x", session_secret="s" * 40, secure_cookies=False,
                        admin_nets=_nets("192.0.2.0/24,127.0.0.1/32"))
    return TestClient(create_app(settings, broker), client=(ip, 5000), follow_redirects=False)


def csrf_of(client, path):
    return re.search(r'name="csrf" value="([^"]+)"', client.get(path).text).group(1)


def login(client, path, user, pw):
    return client.post(path, data={"username": user, "password": pw})


# --- policy ---------------------------------------------------------------
def test_password_policy():
    assert password_problem("short", "bob", 12)
    assert password_problem("bobbobbobbobbob1", "bob", 12)
    assert password_problem("aaaaaaaaaaaaaaaa", "bob", 12)
    assert password_problem("correct horse battery", "bob", 12) is None


def test_limiter_blocks_then_recovers():
    now = [0.0]
    lim = LoginLimiter(per_user=3, window=60, clock=lambda: now[0])
    for _ in range(3):
        lim.fail("1.1.1.1", "bob")
    assert lim.blocked("1.1.1.1", "bob")
    assert not lim.blocked("2.2.2.2", "bob")
    now[0] = 61
    assert not lim.blocked("1.1.1.1", "bob")


# --- self-service ---------------------------------------------------------
def test_user_changes_own_password(broker):
    c = make_client(broker)
    assert login(c, "/account/login", "bob", "bob-old-password!").status_code == 303
    r = c.post("/account/password", data={
        "csrf": csrf_of(c, "/account"), "current": "bob-old-password!",
        "new": "a much better passphrase", "confirm": "a much better passphrase"})
    assert r.status_code == 200 and "Password changed" in r.text
    assert broker.users["bob"]["password"] == "a much better passphrase"


def test_wrong_current_password_changes_nothing(broker):
    c = make_client(broker)
    login(c, "/account/login", "bob", "bob-old-password!")
    r = c.post("/account/password", data={
        "csrf": csrf_of(c, "/account"), "current": "nope",
        "new": "a much better passphrase", "confirm": "a much better passphrase"})
    assert r.status_code == 400
    assert broker.users["bob"]["password"] == "bob-old-password!"


def test_password_change_needs_csrf_token(broker):
    c = make_client(broker)
    login(c, "/account/login", "bob", "bob-old-password!")
    r = c.post("/account/password", data={"csrf": "forged", "current": "bob-old-password!",
                                          "new": "a much better passphrase", "confirm": "a much better passphrase"})
    assert r.status_code == 403


def test_login_locks_out_after_repeated_failures(broker):
    c = make_client(broker)
    for _ in range(5):
        assert login(c, "/account/login", "bob", "wrong").status_code == 401
    r = login(c, "/account/login", "bob", "bob-old-password!")
    assert "Too many failed attempts" in r.text


def test_plain_user_cannot_use_admin_login(broker):
    c = make_client(broker)
    assert login(c, "/admin/login", "bob", "bob-old-password!").status_code == 401


# --- admin ----------------------------------------------------------------
def admin_session(broker):
    c = make_client(broker)
    assert login(c, "/admin/login", "alice", "alice-old-password").status_code == 303
    return c


def test_admin_network_restriction(broker):
    c = make_client(broker, ip="8.8.8.8")
    assert c.get("/admin/login").status_code == 404
    assert login(c, "/admin/login", "alice", "alice-old-password").status_code == 404


def test_admin_creates_resets_and_deletes(broker):
    c = admin_session(broker)
    t = csrf_of(c, "/admin")
    c.post("/admin/users", data={"csrf": t, "username": "carol", "password": "first long passphrase",
                                 "roles": ["sensor-publisher"]})
    assert broker.users["carol"]["roles"] == ["sensor-publisher"]
    c.post("/admin/users/carol/password", data={"csrf": t, "password": "second long passphrase"})
    assert broker.users["carol"]["password"] == "second long passphrase"
    c.post("/admin/users/carol/delete", data={"csrf": t})
    assert "carol" not in broker.users


def test_admin_cannot_touch_service_account_or_self(broker):
    c = admin_session(broker)
    t = csrf_of(c, "/admin")
    assert c.post("/admin/users/portal-svc/delete", data={"csrf": t}).status_code == 400
    assert c.post("/admin/users/alice/delete", data={"csrf": t}).status_code == 400
    assert c.post("/admin/users/alice/roles", data={"csrf": t}).status_code == 400
    assert {"portal-svc", "alice"} <= broker.users.keys()


def test_revoked_admin_is_locked_out_immediately(broker):
    c = admin_session(broker)
    broker.users["alice"]["roles"].remove("portal-admin")
    assert c.get("/admin").status_code == 303
