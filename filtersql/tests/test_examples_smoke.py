# -*- coding: utf-8 -*-
"""
Smoke test for the examples/ directory.

Every example must at least start without raising. This catches the
class of bugs that only show up when a script is actually executed:
missing kwargs (allow_raw_fields=True), missing env vars, wrong imports.

It does NOT verify that the generated SQL is correct - that's what
the dedicated test suites are for.

Strategy:
  - Plain scripts (create_demo_db, pandas_duckdb) run in a subprocess,
    exit code must be 0.
  - Flask apps (datatables, cursor_pagination) are imported in-process
    and checked for an `app` object with a `/` route. Running them via
    subprocess would require port management and process cleanup, and
    we only need to know they load.
  - API scripts (gemini_integration) are run without the API key set,
    to verify the error message is clear and mentions the key.
"""

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest


def _find_examples_dir() -> Path:
    here = Path(__file__).resolve().parent
    for parent in [here, *here.parents]:
        candidate = parent / "examples"
        if candidate.is_dir():
            return candidate
    raise RuntimeError("examples/ directory not found")


EXAMPLES_DIR = _find_examples_dir()


# ---- Registry ----------------------------------------------------------
# Add new examples here as they are created.

PLAIN_SCRIPTS = [
    "ai/create_demo_db.py",
    "pandas_duckdb/pandas_duckdb.py",
]

FLASK_APPS = [
    "datatables/datatables_example.py",
    "pagination/cursor_pagination.py",
]

# (script, env var name that must be present for a full run)
API_SCRIPTS = [
    ("ai/gemini_integration.py", "GEMINI_API_KEY"),
]


# ---- Fixture -----------------------------------------------------------

@pytest.fixture(scope="module")
def workspace(tmp_path_factory):
    """
    Temp dir containing demo.db, produced once by running
    create_demo_db.py. Shared by all tests in this module.
    """
    workdir = tmp_path_factory.mktemp("examples")

    script = EXAMPLES_DIR / "ai" / "create_demo_db.py"
    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=workdir,
        capture_output=True,
        timeout=60,
    )
    assert result.returncode == 0, (
        f"create_demo_db.py failed:\n"
        f"stdout: {result.stdout.decode()}\n"
        f"stderr: {result.stderr.decode()}"
    )
    assert (workdir / "demo.db").exists(), "demo.db was not created"

    return workdir


# ---- Tests -------------------------------------------------------------

@pytest.mark.parametrize("script_rel", PLAIN_SCRIPTS)
def test_plain_script_exits_cleanly(script_rel, workspace):
    """Scripts that terminate must exit with code 0."""
    script = EXAMPLES_DIR / script_rel
    if not script.exists():
        pytest.skip(f"{script_rel} not present")

    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=workspace,
        capture_output=True,
        timeout=60,
    )
    assert result.returncode == 0, (
        f"{script_rel} exited with {result.returncode}\n"
        f"stdout: {result.stdout.decode()}\n"
        f"stderr: {result.stderr.decode()}"
    )


@pytest.mark.parametrize("script_rel", FLASK_APPS)
def test_flask_app_imports(script_rel, workspace, monkeypatch):
    """
    Flask apps: import the module, verify the `app` object exists and
    has the expected routes registered. Import is safe because each
    app's app.run() is guarded by `if __name__ == '__main__'`.
    """
    script = EXAMPLES_DIR / script_rel
    if not script.exists():
        pytest.skip(f"{script_rel} not present")

    # Flask apps call sqlite3.connect('demo.db') at request time,
    # so the CWD must contain demo.db.
    monkeypatch.chdir(workspace)

    spec = importlib.util.spec_from_file_location(script.stem, script)
    module = importlib.util.module_from_spec(spec)
    sys.modules[script.stem] = module  # register so Flask can find root_path

    try:
        spec.loader.exec_module(module)
    except Exception as e:
        pytest.fail(f"{script_rel} failed to import: {type(e).__name__}: {e}")

    assert hasattr(module, "app"), f"{script_rel} defines no 'app' object"

    rules = {r.rule for r in module.app.url_map.iter_rules()}
    assert "/" in rules, f"{script_rel}: no '/' route registered. Routes: {rules}"


@pytest.mark.parametrize("script_rel,api_key", API_SCRIPTS)
def test_api_script_fails_clearly_without_key(script_rel, api_key, workspace):
    """
    API scripts should fail fast with a clear error when the API key is
    missing, not crash with a cryptic SDK traceback.
    """
    script = EXAMPLES_DIR / script_rel
    if not script.exists():
        pytest.skip(f"{script_rel} not present")

    env = {**os.environ, api_key: ""}
    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=workspace,
        capture_output=True,
        timeout=30,
        env=env,
    )

    assert result.returncode != 0, (
        f"{script_rel} should have failed without {api_key}, but exited 0"
    )
    stderr = result.stderr.decode()
    assert api_key in stderr, (
        f"{script_rel} did not mention '{api_key}' in its error.\n"
        f"stderr was:\n{stderr}"
    )