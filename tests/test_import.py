import pytest

from mqtt_admin.importer import MAX_BYTES, MAX_ROWS, parse_users_csv
from test_app import csrf_of, broker, make_client, login  # noqa: F401  (fixtures and helpers)

ROLES = {"admin", "portal-admin", "sensor-publisher"}
PW = "correct horse battery"


def parse(text, existing=(), roles=ROLES):
    return parse_users_csv(text.encode(), roles, set(existing), 12)


# --- parsing ----------------------------------------------------------------
def test_valid_rows_are_planned():
    plan = parse(f"username,password,textname,roles\n"
                 f"sensor1,{PW},Garage sensor,sensor-publisher;admin\n"
                 f"sensor2,{PW},,\n")
    assert plan.errors == []
    assert [(u.username, u.textname, u.roles) for u in plan.users] == [
        ("sensor1", "Garage sensor", ["sensor-publisher", "admin"]),
        ("sensor2", "", []),
    ]


def test_header_names_are_case_insensitive_and_bom_is_ignored():
    plan = parse(f"﻿Username, Password ,TEXTNAME\r\nsensor1,{PW},Shed\r\n")
    assert plan.errors == []
    assert plan.users[0].username == "sensor1" and plan.users[0].textname == "Shed"


def test_missing_required_column_is_reported():
    plan = parse(f"username,textname\nsensor1,Shed\n")
    assert plan.users == [] and "password" in plan.errors[0]


def test_empty_and_header_only_files_are_reported():
    assert "empty" in parse("").errors[0]
    assert "no users" in parse("username,password\n").errors[0]


def test_non_utf8_is_reported():
    plan = parse_users_csv("username,password\nzoë,x\n".encode("latin-1"), ROLES, set(), 12)
    assert "UTF-8" in plan.errors[0]


def test_each_row_problem_is_reported_with_its_line_number():
    plan = parse(f"username,password,roles\n"
                 f"bad name,{PW},\n"                 # line 2: bad username
                 f"dup,{PW},\n"
                 f"dup,{PW},\n"                      # line 4: repeated in file
                 f"taken,{PW},\n"                    # line 5: already on broker
                 f"short,tiny,\n"                    # line 6: password too short
                 f"alice2,{PW},nosuchrole\n",        # line 7: unknown role
                 existing={"taken"})
    assert [u.username for u in plan.users] == ["dup"]
    text = " ".join(plan.errors)
    for needle in ("Line 2:", "Line 4:", "Line 5:", "Line 6:", "Line 7:", "unknown role(s): nosuchrole"):
        assert needle in text


def test_line_numbers_count_blank_lines():
    # Line 3 is blank and line 4 is the bad row. DictReader would skip the blank line and say 3.
    plan = parse(f"username,password\nok1,{PW}\n\nbad,short\n")
    assert plan.errors == ["Line 4: Use at least 12 characters."]


def test_error_messages_end_with_a_single_full_stop():
    plan = parse("username,password,roles\nbad,short,nosuchrole\n")
    assert plan.errors == ["Line 2: Use at least 12 characters; unknown role(s): nosuchrole."]


def test_password_containing_username_is_rejected():
    plan = parse(f"username,password\nsensor1,my-sensor1-password\n")
    assert plan.users == [] and "must not contain the username" in plan.errors[0]


def test_row_limit():
    rows = "".join(f"user{i},{PW}\n" for i in range(MAX_ROWS + 5))
    plan = parse("username,password\n" + rows)
    assert len(plan.users) == MAX_ROWS
    assert any("more than" in e for e in plan.errors)


# --- route ------------------------------------------------------------------
def admin_session(broker):
    c = make_client(broker)
    assert login(c, "/admin/login", "alice", "alice-old-password").status_code == 303
    return c


def upload(c, data, token=None):
    return c.post("/admin/users/import",
                  data={"csrf": token or csrf_of(c, "/admin")},
                  files={"file": ("users.csv", data, "text/csv")})


def test_admin_imports_a_valid_file(broker):
    c = admin_session(broker)
    r = upload(c, f"username,password,textname,roles\nsensor1,{PW},Shed,sensor-publisher\n".encode())
    assert r.status_code == 303
    assert broker.users["sensor1"]["roles"] == ["sensor-publisher"]
    follow = c.get("/admin")
    assert "Imported 1 user." in follow.text


def test_one_bad_row_creates_nothing(broker):
    c = admin_session(broker)
    r = upload(c, f"username,password\nsensor1,{PW}\nsensor2,short\n".encode())
    assert r.status_code == 400
    assert "Nothing was imported" in r.text and "Line 3:" in r.text
    assert "sensor1" not in broker.users and "sensor2" not in broker.users


def test_import_needs_csrf_token(broker):
    c = admin_session(broker)
    r = c.post("/admin/users/import", data={"csrf": "forged"},
               files={"file": ("users.csv", f"username,password\nsensor1,{PW}\n".encode(), "text/csv")})
    assert r.status_code == 403
    assert "sensor1" not in broker.users


def test_oversized_file_is_refused(broker):
    c = admin_session(broker)
    r = upload(c, b"username,password\n" + b"x" * MAX_BYTES)
    assert r.status_code == 400 and "larger than" in r.text


def test_broker_failure_mid_import_is_reported(broker, monkeypatch):
    c = admin_session(broker)
    real = broker.create_client

    def flaky(u, p, roles=(), textname=""):
        if u == "sensor2":
            from mqtt_admin.dynsec import DynSecError
            raise DynSecError("broker says no")
        real(u, p, roles, textname)

    monkeypatch.setattr(broker, "create_client", flaky)
    r = upload(c, f"username,password\nsensor1,{PW}\nsensor2,{PW}\nsensor3,{PW}\n".encode())
    assert r.status_code == 400
    assert "sensor2: broker says no" in r.text
    assert "sensor1" in broker.users and "sensor3" not in broker.users
