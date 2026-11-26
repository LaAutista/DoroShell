#!/usr/bin/env bash
# Minimal compiler entry point for both the downloaded script and a checkout.
set -eu
d=$(mktemp -d)
trap 'rm -rf -- "$d"' EXIT
if ! command -v c++ >/dev/null; then
    [[ $(uname -m) == x86_64 ]] || { echo 'The prebuilt bootstrap requires x86_64. Install a C++20 compiler to build from source.' >&2; exit 1; }
    curl --fail --location --silent --show-error --proto '=https' https://github.com/LaAutista/DoroShell/releases/download/v0.3.0-rc.1/doroshell-bootstrap-linux-x86_64 -o "$d/doroshell-maintenance"
    (cd "$d" && sha256sum --check --status <<< 'c3cf2e7fcddc01b0f12bcd38a6a0f071c17961745a88725a837092e5133ced6d  doroshell-maintenance') || { echo 'The downloaded native bootstrap failed verification.' >&2; exit 1; }
    chmod 700 "$d/doroshell-maintenance"
    "$d/doroshell-maintenance" bootstrap "$@"
    exit
fi
mkdir -p -- "$d/native/maintenance" "$d/native/compatibility"
checkout=$(dirname -- "$0")
for src in native/maintenance/main.cpp native/compatibility/packages.hpp; do
    if [[ -f "$checkout/$src" && -O "$checkout/$src" ]]; then
        cp -- "$checkout/$src" "$d/$src"
    else
        curl --fail --location --silent --show-error --proto '=https' "https://raw.githubusercontent.com/LaAutista/DoroShell/main/$src" -o "$d/$src"
    fi
done
(cd "$d" && sha256sum --check --status <<'SUMS'
3cec79fa9dff6c6673dffb65ba03af08c2c4f1474c5572bbacbed0afcc5ffdf6  native/maintenance/main.cpp
ac87a04818c8823e7453f5815f3b8a714deb9b752287b12bdd2b0dac9e5db0a6  native/compatibility/packages.hpp
SUMS
) || { echo 'The native bootstrap source changed. Download the current bootstrap again.' >&2; exit 1; }
c++ -std=c++20 -O1 "$d/native/maintenance/main.cpp" -o "$d/doroshell-maintenance"
"$d/doroshell-maintenance" bootstrap "$@"
