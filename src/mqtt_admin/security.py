import re
import secrets
import time
from collections import defaultdict, deque

USERNAME_RE = re.compile(r"^[A-Za-z0-9._@-]{1,64}$")


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
