"""012 guard: the battle-test split detection (tests/_battle_split.py, tests/node_shim/node) works.

Each case writes throwaway test files into tmp_path and runs them in an inner pytest with the plugin,
then checks the outcome and message. Case 9 is the positive control for the instrument: the same
unmarked worker start passes without the plugin and the stand-in, so the failure in case 1 comes from
the detection. This file must start no worker in the outer session, so it is not marked.
"""

import ast
import inspect
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from platsim.pins import REPO_ROOT

TESTS_DIR = REPO_ROOT / "tests"
SHIM_DIR = TESTS_DIR / "node_shim"

START_WORKER = 'subprocess.run(["node", "sim/worker.mjs"], input="", check=True, timeout=60)'


def run_inner(tmp_path: Path, files: dict[str, str], *, plugin: bool = True) -> subprocess.CompletedProcess:
    (tmp_path / "pytest.ini").write_text("[pytest]\n")
    for name, body in files.items():
        (tmp_path / name).write_text(textwrap.dedent(body))
    env = dict(os.environ)
    env["PYTHONPATH"] = str(TESTS_DIR)
    args = [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "-q",
            f"--basetemp={tmp_path / 'inner'}", f"--rootdir={tmp_path}", "-c", str(tmp_path / "pytest.ini")]
    if plugin:
        args += ["-p", "_battle_split"]
    else:
        # No plugin and no stand-in: the outer session's split variables and PATH entry are removed.
        for key in [k for k in env if k.startswith("PLATSIM_")]:
            del env[key]
        env["PATH"] = os.pathsep.join(p for p in env["PATH"].split(os.pathsep) if Path(p) != SHIM_DIR)
    args += [str(tmp_path / name) for name in files]
    return subprocess.run(args, cwd=REPO_ROOT, env=env, capture_output=True, text=True, timeout=300)


def out(proc):
    return proc.stdout + proc.stderr


UNMARKED_START = f"""
    import subprocess

    def test_starts_worker():
        {START_WORKER}
"""


def test_unmarked_start_fails_and_names_the_test(tmp_path):  # case 1
    proc = run_inner(tmp_path, {"test_case1.py": UNMARKED_START})
    assert proc.returncode != 0, out(proc)
    assert "ERROR" in proc.stdout
    assert ("test_case1.py::test_starts_worker started the battle worker (sim/worker.mjs) but is not marked "
            "battle_sim") in proc.stdout, out(proc)


def test_marked_start_passes(tmp_path):  # case 2
    proc = run_inner(tmp_path, {"test_case2.py": f"""
        import subprocess
        import pytest

        @pytest.mark.battle_sim
        def test_starts_worker():
            {START_WORKER}
    """})
    assert proc.returncode == 0, out(proc)
    assert "1 battle worker starts; 1 marked tests reached it" in proc.stdout, out(proc)
    assert "test_case2.py::test_starts_worker: own start" in proc.stdout


def test_unmarked_start_in_spawn_child_fails(tmp_path):  # case 3
    proc = run_inner(tmp_path, {"test_case3.py": f"""
        import multiprocessing as mp
        import subprocess

        def child():
            {START_WORKER}

        def test_child_starts_worker():
            p = mp.get_context("spawn").Process(target=child)
            p.start()
            p.join(60)
            assert p.exitcode == 0
    """})
    assert proc.returncode != 0, out(proc)
    assert "test_case3.py::test_child_starts_worker started the battle worker" in proc.stdout, out(proc)


def test_over_marked_test_fails_the_session(tmp_path):  # case 4
    proc = run_inner(tmp_path, {"test_case4.py": """
        import pytest

        @pytest.mark.battle_sim
        def test_no_worker():
            assert True
    """})
    assert proc.returncode != 0, out(proc)
    assert "1 passed" in proc.stdout
    assert ("test_case4.py::test_no_worker is marked battle_sim but never reached the battle worker in this "
            "run") in proc.stdout, out(proc)


