import argparse
import secrets
import string
from pathlib import Path

from src.auth import write_auth_config
from config.settings import AUTH_CONFIG_FILE


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the first Surfboard Scraper admin credential.")
    parser.add_argument("--username", default="admin")
    args = parser.parse_args()

    if Path(AUTH_CONFIG_FILE).exists():
        raise SystemExit(
            f"Refusing to overwrite existing authentication config: {AUTH_CONFIG_FILE}"
        )

    password = "".join(secrets.choice(string.ascii_letters + string.digits + "!@#$%^&*") for _ in range(24))
    write_auth_config(args.username, password)

    print("First admin credential generated.")
    print(f"Username: {args.username}")
    print(f"Password: {password}")
    print(f"Stored hashed credential in: {AUTH_CONFIG_FILE}")
    print("Store the password securely; it cannot be recovered from the application.")


if __name__ == "__main__":
    main()
