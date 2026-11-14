#!/usr/bin/env bash
# Download a complete revision first. Never execute a partially downloaded script.
set -euo pipefail
main() (
    local channel=development ref=main apply=false arg root tmp revision destination
    local -a forwarded=()
    while (($#)); do
        case "$1" in
            --channel) channel=${2:?Missing channel}; shift 2 ;;
            --ref) ref=${2:?Missing revision}; shift 2 ;;
            --apply) apply=true; forwarded+=(--apply); shift ;;
            --plan) shift ;;
            *) forwarded+=("$1"); shift ;;
        esac
    done
    case "$channel" in development) ;; stable) ref=stable ;; *) echo 'Choose development or stable' >&2; return 2 ;; esac
    [[ "$ref" =~ ^[A-Za-z0-9][A-Za-z0-9._/-]*$ && "$ref" != *..* ]] || { echo 'Invalid revision' >&2; return 2; }
    [[ $EUID != 0 ]] || { echo 'Run as your normal desktop user, not root.' >&2; return 1; }
    if ! command -v git >/dev/null || ! command -v python3 >/dev/null; then
        if ! "$apply"; then echo 'Install prerequisites with sudo pacman -Syu --needed git python, or use --apply.'; return 1; fi
        command -v pacman >/dev/null || { echo 'Arch/pacman required' >&2; return 1; }
        echo 'Git/Python are missing. pacman will show a full-system update for approval.'
        sudo pacman -Syu --needed git python
    fi
    # Existing installers use the default XDG layout; do not silently install elsewhere.
    root="$HOME/.local/share/doroshell/sources"
    python3 - "$root" <<'PY'
import pathlib,sys
p=pathlib.Path(sys.argv[1]); home=pathlib.Path.home()
for part in [p,*p.parents]:
    if part.is_symlink(): raise SystemExit('Refusing symlink in source directory')
if not p.is_relative_to(home): raise SystemExit('Source directory outside home')
PY
    mkdir -p "$root"
    tmp=$(mktemp -d "$root/.download-XXXXXXXX")
    trap '[[ -z ${tmp:-} ]] || rm -rf -- "$tmp"' EXIT
    git -C "$tmp" init -q
    git -C "$tmp" remote add origin https://github.com/LaAutista/DoroShell.git
    if command -v gh >/dev/null && gh auth status --hostname github.com >/dev/null 2>&1; then
        # Private repository: use the authorized CLI without changing Git configuration.
        git -C "$tmp" -c credential.helper= -c 'credential.helper=!gh auth git-credential' fetch --depth=1 origin "$ref"
    else
        git -C "$tmp" fetch --depth=1 origin "$ref"
    fi
    git -C "$tmp" checkout --detach -q FETCH_HEAD
    revision=$(git -C "$tmp" rev-parse HEAD)
    [[ -f "$tmp/deploy.py" ]] || { echo 'This revision predates the portable installer; choose development or a newer release.' >&2; return 1; }
    python3 "$tmp/source_release.py"
    if [[ "$channel" == stable ]]; then
        python3 - "$tmp/release.json" <<'PY'
import json,sys
if json.load(open(sys.argv[1]))['channel'] != 'stable': raise SystemExit('This tag is not declared stable')
PY
    fi
    destination="$root/$revision"
    if [[ -e "$destination" ]]; then
        [[ ! -L "$destination" && -d "$destination/.git" ]] || { echo 'Conflicting source path' >&2; return 1; }
        [[ $(git -C "$destination" rev-parse HEAD) == "$revision" && -z $(git -C "$destination" status --porcelain) ]] || { echo 'Existing source has local edits; preserving it.' >&2; return 1; }
        python3 "$destination/source_release.py"
    else
        mv -- "$tmp" "$destination"
        tmp=''
    fi
    python3 "$destination/deploy.py" "${forwarded[@]}"
)
main "$@"
