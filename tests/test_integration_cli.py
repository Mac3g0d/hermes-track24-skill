"""Integration tests for the command-line entry point."""

import json
import subprocess
import sys
from typing import Any

import httpx
import pytest
from pytest_mock import MockerFixture

import track24
from constants import (
    CLI_TIMEOUT_ARGUMENT,
    CUSTOM_TIMEOUT_SECONDS,
    HTTP_FORBIDDEN,
    OUT_OF_RANGE_TIMEOUT,
    PASSWORD,
    SCRIPTS_DIRECTORY,
    SUBPROCESS_TIMEOUT_SECONDS,
    TRACKER_SCRIPT,
)
from fixtures.network import FakeTrack24
from track24_constants import MAX_TRACK_CODES_PER_RUN


async def test_cli_prints_summary_json(
    site: FakeTrack24, ok_result: dict[str, Any], track_code: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """Success prints one JSON summary line and exits 0."""
    site.page()
    site.payload(ok_result)

    exit_code = await track24.run([track_code, "--timeout", CLI_TIMEOUT_ARGUMENT])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.err == ""
    assert json.loads(captured.out) == track24.summary(ok_result)
    assert ok_result["data"]["destinationAddress"] not in captured.out


async def test_cli_passes_arguments_to_tracker(
    site: FakeTrack24, mocker: MockerFixture, track_code: str
) -> None:
    """Parsed arguments reach ``track_many`` unchanged."""
    tracker = mocker.patch.object(track24, "track_many", return_value=[])
    endpoint = "https://track24.ru/ajax/x.ajax.php"

    exit_code = await track24.run([track_code, "--endpoint", endpoint, "--timeout", CLI_TIMEOUT_ARGUMENT])

    assert exit_code == 0
    tracker.assert_awaited_once_with([track_code], endpoint, CUSTOM_TIMEOUT_SECONDS, None)
    assert site.requests == []


async def test_cli_prints_one_line_per_code(
    site: FakeTrack24, batch_codes: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    """Several identifiers produce JSON Lines in argument order."""
    site.page()
    site.echo()

    exit_code = await track24.run(batch_codes)

    lines = capsys.readouterr().out.splitlines()
    assert exit_code == 0
    assert [json.loads(line)["track"] for line in lines] == batch_codes


async def test_cli_mixed_results_exit_with_failure(
    site: FakeTrack24, track_code: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """Successes still reach stdout when another identifier fails; the exit code is 1."""
    site.page()
    site.echo()

    exit_code = await track24.run([track_code, "bad code"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert json.loads(captured.out)["track"] == track_code
    assert json.loads(captured.err) == {"track": "bad code", "ok": False, "error": "InvalidTrackCodeError"}


async def test_cli_reports_http_status(site: FakeTrack24, track_code: str, capsys: pytest.CaptureFixture[str]) -> None:
    """HTTP failures are reported as ``http_error`` with the status code."""
    site.page()
    site.respond(status_code=HTTP_FORBIDDEN, json={"error": "blocked"})

    exit_code = await track24.run([track_code])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.out == ""
    assert json.loads(captured.err) == {
        "track": track_code,
        "ok": False,
        "error": "http_error",
        "http_status": HTTP_FORBIDDEN,
    }


async def test_cli_reports_only_error_type(
    site: FakeTrack24, ok_result: dict[str, Any], track_code: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """Diagnostics name the failure class and leak no response content or password."""
    site.page()
    site.payload({**ok_result, "challenge": True})

    exit_code = await track24.run([track_code])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert json.loads(captured.err) == {"track": track_code, "ok": False, "error": "ChallengeError"}
    assert PASSWORD not in captured.err
    assert ok_result["data"]["destinationAddress"] not in captured.err


async def test_cli_rejects_external_endpoint_flag(
    site: FakeTrack24, track_code: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """``--endpoint`` outside Track24 is refused before the POST."""
    site.page()

    exit_code = await track24.run([track_code, "--endpoint", "https://example.com/ajax/x.ajax.php"])

    assert exit_code == 1
    assert json.loads(capsys.readouterr().err)["error"] == "EndpointError"
    assert [request.method for request in site.requests] == ["GET"]


async def test_cli_uses_injected_client(
    site: FakeTrack24, client: httpx.AsyncClient, ok_result: dict[str, Any], track_code: str
) -> None:
    """A caller-provided client is used and left open."""
    site.page()
    site.payload(ok_result)

    exit_code = await track24.run([track_code], client=client)

    assert exit_code == 0
    assert not client.is_closed


@pytest.mark.parametrize("timeout", ["0", "-1", OUT_OF_RANGE_TIMEOUT])
async def test_cli_rejects_out_of_range_timeout(
    timeout: str, track_code: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """Argument errors exit with argparse's usage status 2."""
    argv = [track_code, "--timeout", timeout]

    with pytest.raises(SystemExit) as caught:
        await track24.run(argv)

    assert caught.value.code == 2
    assert "--timeout" in capsys.readouterr().err


async def test_cli_rejects_too_many_codes(capsys: pytest.CaptureFixture[str]) -> None:
    """Bulk runs are refused before any network activity."""
    argv = [f"TEST{index:05d}" for index in range(MAX_TRACK_CODES_PER_RUN + 1)]

    with pytest.raises(SystemExit) as caught:
        await track24.run(argv)

    assert caught.value.code == 2
    assert "At most" in capsys.readouterr().err


async def test_cli_requires_a_code(capsys: pytest.CaptureFixture[str]) -> None:
    """The tracking identifier is a required positional argument."""
    argv: list[str] = []

    with pytest.raises(SystemExit) as caught:
        await track24.run(argv)

    assert caught.value.code == 2
    assert "code" in capsys.readouterr().err


def test_main_runs_event_loop(mocker: MockerFixture, track_code: str) -> None:
    """The synchronous ``main`` drives ``run`` to completion and returns its exit code."""
    runner = mocker.patch.object(track24, "run", return_value=0)

    exit_code = track24.main([track_code])

    assert exit_code == 0
    runner.assert_awaited_once_with([track_code])


def test_script_runs_standalone_from_installed_layout() -> None:
    """The script imports its sibling constants module when run as a file, as Hermes installs it."""
    command = [sys.executable, str(TRACKER_SCRIPT), "--help"]

    completed = subprocess.run(
        command, cwd=SCRIPTS_DIRECTORY.parent, capture_output=True, text=True, timeout=SUBPROCESS_TIMEOUT_SECONDS
    )

    assert completed.returncode == 0
    assert "--endpoint" in completed.stdout


def test_script_rejects_invalid_code_as_subprocess() -> None:
    """A malformed identifier fails through the real entry point without network access."""
    command = [sys.executable, str(TRACKER_SCRIPT), "bad code"]

    completed = subprocess.run(command, capture_output=True, text=True, timeout=SUBPROCESS_TIMEOUT_SECONDS)

    assert completed.returncode == 1
    assert json.loads(completed.stderr) == {"track": "bad code", "ok": False, "error": "InvalidTrackCodeError"}
