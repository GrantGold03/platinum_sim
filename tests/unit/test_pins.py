import pytest

from platsim import pins


def test_real_repos_match_pins():
    # Positive control: the vendored repos on disk are at the pinned commits.
    pins.check_pins()


def test_wrong_commit_raises(monkeypatch):
    # Negative control: a mismatched pin must be detected.
    monkeypatch.setattr(pins, "DECOMP_COMMIT", "0" * 40)
    with pytest.raises(pins.PinError, match="expected pinned commit"):
        pins.check_pins()


def test_local_edit_raises(monkeypatch):
    # Negative control: a modified vendored tree must be detected.
    real_git = pins._git

    def fake_git(repo, *args):
        if args[:1] == ("status",) and repo == pins.DECOMP_ROOT:
            return " M src/pokemon.c\n"
        return real_git(repo, *args)

    monkeypatch.setattr(pins, "_git", fake_git)
    with pytest.raises(pins.PinError, match="local changes"):
        pins.check_pins()
