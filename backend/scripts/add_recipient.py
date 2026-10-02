import argparse

from src.email_config import add_recipient


def main() -> None:
    parser = argparse.ArgumentParser(description="Add a Recipient to the Email Config.")
    parser.add_argument("email", help="Recipient email address")
    args = parser.parse_args()

    add_recipient(
        {
            "email": args.email,
            "filters": {},
            "include_sent": False,
            "auto_send": True,
        }
    )
    print(f"Recipient added: {args.email}")


if __name__ == "__main__":
    main()
