import pytest

from suhail.security import LoginThrottle, hash_password, safe_display_name, verify_password


def test_correct_password_verifies_and_wrong_one_does_not():
    stored = hash_password("correct horse battery")
    assert verify_password("correct horse battery", stored)
    assert not verify_password("correct horse batterY", stored)


def test_hashes_are_salted():
    assert hash_password("same password 123") != hash_password("same password 123")


def test_short_passwords_are_refused():
    with pytest.raises(ValueError):
        hash_password("short")


@pytest.mark.parametrize("bad", ["", "plaintext", "md5$1$2$3$4$5", "scrypt$x$y$z$@@$@@"])
def test_malformed_or_missing_hash_fails_closed(bad):
    assert not verify_password("anything", bad)


def test_unicode_passwords_work():
    stored = hash_password("كلمة سر طويلة جدا")
    assert verify_password("كلمة سر طويلة جدا", stored)


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def test_throttle_locks_after_max_failures_then_recovers():
    clock = Clock()
    throttle = LoginThrottle(max_attempts=3, window_seconds=60, clock=clock)
    assert throttle.seconds_until_allowed() == 0
    for _ in range(3):
        throttle.record_failure()
    assert 0 < throttle.seconds_until_allowed() <= 61
    clock.now += 61
    assert throttle.seconds_until_allowed() == 0


def test_successful_login_resets_the_counter():
    throttle = LoginThrottle(max_attempts=2, window_seconds=60, clock=Clock())
    throttle.record_failure()
    throttle.record_failure()
    assert throttle.seconds_until_allowed() > 0
    throttle.reset()
    assert throttle.seconds_until_allowed() == 0


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("report.pdf", "report.pdf"),
        ("../../etc/passwd", "passwd"),
        ("C:\\Users\\x\\file.docx", "file.docx"),
        ("a\x00b\nc.txt", "abc.txt"),
        ("   ", "unnamed"),
        ("..", "unnamed"),
        ("تقرير سنوي.pdf", "تقرير سنوي.pdf"),
    ],
)
def test_safe_display_name(raw, expected):
    assert safe_display_name(raw) == expected


def test_safe_display_name_caps_length():
    assert len(safe_display_name("a" * 500 + ".pdf")) == 150
