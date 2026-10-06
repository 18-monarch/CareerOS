"""Private operator commands: bootstrap an empty account or recover its password."""

import argparse
import getpass

from sqlalchemy import delete, select

from careeros.db import SessionLocal
from careeros.models import AuditLog, AuthSession, Preferences, Profile, User
from careeros.schemas import Credentials, PreferenceIn
from careeros.security import hasher


def manage_user(db, email, password, name="CareerOS user", reset=False):
    credentials = Credentials(email=email, password=password, name=name)
    user = db.scalar(select(User).where(User.email == credentials.email.lower()).with_for_update())
    if reset:
        if not user:
            raise ValueError("Account not found")
        user.password_hash = hasher.hash(password)
        db.execute(delete(AuthSession).where(AuthSession.user_id == user.id))
        action = "password.operator_reset"
    else:
        if user:
            raise ValueError("Account already exists; it was not modified")
        user = User(
            email=credentials.email.lower(),
            name=credentials.name,
            password_hash=hasher.hash(password),
        )
        db.add(user)
        db.flush()
        db.add_all(
            [
                Profile(user_id=user.id),
                Preferences(user_id=user.id, data=PreferenceIn().model_dump()),
            ]
        )
        action = "account.operator_created"
    db.add(AuditLog(user_id=user.id, action=action))
    db.commit()
    return user.id


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["create-user", "reset-password"])
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", default="CareerOS user")
    args = parser.parse_args()
    # Do not accept secrets as command-line arguments or write them to logs.
    password = getpass.getpass("New password (12+ characters): ")
    if password != getpass.getpass("Confirm new password: "):
        parser.exit(1, "Passwords did not match; nothing changed.\n")
    try:
        with SessionLocal() as db:
            manage_user(db, args.email, password, args.name, reset=args.command == "reset-password")
    except ValueError:
        parser.exit(
            1,
            "Unable to complete account operation. Check the email, password length and whether the account already exists.\n",
        )
    print(
        "Account created without demo data."
        if args.command == "create-user"
        else "Password reset; all existing sessions revoked."
    )


if __name__ == "__main__":
    main()
