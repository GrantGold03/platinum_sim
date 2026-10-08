"""Optimizer resume is refused across code/data versions (optimizer/run.py _State; platsim/version.py).

A stand-in pool supplies the worker hello; the ledger, species resolution and the optimization body
(`_run`) are stubs, so no battle is simulated: this checks only the checkpoint fingerprint logic and its wiring.
"""

from __future__ import annotations

import json

import pytest

from platsim import version
from platsim.optimizer import run as R
from platsim.optimizer.api import InvalidRequest, OptimizeRequest

SPECIES = ("infernape", "staraptor", "luxray", "garchomp", "gyarados", "gardevoir")
HELLO = {"sim_code_hash": "sha256:" + "a" * 64, "node_version": "v22.0.0", "decomp_commit": "d", "showdown_commit": "s",
         "decomp_data_hash": "sha256:x", "divergence_ledger_version": "v1", "divergence_patches_applied": 5,
         "pp_restore_between_battles": False, "policies": [], "opponent_policies": []}


class StubPool:
    hello = dict(HELLO)

    def __init__(self, workers=None):
        self.closed = False

    def close(self):
        self.closed = True


@pytest.fixture
def stubbed(monkeypatch):
    calls = []

    def fake_run(req, preset, led, consts, out, state, pool, prog):
        calls.append(out)
        state.done("calibrate", {"stub": True})
        return False

    monkeypatch.setattr("platsim.sim.pool.WorkerPool", StubPool)
    # the ledger is not needed here (run_optimization only asks it for a legality-options view)
    monkeypatch.setattr("platsim.availability.ledger.build_ledger",
                        lambda: type("NoLedger", (), {"with_options": lambda self, o: None})())
    monkeypatch.setattr(R.C, "resolve_species", lambda species, led: [f"SPECIES_{s.upper()}" for s in species])
    monkeypatch.setattr(R, "_run", fake_run)
    StubPool.hello = dict(HELLO)
    return calls


def _req(out, **kw):
    return OptimizeRequest(species=SPECIES, budget="quick", seed="resume-test", workers=1, out_dir=out, **kw)


def test_state_records_full_fingerprint_and_resumes_when_unchanged(tmp_path, stubbed):
    out = tmp_path / "o"
    R.run_optimization(_req(out))
    st = json.loads((out / "state.json").read_text())
    assert st["code"] == version.code_fingerprint(HELLO)
    assert set(version.CODE_KEYS) <= set(st["code"])
    assert st["stages"]["calibrate"] == {"stub": True}
    R.run_optimization(_req(out))  # same code: resumes (no error)
    assert len(stubbed) == 2


@pytest.mark.parametrize("key,value", [("sim_code_hash", "sha256:" + "b" * 64), ("node_version", "v23.0.0"),
                                       ("decomp_data_hash", "sha256:y"), ("divergence_ledger_version", "v2")])
def test_resume_refused_when_worker_fingerprint_differs(tmp_path, stubbed, key, value):
    out = tmp_path / "o"
    R.run_optimization(_req(out))
    before = (out / "state.json").read_text()
    StubPool.hello = dict(HELLO, **{key: value})
    with pytest.raises(InvalidRequest, match=f"different code/data.*{key}.*--force-new"):
        R.run_optimization(_req(out))
    assert (out / "state.json").read_text() == before  # the checkpoint is left untouched
    assert len(stubbed) == 1


def test_resume_refused_when_platsim_code_differs(tmp_path, stubbed):
    out = tmp_path / "o"
    R.run_optimization(_req(out))
    st = json.loads((out / "state.json").read_text())
    st["code"]["platsim_code_hash"] = "sha256:" + "0" * 64  # checkpoint written by other Python code
    (out / "state.json").write_text(json.dumps(st))
    with pytest.raises(InvalidRequest, match="platsim_code_hash"):
        R.run_optimization(_req(out))


def test_legacy_state_without_code_fingerprint_is_refused(tmp_path, stubbed):
    out = tmp_path / "o"
    R.run_optimization(_req(out))
    st = json.loads((out / "state.json").read_text())
    del st["code"]
    (out / "state.json").write_text(json.dumps(st))
    with pytest.raises(InvalidRequest, match="no code fingerprint"):
        R.run_optimization(_req(out))


def test_repo_commit_change_alone_still_resumes(tmp_path, stubbed):
    out = tmp_path / "o"
    R.run_optimization(_req(out))
    st = json.loads((out / "state.json").read_text())
    st["code"]["repo_commit"] = "0" * 40
    (out / "state.json").write_text(json.dumps(st))
    R.run_optimization(_req(out))  # content hashes match: same code, resumed
    assert len(stubbed) == 2


def test_force_new_moves_old_checkpoint_aside(tmp_path, stubbed):
    out = tmp_path / "o"
    R.run_optimization(_req(out))
    old = (out / "state.json").read_text()
    (out / "result.json").write_text("{}")
    StubPool.hello = dict(HELLO, sim_code_hash="sha256:" + "b" * 64)
    R.run_optimization(_req(out, force_new=True))
    assert (out / "superseded-1" / "state.json").read_text() == old
    assert (out / "superseded-1" / "result.json").is_file() and not (out / "result.json").exists()
    assert json.loads((out / "state.json").read_text())["code"]["sim_code_hash"] == "sha256:" + "b" * 64


def test_different_job_in_out_dir_is_refused(tmp_path, stubbed):
    out = tmp_path / "o"
    R.run_optimization(_req(out))
    with pytest.raises(InvalidRequest, match="different optimize job"):
        R.run_optimization(OptimizeRequest(species=SPECIES, budget="quick", seed="other", workers=1, out_dir=out))
