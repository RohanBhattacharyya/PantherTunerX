"""Package layout and ELF validation without building the full GUI for each test."""

import importlib.util
import struct
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "linux", reason="Native Linux package staging")

_spec = importlib.util.spec_from_file_location(
    "package_linux", Path(__file__).parents[1] / "tools/package_linux.py"
)
packaging = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(packaging)


@pytest.fixture
def bundle(tmp_path):
    root = tmp_path / "bundle"
    (root / "_internal").mkdir(parents=True)
    header = bytearray(20)
    header[:6] = b"\x7fELF\x02\x01"
    struct.pack_into("<H", header, 18, 62)
    (root / "PantherTunerX").write_bytes(header)
    (root / "PantherTunerX").chmod(0o755)
    (root / "_internal/libexample.so.1").write_bytes(b"shared-library")
    (root / "_internal/libexample.so").symlink_to("libexample.so.1")
    (root / "licenses").mkdir()
    (root / "licenses/CTRE_LICENSE.txt").write_text("Vendor notice")
    return root


def test_staging_preserves_executables_symlinks_and_notices(bundle, tmp_path):
    dest = tmp_path / "package"
    packaging.stage(bundle, dest)
    binary = dest / "opt/panther-tuner-x/PantherTunerX"
    assert binary.stat().st_mode & 0o777 == 0o755
    library = dest / "opt/panther-tuner-x/_internal/libexample.so"
    assert library.is_symlink()
    assert library.read_bytes() == b"shared-library"
    launcher = dest / "usr/bin/panther-tuner"
    assert launcher.stat().st_mode & 0o777 == 0o755
    assert 'exec /opt/panther-tuner-x/PantherTunerX "$@"' in launcher.read_text()
    desktop = dest / "usr/share/applications/panther-tuner-x.desktop"
    assert "Exec=panther-tuner --simulate" in desktop.read_text()
    assert desktop.stat().st_mode & 0o777 == 0o644
    notices = dest / "usr/share/licenses/panther-tuner-x"
    assert (notices / "CTRE_LICENSE.txt").read_text() == "Vendor notice"
    assert (notices / "device-images-sources.json").is_file()
    assert (dest / "usr/share/doc/panther-tuner-x/installation.md").is_file()


def test_staging_never_overwrites_existing_files(bundle, tmp_path):
    dest = tmp_path / "occupied"
    dest.mkdir()
    (dest / "keep").write_text("unchanged")
    with pytest.raises(ValueError, match="empty"):
        packaging.stage(bundle, dest)
    assert (dest / "keep").read_text() == "unchanged"


def test_staging_rejects_recursive_destination(bundle):
    with pytest.raises(ValueError, match="separate"):
        packaging.stage(bundle, bundle / "package")


def test_staging_requires_vendor_notices(bundle, tmp_path):
    (bundle / "licenses/CTRE_LICENSE.txt").unlink()
    with pytest.raises(ValueError, match="license"):
        packaging.stage(bundle, tmp_path / "package")


def test_architecture_comes_from_elf_not_build_host(bundle):
    assert packaging.bundle_architecture(bundle) == ("amd64", "x86_64")
    header = bytearray((bundle / "PantherTunerX").read_bytes())
    struct.pack_into("<H", header, 18, 183)
    (bundle / "PantherTunerX").write_bytes(header)
    assert packaging.bundle_architecture(bundle) == ("arm64", "aarch64")


def test_rejects_non_linux_bundle(bundle):
    (bundle / "PantherTunerX").write_bytes(b"Windows executable")
    with pytest.raises(ValueError, match="ELF"):
        packaging.bundle_architecture(bundle)


def test_package_declares_actual_bundled_glibc_floor(bundle):
    assert packaging.glibc_floor(bundle) == "2.35"
    (bundle / "_internal/library.so").write_bytes(b"\x7fELF\0GLIBC_2.39\0GLIBC_2.44\0GLIBC_2.9")
    (bundle / "README").write_text("GLIBC_2.99 is text, not an ELF requirement")
    assert packaging.glibc_floor(bundle) == "2.44"
