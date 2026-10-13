"""Read a CSV of new users and check every row before anything is created on the broker.

Columns: username, password, textname (optional), roles (optional, separated by semicolons).
The first row must be the header. Column names are not case-sensitive.
"""
import csv
import io
from dataclasses import dataclass, field

from .security import USERNAME_RE, password_problem

MAX_BYTES = 256 * 1024
MAX_ROWS = 500
REQUIRED_COLUMNS = {"username", "password"}


@dataclass
class NewUser:
    username: str
    password: str
    textname: str
    roles: list[str]


@dataclass
class Plan:
    users: list[NewUser] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def parse_users_csv(data: bytes, known_roles, existing_users, min_length: int) -> Plan:
    """Return the users to create, or the list of problems. Creates nothing itself."""
    plan = Plan()
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        plan.errors.append("The file must be UTF-8 text, such as a CSV saved from a spreadsheet as UTF-8.")
        return plan

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        plan.errors.append("The file is empty. The first row must be the header: username,password,textname,roles.")
        return plan
    reader.fieldnames = [h.strip().lower() for h in reader.fieldnames]
    missing = REQUIRED_COLUMNS - set(reader.fieldnames)
    if missing:
        plan.errors.append(f"Missing column(s): {', '.join(sorted(missing))}. "
                           "The first row must be the header: username,password,textname,roles.")
        return plan

    taken = set(existing_users)
    for raw in reader:
        # line_num is the file line the row ended on. It counts blank lines, which DictReader skips.
        n = reader.line_num
        if len(plan.users) + len(plan.errors) >= MAX_ROWS:
            plan.errors.append(f"The file has more than {MAX_ROWS} rows. Split it and import in parts.")
            break
        username = (raw.get("username") or "").strip()
        password = raw.get("password") or ""
        textname = (raw.get("textname") or "").strip()
        roles = [r.strip() for r in (raw.get("roles") or "").split(";") if r.strip()]

        problems = []
        if not USERNAME_RE.match(username):
            problems.append("username must use letters, digits and . _ @ - only, up to 64")
        elif username in taken:
            problems.append(f"{username} already exists or is repeated in this file")
        elif problem := password_problem(password, username, min_length):
            problems.append(problem)
        unknown = [r for r in roles if r not in known_roles]
        if unknown:
            problems.append(f"unknown role(s): {', '.join(unknown)}")

        if problems:
            # password_problem() messages end in a full stop of their own, so strip it before joining.
            plan.errors.append(f"Line {n}: " + "; ".join(p.rstrip(".") for p in problems) + ".")
        else:
            plan.users.append(NewUser(username, password, textname, roles))
            taken.add(username)
    if not plan.users and not plan.errors:
        plan.errors.append("The file has a header but no users in it.")
    return plan
