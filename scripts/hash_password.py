"""Generate the ADMIN_PASSWORD_HASH line for .env.

python -m scripts.hash_password
"""

from __future__ import annotations

import getpass
import sys

from suhail.security import MIN_PASSWORD_LENGTH, hash_password


def main() -> int:
    first = getpass.getpass("Admin password: ")
    if getpass.getpass("Repeat password: ") != first:
        print("Passwords do not match.", file=sys.stderr)
        return 1
    try:
        hashed = hash_password(first)
    except ValueError:
        print(f"Use at least {MIN_PASSWORD_LENGTH} characters.", file=sys.stderr)
        return 1
    # Single quotes: the hash contains '$', which some env loaders would expand.
    print("\nAdd this line to your .env file:\n")
    print(f"ADMIN_PASSWORD_HASH='{hashed}'")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
