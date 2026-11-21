"""Deployment entry point: makes `src/` importable, then runs the dashboard."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from dashboard.app import main  # noqa: E402

main()
