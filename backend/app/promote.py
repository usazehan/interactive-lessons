"""Promote a user to admin (admins bypass project-ownership checks).

    python -m app.promote someone@example.com

Run against whatever DATABASE_PATH points at. There is intentionally no HTTP
endpoint for this — admin rights are granted out of band.
"""
import argparse
from typing import Optional

from app.store import user_store


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Promote a user to admin.")
    parser.add_argument("email", help="the user's email")
    args = parser.parse_args(argv)

    user = user_store.get_orm_by_email(args.email)
    if user is None:
        print(f"no user with email {args.email}")
        return 1
    user_store.set_role(user.id, "admin")
    print(f"{args.email} is now an admin")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
