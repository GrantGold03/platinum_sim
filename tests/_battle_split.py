"""The battle-test split (012): every test that starts the battle worker carries `battle_sim`.

A stand-in `node` (tests/node_shim/node), first on PATH for the whole session, logs each start of
sim/worker.mjs with the test and fixture running at that moment, then execs the real node. PATH and
the environment are inherited by subprocess and `spawn` children, so starts there are seen too.

Checks, in every run (contracts/test-modes.md):
- an unmarked test that started the worker fails at its teardown;
- at session end: an unmarked test that uses a fixture which started the worker, a start outside any
  test, and a marked test that passed without reaching the worker each fail the session.

Loaded by tests/conftest.py (`pytest_plugins`), or with `-p _battle_split` and tests/ on PYTHONPATH.
The marker is registered here, not in pyproject.toml: platsim_code_hash covers pyproject.toml, and
this test-only feature must not change it.
"""

import json
import os
import shutil
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SHIM_DIR = Path(__file__).resolve().parent / "node_shim"
WORKER_SCRIPT = (REPO_ROOT / "sim" / "worker.mjs").resolve()
MARKER = "battle_sim"
MARKER_HELP = (
    "battle_sim: starts the battle worker (node sim/worker.mjs), directly, via a fixture, "
    "or in a child process; excluded by the fast mode"
)


class _Split:
    def __init__(self, log_path):
        self.log_path = log_path
        self.flagged = set()  # tests already failed at teardown for their own unmarked start
        self.setup_passed = set()
        self.passed = set()  # setup and call passed, not an expected failure
        self.under = []  # (test id, message)
        self.outside = []
        self.over = []
        self.routes = {}  # marked test -> "own start" or the starter fixture

    def records(self):
        try:
            text = self.log_path.read_text()
        except FileNotFoundError:
            return []
        out = []
        for line in text.splitlines():
            test, marked, fixture, pid = (line.split("\t") + ["", "", "", ""])[:4]
            out.append({"test": test, "marked": marked, "fixture": fixture, "pid": pid})
        return out


def _fixture_key(fixturedef):
    return f"{fixturedef.baseid}::{fixturedef.argname}"


def _resolved_fixture_keys(item):
    """`<baseid>::<name>` of each fixture pytest resolved for this item (its whole closure)."""
    info = getattr(item, "_fixtureinfo", None)
    if info is None:
        return []
    keys = []
    for name in item.fixturenames:
        defs = info.name2fixturedefs.get(name)
        if defs:
            keys.append(_fixture_key(defs[-1]))
    return keys


def _marked(item):
    return item.get_closest_marker(MARKER) is not None


@pytest.hookimpl(trylast=True)  # after tests/conftest.py has set basetemp
def pytest_configure(config):
    config.addinivalue_line("markers", MARKER_HELP)
    real_node = os.environ.get("PLATSIM_REAL_NODE") or shutil.which("node")
    if real_node is None:
        raise pytest.UsageError("_battle_split: no `node` on PATH")
    log_path = config._tmp_path_factory.getbasetemp() / "battle-worker-starts.tsv"
    log_path.write_text("")
    os.environ["PLATSIM_REAL_NODE"] = real_node
    os.environ["PLATSIM_WORKER_SCRIPT"] = str(WORKER_SCRIPT)
    os.environ["PLATSIM_WORKER_LOG"] = str(log_path)
    # A nested pytest inherits the outer test's values; starts during its collection are outside any test.
    os.environ["PLATSIM_TEST_ID"] = ""
    os.environ["PLATSIM_TEST_MARKED"] = ""
    os.environ["PLATSIM_FIXTURE"] = ""
    path = os.environ.get("PATH", "")
    if path.split(os.pathsep)[:1] != [str(SHIM_DIR)]:
        os.environ["PATH"] = str(SHIM_DIR) + os.pathsep + path
    config._battle_split = _Split(log_path)


def _set_test(item):
    os.environ["PLATSIM_TEST_ID"] = item.nodeid if item is not None else ""
    os.environ["PLATSIM_TEST_MARKED"] = ("1" if _marked(item) else "0") if item is not None else ""
    os.environ["PLATSIM_FIXTURE"] = ""


@pytest.hookimpl(wrapper=True)
def pytest_runtest_setup(item):
    _set_test(item)
    return (yield)


