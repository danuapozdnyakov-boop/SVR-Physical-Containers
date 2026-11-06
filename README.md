# SVRPhysicalContainers 0.2.10 Beta — source

Source matching the 0.2.10 Beta Nexus release. This repository is for code review and development; it is not an installable mod.

## Layout
- `SVRPhysicalContainers/`: plugin source, model profiles, supporting headers and policy/math tests.
- `third-party/`: bundled upstream code and dependency notices used by the source build.
- `HiggsInterface.h`: HIGGS mod interface.
- `CMakeLists.txt`: CMake build configuration.
- `release-manifest.json`: shipped runtime and mesh hashes.
- `COPYING.txt`, `EXCEPTIONS.md`: license terms and CommonLib exceptions.

## Build
Windows x64; MSVC with C++23 support and Windows SDK; CMake 3.24+.
Prepare a vcpkg x64-windows prefix containing DirectXTK and Xbyak (including their CMake config files).
The remaining bundled dependencies are in third-party/. HIGGS is required at runtime, not shipped as a DLL.

From an x64 Visual Studio developer shell:

    cmake -S . -B build -A x64 -DDEPS="C:/vcpkg/installed/x64-windows"
    cmake --build build --config Release

Adjust the dependency path for your machine. A clean-machine build of this release CMake setup has not been independently verified; the supplied DLL was built from the matching plugin source using the author's MSVC environment. Do not assume identical executable hashes across compiler versions.

## Scope and validation
Runtime: Skyrim VR 1.4.15 / SKSEVR. See README.txt and the source for requirements and limitations.
Automated checks cover the relevant mathematical/policy logic and VR runtime query; they do not prove all behavior in a headset or on other modlists.
Historical asset scripts may describe earlier generation stages. The release manifest identifies the actual shipped assets.
The plugin's own graphics compatibility generator has a separate repository.

## License and third-party assets
GPL-3.0-or-later, subject to the included dependency notices and CommonLib exceptions.
Bethesda mesh/texture rights remain separate from the code license. Third-party game/graphics mods and their DLLs are not relicensed by this repository.
