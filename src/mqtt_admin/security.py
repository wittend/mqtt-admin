import re
import secrets
import time
from collections import defaultdict, deque

USERNAME_RE = re.compile(r"^[A-Za-z0-9._@-]{1,64}$")
ROLE_RE = USERNAME_RE  # role names use the same characters as usernames

# dynsec rule types the portal can create, and whether each takes wildcards.
# Publish rules match the topic pattern against the publishing topic, and
# subscribe-pattern rules match a subscription pattern.  "Literal" subscribe
# rules must name one topic exactly.
ACL_TYPES = {
    "publishClientSend": True,
    "publishClientReceive": True,
    "subscribeLiteral": False,
    "subscribePattern": True,
    "unsubscribeLiteral": False,
    "unsubscribePattern": True,
}


def acl_problem(acltype: str, topic: str) -> str | None:
    """Return what is wrong with a topic rule, or None when it is acceptable."""
    if acltype not in ACL_TYPES:
        return "Choose a rule type from the list."
    if not topic or len(topic) > 256:
        return "Topics are 1 to 256 characters."
    if any(ch.isspace() or ord(ch) < 32 for ch in topic):
        return "Topics cannot contain spaces or control characters."
    if topic.startswith("$"):
        return "Topics starting with $ are reserved for the broker."
    levels = topic.split("/")
    for i, level in enumerate(levels):
        if level == "#":
            if i != len(levels) - 1:
                return "# must be the last level of a topic."
        elif level == "+":
            continue
        elif "+" in level or "#" in level:
            return "+ and # must fill a whole level, for example sensors/+/data."
    if not ACL_TYPES[acltype] and ("+" in topic or "#" in topic):
        return "This rule type needs one exact topic, without + or #."
    return None


def password_problem(password: str, username: str, min_length: int) -> str | None:
    """Return what is wrong with a new password, or None when it is acceptable."""
    if len(password) < min_length:
        return f"Use at least {min_length} characters."
    if len(password) > 128:
        return "Use at most 128 characters."
    if username.lower() in password.lower():
        return "The password must not contain the username."
    if len(set(password)) < 5:
        return "That password is too repetitive."
    return None


class LoginLimiter:
    """Counts failed logins per (client address, username) and per address alone."""

    def __init__(self, per_user=5, per_ip=20, window=900.0, clock=time.monotonic):
        self.per_user, self.per_ip, self.window, self.clock = per_user, per_ip, window, clock
        self._fails: dict[tuple, deque] = defaultdict(deque)

    def _prune(self, key):
        q, now = self._fails[key], self.clock()
        while q and now - q[0] > self.window:
            q.popleft()
        return q

    def blocked(self, ip: str, username: str) -> bool:
        return (len(self._prune((ip, username.lower()))) >= self.per_user
                or len(self._prune((ip, ""))) >= self.per_ip)

    def fail(self, ip: str, username: str):
        now = self.clock()
        self._fails[(ip, username.lower())].append(now)
        self._fails[(ip, "")].append(now)

    def succeed(self, ip: str, username: str):
        self._fails.pop((ip, username.lower()), None)


def new_csrf() -> str:
    return secrets.token_urlsafe(24)
