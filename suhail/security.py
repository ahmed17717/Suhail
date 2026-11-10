"""Small, dependency-free security helpers.

* Password hashing uses scrypt from the standard library (memory-hard, no extra
  dependency). Only a hash is ever stored in the environment.
* `LoginThrottle` slows brute-forcing of the admin password.
* `safe_display_name` makes user-supplied file names safe to store and render.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import re
import threading
import time
from collections import deque
from collections.abc import Callable

_SCHEME = "scrypt"
_N, _R, _P = 2**14, 8, 1  # ~16 MB, a few hundred ms per hash
_SALT_BYTES = 16
_KEY_BYTES = 32
MIN_PASSWORD_LENGTH = 10


def hash_password(password: str) -> str:
    """Return a self-describing hash: ``scrypt$N$r$p$salt$key`` (base64)."""
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters long.")
    salt = os.urandom(_SALT_BYTES)
    key = hashlib.scrypt(password.encode(), salt=salt, n=_N, r=_R, p=_P, dklen=_KEY_BYTES)
    b64 = lambda raw: base64.b64encode(raw).decode()  # noqa: E731
    return f"{_SCHEME}${_N}${_R}${_P}${b64(salt)}${b64(key)}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Constant-time check. Any malformed/empty hash simply fails closed."""
    try:
        scheme, n, r, p, salt_b64, key_b64 = stored_hash.split("$")
        if scheme != _SCHEME:
            return False
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(key_b64)
        candidate = hashlib.scrypt(
            password.encode(), salt=salt, n=int(n), r=int(r), p=int(p), dklen=len(expected)
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(candidate, expected)


class LoginThrottle:
    """Process-wide limiter: at most `max_attempts` failures per `window_seconds`.

    It is intentionally global rather than per-session: a per-session counter is
    trivially bypassed by opening a new browser tab. The trade-off (someone on the
    LAN can temporarily lock the admin out) is acceptable for a single-admin tool.
    """

    def __init__(
        self,
        max_attempts: int = 5,
        window_seconds: int = 300,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._max = max_attempts
        self._window = window_seconds
        self._clock = clock
        self._failures: deque[float] = deque()
        self._lock = threading.Lock()

    def _prune(self, now: float) -> None:
        while self._failures and now - self._failures[0] > self._window:
            self._failures.popleft()

    def seconds_until_allowed(self) -> int:
        """0 if a login attempt is allowed right now, otherwise seconds to wait."""
        with self._lock:
            now = self._clock()
            self._prune(now)
            if len(self._failures) < self._max:
                return 0
            return max(1, int(self._window - (now - self._failures[0])) + 1)

    def record_failure(self) -> None:
        with self._lock:
            now = self._clock()
            self._prune(now)
            self._failures.append(now)

    def reset(self) -> None:
        with self._lock:
            self._failures.clear()


_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")
_MAX_NAME_LEN = 150


def safe_display_name(raw: str, fallback: str = "unnamed") -> str:
    """Strip directories and control characters; cap length.

    The result is for *display and duplicate detection only*. Files are stored on
    disk under a generated UUID, so a hostile name can never influence a path.
    """
    name = raw.replace("\\", "/").split("/")[-1]
    name = _CONTROL_CHARS.sub("", name).strip().strip(".")
    return name[:_MAX_NAME_LEN] or fallback
