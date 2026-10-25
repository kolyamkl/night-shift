"""dataconv: convert open PII datasets into the Veil canonical document format."""


def main() -> None:
    from .build import main as _main

    _main()
