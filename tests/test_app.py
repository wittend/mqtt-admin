import re

import pytest
from fastapi.testclient import TestClient

from mqtt_admin.app import create_app
from mqtt_admin.config import Settings, _nets
from mqtt_admin.dynsec import DynSecError
from mqtt_admin.security import LoginLimiter, acl_problem, password_problem


class FakeDynSec:
    """Same surface as DynSec, backed by a dict."""

    def __init__(self):
        self.users = {
            "portal-svc": {"password": "svc", "roles": ["admin"]},
            "alice": {"password": "alice-old-password", "roles": ["portal-admin"]},
            "bob": {"password": "bob-old-password!", "roles": []},
        }
        self.roles = {
            "admin": {"acls": []},
            "portal-admin": {"acls": []},
            "sensor-publisher": {"acls": []},
        }
        self.default_acl = {"publishClientSend": False, "publishClientReceive": True,
                            "subscribe": False, "unsubscribe": True}

    def verify_login(self, u, p):
        return u in self.users and self.users[u]["password"] == p

    def get_client(self, u):
        c = self.users.get(u)
        return c and {"username": u, "roles": [{"rolename": r} for r in c["roles"]]}

    def list_clients(self):
        return [self.get_client(u) | {"textname": ""} for u in self.users]

    def list_roles(self):
        return list(self.roles)

    def get_role(self, r):
        role = self.roles.get(r)
        if role is None:
            return None
        return {"rolename": r, "acls": [dict(a) for a in role["acls"]]}

    def get_default_acl(self):
        return dict(self.default_acl)

    def create_role(self, r):
        if r in self.roles:
            raise DynSecError("Role already exists")
        self.roles[r] = {"acls": []}

    def delete_role(self, r):
        if r not in self.roles:
            raise DynSecError("Role not found")
        del self.roles[r]
        for u in self.users.values():
            if r in u["roles"]:
                u["roles"].remove(r)

    def add_role_acl(self, r, acltype, topic, allow, priority=0):
        acls = self.roles[r]["acls"]
        if any(a["acltype"] == acltype and a["topic"] == topic for a in acls):
            raise DynSecError("ACL already exists")
        acls.append({"acltype": acltype, "topic": topic, "allow": allow, "priority": priority})

    def remove_role_acl(self, r, acltype, topic):
        acls = self.roles[r]["acls"]
        before = len(acls)
        acls[:] = [a for a in acls if not (a["acltype"] == acltype and a["topic"] == topic)]
        if len(acls) == before:
            raise DynSecError("ACL not found")

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


def test_acl_rules_are_checked():
    ok = [
        ("publishClientSend", "hamsci/mag/TEST/data"),
        ("publishClientSend", "hamsci/mag/+/data"),
        ("subscribePattern", "hamsci/mag/#"),
        ("subscribeLiteral", "hamsci/mag/TEST/data/command"),
    ]
    bad = [
        ("nonsense", "a/b"),          # unknown rule type
        ("publishClientSend", ""),    # empty
        ("publishClientSend", "a b"), # space
        ("publishClientSend", "$CONTROL/dynamic-security/v1"),
        ("publishClientSend", "a/#/b"),   # # not last
        ("publishClientSend", "a/b#"),    # wildcard inside a level
        ("subscribeLiteral", "a/+/b"),    # literal rule with a wildcard
        ("subscribeLiteral", "a/#"),
    ]
    for acltype, topic in ok:
        assert acl_problem(acltype, topic) is None, (acltype, topic)
    for acltype, topic in bad:
        assert acl_problem(acltype, topic), (acltype, topic)


