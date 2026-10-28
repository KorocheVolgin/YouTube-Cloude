# Third-party notices and review status

The root `LICENSE` contains GPL-3.0 text, but that file does not grant rights
over third-party code or replace licenses and notices for dependencies.
Project provenance and the license scope remain under review; see
[the audit](docs/LICENSING_AUDIT.md).

## Components requiring artifact-specific review

| Component | Current concern | Review needed |
| --- | --- | --- |
| Kivy / python-for-android recipes and patches | Local recipe files and patches appear derived from python-for-android. | Preserve upstream copyright/license notices and verify source revision and modifications. |
| FFmpeg / ffprobe | The release workflow downloads or installs FFmpeg and bundles binaries. The Linux static supplier identifies its builds as GPLv3. | Record exact version, configuration, source, license texts and corresponding-source offer for every OS artifact. Review the actual Windows/macOS builds separately. |
| PySide6 / Qt / Shiboken6 | Optional Qt GUI dependencies; Qt components may use LGPLv3, GPLv3 or commercial terms. | Inventory the exact modules and native libraries shipped; include notices/source and satisfy applicable replacement/relinking conditions. |
| Python runtime and other dependencies | The dependency list includes packages with separate license terms; native wheels may include more components. | Generate a versioned inventory from each build environment and inspect final artifacts rather than relying on package metadata alone. |
| Android target packages | Host Python metadata is not an inventory of the APK. | Inspect target Python/native packages, notices, sources and applicable obligations in the built APK. |

This list is a review checklist, not a complete SBOM or a legal conclusion.
Do not assume a package's SPDX label alone supplies its complete notice text.
