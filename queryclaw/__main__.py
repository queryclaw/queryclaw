"""Run QueryClaw as a module."""

from queryclaw.cli.commands import app


def main() -> None:
    """Entrypoint for `python -m queryclaw`."""
    app()


if __name__ == "__main__":
    main()