@pytest.hookimpl(wrapper=True)
def pytest_runtest_call(item):
    _set_test(item)
    return (yield)


@pytest.hookimpl(wrapper=True)
def pytest_runtest_teardown(item, nextitem):
    _set_test(item)
    try:
        result = yield
    finally:
        _set_test(None)
    split = item.config._battle_split
    if any(r["test"] == item.nodeid and r["marked"] == "0" for r in split.records()):
        split.flagged.add(item.nodeid)
        pytest.fail(
            f"{item.nodeid} started the battle worker (sim/worker.mjs) but is not marked {MARKER}. "
            f"Add @pytest.mark.{MARKER}, or stop it from starting the worker.",
            pytrace=False,
        )
    return result


@pytest.hookimpl(wrapper=True)
def pytest_fixture_setup(fixturedef, request):
    previous = os.environ.get("PLATSIM_FIXTURE", "")
    os.environ["PLATSIM_FIXTURE"] = _fixture_key(fixturedef)
    try:
        return (yield)
    finally:
        os.environ["PLATSIM_FIXTURE"] = previous


@pytest.hookimpl(wrapper=True)
def pytest_runtest_makereport(item, call):
    report = yield
    split = item.config._battle_split
    if report.when == "setup" and report.passed:
        split.setup_passed.add(item.nodeid)
    if report.when == "call" and report.passed and not hasattr(report, "wasxfail"):
        split.passed.add(item.nodeid)
    return report


@pytest.hookimpl(tryfirst=True)
def pytest_sessionfinish(session, exitstatus):
    split = getattr(session.config, "_battle_split", None)
    if split is None:
        return
    records = split.records()
    own = {r["test"] for r in records if r["test"]}
    starters = {r["fixture"] for r in records if r["fixture"]}

    for r in records:
        if not r["test"]:
            split.outside.append(
                f"the battle worker was started outside any test (fixture {r['fixture'] or 'none'})."
            )
        elif r["marked"] == "0" and r["test"] not in split.flagged:
            split.flagged.add(r["test"])
            split.under.append(
                f"{r['test']} started the battle worker (sim/worker.mjs) but is not marked {MARKER}."
            )

    for item in session.items:
        nodeid = item.nodeid
        used = [k for k in _resolved_fixture_keys(item) if k in starters]
        if _marked(item):
            if nodeid in own:
                split.routes[nodeid] = "own start"
            elif used:
                split.routes[nodeid] = f"fixture {used[0]}"
            elif nodeid in split.passed:
                split.over.append(
                    f"{nodeid} is marked {MARKER} but never reached the battle worker in this run. "
                    "Remove the mark."
                )
        elif used and nodeid in split.setup_passed and nodeid not in split.flagged:
            split.flagged.add(nodeid)
            split.under.append(
                f"{nodeid} uses fixture {used[0]}, which starts the battle worker, but is not marked {MARKER}."
            )

    report_path = os.environ.get("PLATSIM_SPLIT_REPORT")
    if report_path:
        Path(report_path).write_text(
            json.dumps(
                {
                    "worker_starts": len(records),
                    "starter_fixtures": sorted(starters),
                    "marked_routes": split.routes,
                    "under_marked": split.under,
                    "started_outside_tests": split.outside,
                    "over_marked": split.over,
                },
                indent=2,
            )
            + "\n"
        )
    if (split.under or split.outside or split.over) and session.exitstatus == pytest.ExitCode.OK:
        session.exitstatus = pytest.ExitCode.TESTS_FAILED
    split.records_count = len(records)
    split.starters = starters


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    split = getattr(config, "_battle_split", None)
    if split is None or not hasattr(split, "records_count"):
        return
    tr = terminalreporter
    tr.section("battle split")
    tr.write_line(
        f"{split.records_count} battle worker starts; {len(split.routes)} marked tests reached it; "
        f"under-marked {len(split.under)}, started outside a test {len(split.outside)}, "
        f"over-marked {len(split.over)}"
    )
    for nodeid, route in sorted(split.routes.items()):
        tr.write_line(f"  {nodeid}: {route}")
    for msg in split.under + split.outside + split.over:
        tr.write_line(f"SPLIT FAILURE: {msg}", red=True)
