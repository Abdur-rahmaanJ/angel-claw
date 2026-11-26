"""Compatibility entry point: `python -m angel_claw.main` behaves like the CLI."""

from .cli import main

if __name__ == "__main__":
    main()
