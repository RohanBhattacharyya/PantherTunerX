# Maintainer: Rohan Bhattacharyya <73246001+RohanBhattacharyya@users.noreply.github.com>
pkgname=panther-tuner-x-git
pkgver=0.1.0.r1.gd7f6a14
pkgrel=1
pkgdesc='Desktop diagnostics, configuration and plotting for CTRE Phoenix 6 devices'
arch=('x86_64' 'aarch64')
url='https://github.com/RohanBhattacharyya/PantherTunerX'
license=('MIT' 'Apache-2.0' 'LGPL-3.0-only' 'LicenseRef-CTRE' 'LicenseRef-Device-Images')
depends=('glibc>=2.35' 'gcc-libs' 'libglvnd' 'libx11' 'libxext' 'libxrender'
         'libxcb' 'libxkbcommon-x11' 'xcb-util-cursor' 'xcb-util-wm'
         'xcb-util-image' 'xcb-util-keysyms' 'xcb-util-renderutil'
         'fontconfig' 'freetype2' 'dbus' 'zlib' 'libusb')
makedepends=('git' 'uv>=0.13.1')
checkdepends=('desktop-file-utils')
provides=('panther-tuner-x')
conflicts=('panther-tuner-x')
# PyInstaller bundles contain private Qt/Python libraries and a bootloader archive.
# Do not strip them, publish their shared-library provides, or split debug symbols.
options=('!strip' '!debug')
_source_url="${PANTHER_SOURCE_URL:-https://github.com/RohanBhattacharyya/PantherTunerX.git}"
source=("PantherTunerX::git+${_source_url}#branch=main")
sha256sums=('SKIP')

_uv() {
    UV_CACHE_DIR="$srcdir/.uv-cache" \
    UV_PYTHON_INSTALL_DIR="$srcdir/.python" \
    UV_PYTHON_PREFERENCE=only-managed \
    uv "$@"
}

pkgver() {
    cd "$srcdir/PantherTunerX"
    printf '0.1.0.r%s.g%s' "$(git rev-list --count HEAD)" "$(git rev-parse --short HEAD)"
}

prepare() {
    cd "$srcdir/PantherTunerX"
    # The vendor SDK is not compatible with Arch's current system Python.
    # Fetch the pinned interpreter and hash-locked wheels into the build tree.
    _uv sync --frozen --python 3.12.14
}

build() {
    cd "$srcdir/PantherTunerX"
    _uv run --frozen --offline python tools/build.py
}

check() {
    cd "$srcdir/PantherTunerX"
    desktop-file-validate packaging/linux/panther-tuner-x.desktop
    # Integration tests need exclusive access to the vendor's port 1250.
    # These checks need neither a display nor a running CAN/diagnostics server.
    QT_QPA_PLATFORM=offscreen _uv run --frozen --offline pytest -q -m 'not integration'
    dist/PantherTunerX/PantherTunerX --help
}

package() {
    cd "$srcdir/PantherTunerX"
    _uv run --frozen --offline python tools/package_linux.py --format stage --destdir "$pkgdir"
}
