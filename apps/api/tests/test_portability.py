"""Cross-platform installation and real process lock regressions."""

import subprocess
import sys
from pathlib import Path

import pytest
from careeros.db import build_engine
from careeros.services.locking import job_lock
from packaging.markers import default_environment
from packaging.requirements import Requirement

ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize("filename", ["requirements.lock", "requirements-dev.lock"])
def test_windows_dependencies_skip_unix_loop(filename):
    environment = {
        **default_environment(),
        "os_name": "nt",
        "sys_platform": "win32",
        "platform_system": "Windows",
        "platform_python_implementation": "CPython",
        "implementation_name": "cpython",
        "python_version": "3.12",
    }
    selected = set()
    for line in (ROOT / filename).read_text().splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        requirement = Requirement(line)
        if not requirement.marker or requirement.marker.evaluate(environment):
            selected.add(requirement.name)
    assert "uvloop" not in selected
    assert {"uvicorn", "tzdata", "psycopg-binary"} <= selected
    if filename == "requirements-dev.lock":
        assert "colorama" in selected


def test_local_lock_excludes_other_process_and_releases_after_error(tmp_path):
    engine = build_engine(f"sqlite:///{tmp_path}/locks.db")
    code = """
import sys
from careeros.db import build_engine
from careeros.services.locking import job_lock
engine = build_engine(sys.argv[1])
with job_lock(engine, 'portable-lock') as acquired:
    print('acquired' if acquired else 'busy')
engine.dispose()
"""

    def contender():
        result = subprocess.run(
            [sys.executable, "-c", code, str(engine.url)],
            check=True,
            capture_output=True,
            text=True,
            timeout=15,
        )
        return result.stdout.strip()

    try:
        with pytest.raises(RuntimeError, match="worker failed"):
            with job_lock(engine, "portable-lock") as acquired:
                assert acquired
                assert contender() == "busy"
                raise RuntimeError("worker failed")
        assert contender() == "acquired"
    finally:
        engine.dispose()
