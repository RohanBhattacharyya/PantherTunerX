# Third-party notices

Panther Tuner X application source is MIT licensed. This does not relicense vendor libraries, device firmware, trademarks, documentation, or assets.

* **Phoenix 6 26.3.0**, CTR Electronics: proprietary SDK, installed as a PyPI dependency. The Python wheel's source references `CTRE_LICENSE.txt` but its metadata does not include that file. The exact-version [official C++ headers archive](https://maven.ctr-electronics.com/release/com/ctre/phoenix6/wpiapi-cpp/26.3.0/wpiapi-cpp-26.3.0-headers.zip) supplies it; a copy is preserved at [docs/licenses/CTRE_LICENSE.txt](docs/licenses/CTRE_LICENSE.txt) and included in frozen bundles. Users and redistributors must review and comply with that license. No vendor binaries are committed here. Review redistribution requirements before publishing bundles.
* **PySide6 / Qt**: LGPLv3/GPLv3/commercial, as applicable to individual modules. This app uses Qt Core, GUI and Widgets, and uses dynamic libraries. Preserve Qt notices and users' rights to replace LGPL libraries when distributing bundles. See https://doc.qt.io/qtforpython-6/licenses.html.
* **pyqtgraph**: MIT. **NumPy**: BSD-3-Clause, with additional bundled-component notices. **HTTPX**: BSD-3-Clause. Their licenses accompany installed packages.
* **PyInstaller**: GPLv2-or-later with bootloader exception. Build tool only; preserve its exception and notices as required.

CTRE's archived MIT-licensed diagnostics client was inspected as protocol reference. Its implementation, assets and binaries were not copied into the app. The current SDK shared library was inspected locally (strings and disassembly) and its diagnostics server exercised in vendor simulation to verify wire behavior. No Tuner X installer assets or proprietary executable code are included in this repository.

Application branding is text and Qt styling; the Panther logo has been removed. Reference screenshots remain on CTRE's documentation servers and are linked in research notes.

**Official device product images:** CTR Electronics and the respective product/photography owners retain copyright and trademarks in the product images bundled under `src/panther_tuner/assets/devices/`. They were downloaded from the official CTR Electronics store's CDN for device identification, at the user's request. These images are third-party assets, **not covered by the application's MIT license**. No separate permissive image license is asserted. Exact product pages and image URLs are recorded in that directory's `sources.json`; the application loads them locally without contacting the store. Talon FX artwork is representative of the device family and does not identify a connected motor's exact mechanical variant.