def test_unmarked_user_of_shared_fixture_fails_the_session(tmp_path):  # case 5
    proc = run_inner(tmp_path, {"test_case5.py": f"""
        import subprocess
        import pytest

        @pytest.fixture(scope="module")
        def pool():
            {START_WORKER}
            return "pool"

        @pytest.mark.battle_sim
        def test_first(pool):
            assert pool

        def test_second_unmarked(pool):
            assert pool
    """})
    assert proc.returncode != 0, out(proc)
    assert "2 passed" in proc.stdout, out(proc)
    assert ("test_case5.py::test_second_unmarked uses fixture test_case5.py::pool, which starts the battle "
            "worker, but is not marked battle_sim") in proc.stdout, out(proc)
    assert "test_case5.py::test_first: fixture test_case5.py::pool" not in proc.stdout  # own start (setup)
    assert "test_case5.py::test_first: own start" in proc.stdout


def test_other_node_program_is_not_logged(tmp_path):  # case 6
    proc = run_inner(tmp_path, {"test_case6.py": """
        import subprocess

        def test_node_e():
            subprocess.run(["node", "-e", "1"], check=True, timeout=60)
            subprocess.run(["node", "sim/seeds.mjs", "--help"], timeout=60)
    """})
    assert proc.returncode == 0, out(proc)
    assert "0 battle worker starts" in proc.stdout, out(proc)


def test_fixtures_with_the_same_name_are_kept_apart(tmp_path):  # case 7
    proc = run_inner(tmp_path, {
        "test_case7a.py": f"""
            import subprocess
            import pytest

            @pytest.fixture(scope="module")
            def pool():
                {START_WORKER}
                return "a"

            @pytest.mark.battle_sim
            def test_a(pool):
                assert pool == "a"
        """,
        "test_case7b.py": """
            import pytest

            @pytest.fixture(scope="module")
            def pool():
                return "b"

            def test_b(pool):
                assert pool == "b"
        """,
    })
    assert proc.returncode == 0, out(proc)
    assert "under-marked 0" in proc.stdout, out(proc)


def test_start_outside_any_test_fails_the_session(tmp_path):  # case 8
    proc = run_inner(tmp_path, {"test_case8.py": f"""
        import subprocess

        {START_WORKER}

        def test_nothing():
            assert True
    """})
    assert proc.returncode != 0, out(proc)
    assert "the battle worker was started outside any test (fixture none)" in proc.stdout, out(proc)


def test_positive_control_without_detection_the_unmarked_start_passes(tmp_path):  # case 9
    proc = run_inner(tmp_path, {"test_case9.py": UNMARKED_START}, plugin=False)
    assert proc.returncode == 0, out(proc)
    assert "battle split" not in proc.stdout


def test_known_battle_test_carries_the_mark(request):
    items = [i for i in request.session.items if i.nodeid.startswith("tests/integration/test_worker.py::")]
    if not items:  # this file run alone: collect test_worker.py without running it
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "--collect-only", "-q", "-m", "battle_sim",
             "tests/integration/test_worker.py"],
            cwd=REPO_ROOT, capture_output=True, text=True, timeout=120)
        assert proc.returncode == 0, out(proc)
        assert "tests/integration/test_worker.py::" in proc.stdout, out(proc)
        assert "deselected" not in proc.stdout, out(proc)
    else:
        assert all(i.get_closest_marker("battle_sim") for i in items)


def test_worker_pool_default_command_uses_bare_node():
    # Read the default without starting workers (WorkerPool.__init__ starts them).
    from platsim.sim import pool

    source = textwrap.dedent(inspect.getsource(pool.WorkerPool.__init__))
    defaults = [node for node in ast.walk(ast.parse(source))
                if isinstance(node, ast.BoolOp) and ast.unparse(node).startswith("command or")]
    assert len(defaults) == 1, source
    assert ast.unparse(defaults[0].values[1]) == "['node', str(WORKER_SCRIPT)]"
    assert pool.WORKER_SCRIPT.resolve() == (REPO_ROOT / "sim" / "worker.mjs").resolve()


def test_stand_in_is_first_on_path():
    assert os.environ["PATH"].split(os.pathsep)[0] == str(SHIM_DIR)
    assert Path(os.environ["PLATSIM_REAL_NODE"]).name == "node"
    assert Path(os.environ["PLATSIM_REAL_NODE"]).parent != SHIM_DIR
