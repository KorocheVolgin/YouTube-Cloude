# Licensing and distribution audit — status: incomplete

This document records review items for this repository snapshot. It is not a
legal opinion or a certification that the project or any release complies
with all applicable licenses.

## Project license scope

The `patch-1` branch adds the text of GPL-3.0 in `LICENSE`. The code history
contains earlier contributions from multiple revisions/authors. Before
applying GPL-3.0 to the entire codebase, establish that the person granting
that license holds the necessary rights for each retained contribution, or
obtain permission from the relevant authors. A license-file commit cannot on
its own change the license of code whose copyright belongs to someone else.

Record provenance, author, source revision, applicable license/permission
and affected paths. For code whose permission cannot be established, keep
its status explicit and do not distribute it as though GPL-3.0 permission
were verified. Removing a license file is not itself a cure; resolve the
underlying rights and communicate any changed scope clearly.

## Third-party code and build outputs

- The Kivy and FreeType recipes and Kivy patches should be compared against
  their python-for-android sources. Preserve the applicable upstream notices;
  a recipe's license does not license the native library it builds.
- The release workflow bundles FFmpeg/ffprobe. The Linux static build source
  used by the workflow identifies its builds as GPLv3. Record the exact
  binary version/configuration and provide all applicable notices and
  corresponding source. Determine the Windows/macOS build provenance and
  terms independently.
- Qt/PySide/Shiboken, Python, NumPy, Pillow, PyCryptodome, Reed-Solomon and
  other dependencies need version-specific review. Inspect the libraries
  actually included in each desktop artifact, not just the host dependency
  list. For LGPL components, verify the applicable replacement/relinking
  route and source obligations.
- Android needs an inventory of the APK's target Python/native libraries.
  A desktop/host package inventory is not sufficient.
- Previously published binaries need their own inspection. Source changes
  or a new notice file do not retroactively alter what was distributed.

## Before publishing releases

- [ ] Establish provenance and license permission for all retained project code.
- [ ] Confirm the intended license scope and correct README/package metadata.
- [ ] Inventory exact dependency versions and notices for each target artifact.
- [ ] Review FFmpeg/ffprobe binaries, configuration, notices and source delivery.
- [ ] Inspect final desktop and Android artifacts for native libraries and
  verify the corresponding license obligations.
- [ ] Inspect earlier release assets and determine whether corrections or
  additional source/notice delivery are needed.

Until these items are resolved, describe the project license scope and
release status as under review rather than asserting blanket compliance.
