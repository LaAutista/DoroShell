# Panel dependency selection

The panel remains pinned to LXQt Panel **2.4.1**, commit
`cffb0cd29c6ce0360356006ce727a9b01347e062`. Its upstream CMake requires liblxqt
**at least 2.4.0**, not exactly 2.4.0. Installed liblxqt 2.5 explicitly requires
build-tools 2.5. The earlier builder always placed privately built tools 2.4 first
in CMake's search path, causing configuration to fail on an otherwise usable
2.5 development environment.

The builder now selects an official, commit-pinned tools release from standard
generated liblxqt development metadata **before downloads or work-directory
creation**:

| liblxqt family | Required/reviewed tools | Exact tools commit |
| --- | --- | --- |
| 2.4.x | 2.4.0 | `0f56cd400d2afcb6f16d4ca88538ed716439c2c2` |
| 2.5.x | 2.5.0 | `ca90f9b0c5eedc3ab89d4031811dff833392bf3b` |

Changed upstream tags, unknown families, a different tools requirement, malformed,
missing or contradictory metadata and missing prerequisite executables are refused.
The initial check also queries the declared Qt Widgets/DBus/Xdg minima and GIO
Unix headers with pkg-config. It does not replace CMake's remaining compiler,
architecture, Qt private-header, KF6, plugin and ABI/dependency checks. A metadata
check alone is not a successful native build or a future-version guarantee.

```sh
python panel/build.py --check-dependencies
python panel/build.py --work /absolute/empty/build-directory
# An explicitly prepared liblxqt installation, without changing host packages:
python panel/build.py --lxqt-prefix /absolute/prepared/prefix --check-dependencies
python panel/build.py --lxqt-prefix /absolute/prepared/prefix --work /absolute/new-build
```

An explicit prefix takes priority; otherwise a standard liblxqt CMake directory
in `CMAKE_PREFIX_PATH` is selected first, followed by pkg-config's `lxqt` prefix.
Supported prefix layouts are `share/cmake/lxqt`, `lib/cmake/lxqt` or
`lib64/cmake/lxqt`; ambiguous layouts are refused. Linux environment prefix lists
are colon-separated. Paths may contain spaces, but must be absolute and contain
no CMake semicolon separator or control characters. A prepared dependency stack
may also need its own `PKG_CONFIG_PATH` for the declared Qt dependencies.

The selected library and newly built tools are explicitly bound through their
CMake package directories. Other CMake checks remain enabled. No host dependency
is downgraded, copied into the system, or silently replaced. This builder does not
run a package manager or authentication command. The existing bootstrap/deploy
package offer remains a separate, explicitly approved stage.

`deploy.py` uses the same detector and includes the selected prefix, versions and
metadata hashes in its native build cache key. Changing that evidence requires a
new private build; unchanged completed builds retain the existing full runtime
hash/mode checks. No new installed toolkit helper or ownership schema is required:
native builds run from the retained complete source checkout, not the reduced
Settings toolkit. Module preferences, selection, activation and rollback are unchanged.

Every attempted build records `build-provenance.json` in its work directory:
library/config identity, selected tools tag/commit, panel pin, ordered patch hashes
and building/failed-or-interrupted/complete status. Successful runtime notices
include the same record. Dependency metadata is rechecked before panel CMake
configuration. Failures retain their work directory and diagnostics; retry in a
new empty directory after correcting dependencies. A record left `building` by
an uncatchable interruption is incomplete, never a successful deployment proof.
Provenance contains local build paths: keep it private, not in source publication.

## Evidence and limits

The published builder was reproduced failing against liblxqt 2.5: CMake requested
tools 2.5 but found the private 2.4 helper. The corrected builder completed all
1,367 native steps against the installed 2.5 library and tools 2.5, then installed
only into its private prefix/DESTDIR. Only Git transfer used local pinned clones;
revision verification, patching, CMake, compilation, linking and staging were real.
The official tools 2.5 clone was acquired separately and its exact commit verified.
No executable was run and no personal profile or system package was installed.

The complete disposable/offscreen suite passes **564 tests in 38.089s**.
Unit fixtures cover both families, later patch numbers with the same reviewed
tools requirement, missing/invalid/ambiguous metadata, changed dependencies/tags,
failure/cancellation, provenance, cache reuse/invalidation and no-write CLI errors.
Actual read-only checks also selected the saved prepared 2.4 prefix correctly;
the earlier independently verified full 2.4 builds remain historical evidence.
Clean-OS one-command installation, normal login, panel runtime and other future
LXQt/library/tool combinations remain unverified. No CMake version check is bypassed.

Primary sources: [pinned panel requirements](https://github.com/lxqt/lxqt-panel/blob/cffb0cd29c6ce0360356006ce727a9b01347e062/CMakeLists.txt),
[liblxqt 2.5 requirements](https://github.com/lxqt/liblxqt/blob/2.5.0/CMakeLists.txt),
[generated dependency contract](https://github.com/lxqt/liblxqt/blob/2.5.0/cmake/lxqt-config.cmake.in),
[official tools 2.5 release](https://github.com/lxqt/lxqt-build-tools/releases/tag/2.5.0).
