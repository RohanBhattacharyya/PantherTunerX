import importlib.util
import sys
import tarfile
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location(
    "archive_bundle", Path(__file__).parents[1] / "tools/archive_bundle.py"
)
archive = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(archive)


@pytest.mark.skipif(sys.platform == "win32", reason="Unix framework links and executable modes")
@pytest.mark.parametrize("system,folder", [("linux", "PantherTunerX"), ("darwin", "PantherTunerX.app")])
def test_archive_preserves_unix_executable_and_relative_links(tmp_path, system, folder):
    root = tmp_path / folder
    root.mkdir()
    executable = root / "PantherTunerX"
    executable.write_text("#!/bin/sh\n")
    executable.chmod(0o755)
    (root / "library").symlink_to("PantherTunerX")
    result = archive.archive_bundle(tmp_path, system, "arm64")
    with tarfile.open(result) as contents:
        assert contents.getmember(f"{folder}/PantherTunerX").mode & 0o111
        link = contents.getmember(f"{folder}/library")
        assert link.issym()
        assert link.linkname == "PantherTunerX"
