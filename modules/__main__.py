"""Allow `python -m modules` to run the CLI entry point."""

from modules.root_cli_main_entry import main

if __name__ == "__main__":
    import sys

    sys.exit(main())
