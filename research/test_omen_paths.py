"""omen_paths: worktrees find the main checkout's data_archive; OMEN_DATA_DIR overrides."""
import subprocess
import sys
import tempfile
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import omen_paths


@pytest.fixture
def tmp_path():
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


def _git(*a, cwd):
    subprocess.run(["git", *a], cwd=cwd, check=True, capture_output=True)


def test_env_override_wins(tmp_path):
    assert omen_paths.data_archive_dir(tmp_path, {"OMEN_DATA_DIR": "X:/data"}) == Path("X:/data")


def test_local_dir_used_when_present(tmp_path):
    (tmp_path / "data_archive").mkdir()
    assert omen_paths.data_archive_dir(tmp_path, {}) == tmp_path / "data_archive"


def test_linked_worktree_resolves_to_main_checkout(tmp_path):
    main = tmp_path / "main"
    main.mkdir()
    _git("init", "-q", cwd=main)
    _git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "--allow-empty", "-m", "i", cwd=main)
    (main / "data_archive").mkdir()
    wt = tmp_path / "wt"
    _git("worktree", "add", "-q", "-b", "b", str(wt), cwd=main)
    assert not (wt / "data_archive").exists()
    got = omen_paths.data_archive_dir(wt, {})
    assert got.resolve() == (main / "data_archive").resolve()


def test_default_when_nothing_exists(tmp_path):
    assert omen_paths.data_archive_dir(tmp_path, {}) == tmp_path / "data_archive"


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-q"]))

