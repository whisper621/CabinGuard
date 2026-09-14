"""Run a Python module with the repository virtual environment when available."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def project_python() -> Path:
    candidate = (
        PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
        if os.name == "nt"
        else PROJECT_ROOT / ".venv" / "bin" / "python"
    )
    return candidate if candidate.exists() else Path(sys.executable)


def main() -> int:
    return subprocess.run(
        [str(project_python()), *sys.argv[1:]],
        cwd=PROJECT_ROOT,
        check=False,
    ).returncode


if __name__ == "__main__":
    raise SystemExit(main())
