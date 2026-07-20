"""Canonical schema-v8 demo reset command.

The old reset_v7_demo_data module remains as an import-compatible entry point
for existing local automation while this wrapper exposes the current name.
"""

from reset_v7_demo_data import main


if __name__ == "__main__":
    raise SystemExit(main())
