"""Integration tests for the command-line entry point."""

from __future__ import annotations

import json
import subprocess
import sys
from typing import Any

import pytest

import track24
from helpers.constants import (
    CLI_TIMEOUT_ARGUMENT,
    ENDPOINT_PATH,
    EVENT_ID,
    HTTP_FORBIDDEN,
    OUT_OF_RANGE_TIMEOUT,
    PAGE_WITH_LITERAL_TEMPLATE,
    PASSWORD,
    SCRIPTS_DIRECTORY,
    SECRET_ADDRESS,
    SUBPROCESS_TIMEOUT_SECONDS,
    TRACK_CODE,
    TRACKER_SCRIPT,
)
from helpers.crypto import encrypt_envelope
from helpers.server import FakeTrack24, Reply

pytestmark = pytest.mark.integration


@pytest.fixture
def live_site(fake_track24: FakeTrack24) -> FakeTrack24:
    """A fake site with a standard page and endpoint registered."""
    fake_track24.routes["/"] = Reply.html(
        PAGE_WITH_LITERAL_TEMPLATE.format(password=PASSWORD, endpoint=ENDPOINT_PATH)
    )
    return fake_track24


def test_cli_prints_summary_json(
    live_site: FakeTrack24, opener: Any, ok_result: dict[str, Any], capsys: pytest.CaptureFixture[str]
) -> None:
    """Success prints one JSON summary line and exits 0."""
    live_site.routes[ENDPOINT_PATH] = Reply.json(encrypt_envelope(ok_result))

    exit_code = track24.main([TRACK_CODE, "--timeout", CLI_TIMEOUT_ARGUMENT], opener=opener)

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.err == ""
    output = json.loads(captured.out)
    assert output["track"] == TRACK_CODE
    assert output["last_event_id"] == EVENT_ID
    assert output["delivered"] is False
    assert SECRET_ADDRESS not in captured.out


def test_cli_reports_http_status(
    live_site: FakeTrack24, opener: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    """HTTP failures are reported as ``http_error`` with the status code."""
    live_site.routes[ENDPOINT_PATH] = Reply.json({"error": "blocked"}, status=HTTP_FORBIDDEN)

    exit_code = track24.main([TRACK_CODE], opener=opener)

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.out == ""
    assert json.loads(captured.err) == {"ok": False, "error": "http_error", "http_status": HTTP_FORBIDDEN}


def test_cli_reports_only_error_type(
    live_site: FakeTrack24, opener: Any, ok_result: dict[str, Any], capsys: pytest.CaptureFixture[str]
) -> None:
    """Diagnostics name the failure class and leak no response content or password."""
    challenged = {**ok_result, "challenge": True}
    live_site.routes[ENDPOINT_PATH] = Reply.json(encrypt_envelope(challenged))

    exit_code = track24.main([TRACK_CODE], opener=opener)

    captured = capsys.readouterr()
    assert exit_code == 1
    assert json.loads(captured.err) == {"ok": False, "error": "ChallengeError"}
    assert PASSWORD not in captured.err
    assert SECRET_ADDRESS not in captured.err


def test_cli_rejects_external_endpoint_flag(
    live_site: FakeTrack24, opener: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    """``--endpoint`` outside Track24 is refused before the POST."""
    endpoint = "https://example.com/ajax/x.ajax.php"

    exit_code = track24.main([TRACK_CODE, "--endpoint", endpoint], opener=opener)

    captured = capsys.readouterr()
    assert exit_code == 1
    assert json.loads(captured.err)["error"] == "EndpointError"
    assert [request.method for request in live_site.requests] == ["GET"]


@pytest.mark.parametrize("timeout", ["0", "-1", OUT_OF_RANGE_TIMEOUT])
def test_cli_rejects_out_of_range_timeout(timeout: str, capsys: pytest.CaptureFixture[str]) -> None:
    """Argument errors exit with argparse's usage status 2."""
    argv = [TRACK_CODE, "--timeout", timeout]

    with pytest.raises(SystemExit) as caught:
        track24.main(argv)

    assert caught.value.code == 2
    assert "--timeout" in capsys.readouterr().err


def test_script_runs_standalone_from_installed_layout() -> None:
    """The script imports its sibling constants module when run as a file, as Hermes installs it."""
    command = [sys.executable, str(TRACKER_SCRIPT), "--help"]

    completed = subprocess.run(
        command,
        cwd=SCRIPTS_DIRECTORY.parent,
        capture_output=True,
        text=True,
        timeout=SUBPROCESS_TIMEOUT_SECONDS,
        check=False,
    )

    assert completed.returncode == 0
    assert "--endpoint" in completed.stdout


def test_script_rejects_invalid_code_as_subprocess() -> None:
    """A malformed identifier fails without network access and prints a typed error."""
    command = [sys.executable, str(TRACKER_SCRIPT), "bad code"]

    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=SUBPROCESS_TIMEOUT_SECONDS,
        check=False,
    )

    assert completed.returncode == 1
    assert json.loads(completed.stderr) == {"ok": False, "error": "InvalidTrackCodeError"}
