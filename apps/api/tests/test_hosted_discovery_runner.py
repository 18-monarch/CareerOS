import runpy
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

RUNNER = Path(__file__).resolve().parents[3] / "scripts/run-hosted-discovery.py"


def test_public_runner_rejects_missing_or_unsafe_config_without_echoing_secrets(capsys):
    runner = runpy.run_path(str(RUNNER))
    base = {
        "DATABASE_URL": "postgresql://user:private-password@ep.neon.tech/db?sslmode=require",
        "FRONTEND_ORIGIN": "https://careeros.example.com",
    }
    assert runner["valid_config"](base)
    for values in (
        {},
        {**base, "DATABASE_URL": "sqlite:///local.db"},
        {**base, "DATABASE_URL": base["DATABASE_URL"].replace("ep.neon", "ep-pooler.neon")},
        {**base, "DATABASE_URL": base["DATABASE_URL"].replace("?sslmode=require", "")},
        {**base, "FRONTEND_ORIGIN": "https://careeros.example.com/"},
    ):
        with patch.dict("os.environ", values, clear=True), patch("subprocess.run") as child:
            assert runner["main"]() == 1
            child.assert_not_called()
    assert "private-password" not in capsys.readouterr().out


@pytest.mark.parametrize("failure", [False, True, "timeout"])
def test_public_runner_suppresses_child_output_and_propagates_failure(failure, capsys):
    runner = runpy.run_path(str(RUNNER))

    def execute(command, **kwargs):
        assert command[1:] == ["-m", "careeros.deploy", "cron"]
        assert kwargs["stdout"] == subprocess.DEVNULL
        assert kwargs["stderr"] == subprocess.DEVNULL
        assert kwargs["timeout"] == 900
        if failure == "timeout":
            raise subprocess.TimeoutExpired(command, 900, output="private-record")
        return subprocess.CompletedProcess(command, int(failure), "private-record", "secret")

    with patch("subprocess.run", side_effect=execute):
        assert runner["run_cycle"]() == (1 if failure else 0)
    output = capsys.readouterr().out
    assert "private-record" not in output
    assert "secret" not in output