def test_admin_builds_a_role_with_rules(broker):
    c = admin_session(broker)
    t = csrf_of(c, "/admin")
    r = c.post("/admin/roles", data={"csrf": t, "rolename": "station-hamsci"})
    assert r.status_code == 303
    r = c.post("/admin/roles/station-hamsci/rules", data={
        "csrf": t, "acltype": "publishClientSend", "topic": "hamsci/mag/TEST/data", "allow": "1", "priority": "0"})
    assert r.status_code == 303
    r = c.post("/admin/roles/station-hamsci/rules", data={
        "csrf": t, "acltype": "subscribeLiteral", "topic": "hamsci/mag/TEST/data/command", "allow": "1"})
    assert r.status_code == 303
    assert broker.roles["station-hamsci"]["acls"] == [
        {"acltype": "publishClientSend", "topic": "hamsci/mag/TEST/data", "allow": True, "priority": 0},
        {"acltype": "subscribeLiteral", "topic": "hamsci/mag/TEST/data/command", "allow": True, "priority": 0},
    ]
    page = c.get("/admin").text
    assert "hamsci/mag/TEST/data" in page and "station-hamsci" in page


def test_bad_rule_is_refused_and_not_saved(broker):
    c = admin_session(broker)
    t = csrf_of(c, "/admin")
    c.post("/admin/roles", data={"csrf": t, "rolename": "station-hamsci"})
    r = c.post("/admin/roles/station-hamsci/rules", data={
        "csrf": t, "acltype": "subscribeLiteral", "topic": "a/+/b", "allow": "1"})
    assert r.status_code == 400
    assert broker.roles["station-hamsci"]["acls"] == []


def test_bad_role_inputs_are_refused(broker):
    c = admin_session(broker)
    t = csrf_of(c, "/admin")
    assert c.post("/admin/roles", data={"csrf": t, "rolename": "has space"}).status_code == 400
    assert c.post("/admin/roles", data={"csrf": t, "rolename": "sensor-publisher"}).status_code == 400
    assert c.post("/admin/roles/sensor-publisher/rules", data={
        "csrf": t, "acltype": "publishClientSend", "topic": "x", "allow": "maybe"}).status_code == 400
    assert c.post("/admin/roles/sensor-publisher/rules", data={
        "csrf": t, "acltype": "publishClientSend", "topic": "x", "allow": "1", "priority": "5000"}).status_code == 400
    assert c.post("/admin/roles/ghost/rules", data={
        "csrf": t, "acltype": "publishClientSend", "topic": "x", "allow": "1"}).status_code == 400


def test_builtin_roles_cannot_be_changed(broker):
    c = admin_session(broker)
    t = csrf_of(c, "/admin")
    for name in ("admin", "portal-admin"):
        assert c.post(f"/admin/roles/{name}/rules", data={
            "csrf": t, "acltype": "publishClientSend", "topic": "x", "allow": "1"}).status_code == 400
        assert c.post(f"/admin/roles/{name}/delete", data={"csrf": t}).status_code == 400
    assert "portal-admin" in broker.roles and "admin" in broker.roles


def test_removing_a_rule(broker):
    broker.roles["sensor-publisher"]["acls"].append(
        {"acltype": "publishClientSend", "topic": "hamsci/mag/x/data", "allow": True, "priority": 0})
    c = admin_session(broker)
    t = csrf_of(c, "/admin")
    c.post("/admin/roles/sensor-publisher/rules/remove", data={
        "csrf": t, "acltype": "publishClientSend", "topic": "hamsci/mag/x/data"})
    assert broker.roles["sensor-publisher"]["acls"] == []


def test_deleting_a_role_removes_it_from_accounts(broker):
    broker.users["bob"]["roles"].append("sensor-publisher")
    c = admin_session(broker)
    t = csrf_of(c, "/admin")
    r = c.post("/admin/roles/sensor-publisher/delete", data={"csrf": t})
    assert r.status_code == 303
    assert "sensor-publisher" not in broker.roles
    assert broker.users["bob"]["roles"] == []
    assert "removed from 1 account" in c.get("/admin").text


def test_role_forms_need_admin_and_csrf(broker):
    c = make_client(broker)
    assert c.post("/admin/roles", data={"csrf": "x", "rolename": "new"}).status_code == 401
    c = admin_session(broker)
    assert c.post("/admin/roles", data={"csrf": "forged", "rolename": "new"}).status_code == 403
    assert "new" not in broker.roles

