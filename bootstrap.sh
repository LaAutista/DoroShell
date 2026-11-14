#!/usr/bin/env bash
# Download a complete revision first. Never execute a partially downloaded script.
set -euo pipefail
main() (
    local channel=development ref=main apply=false allow_packages=true arg root tmp revision destination
    local -a forwarded=() missing=()
    while (($#)); do
        case "$1" in
            --channel) channel=${2:?Missing channel}; shift 2 ;;
            --ref) ref=${2:?Missing revision}; shift 2 ;;
            --apply) apply=true; forwarded+=(--apply); shift ;;
            --no-packages) allow_packages=false; forwarded+=(--no-packages); shift ;;
            --plan) shift ;;
            *) forwarded+=("$1"); shift ;;
        esac
    done
    case "$channel" in development) ;; stable) ref=stable ;; *) echo 'Choose development or stable' >&2; return 2 ;; esac
    [[ "$ref" =~ ^[A-Za-z0-9][A-Za-z0-9._/-]*$ && "$ref" != *..* ]] || { echo 'Invalid revision' >&2; return 2; }
    [[ $EUID != 0 ]] || { echo 'Run as your normal desktop user, not root.' >&2; return 1; }
    for arg in git python3; do
        command -v "$arg" >/dev/null || missing+=("$arg")
    done
    if ((${#missing[@]})); then
        printf 'Missing acquisition commands: %s\n' "${missing[*]}" >&2
        echo 'Prerequisite plan: sudo pacman -Syu --needed git python' >&2
        echo 'This may update the whole system before layout validation. No DoroShell configuration is written at this step.' >&2
        if ! "$apply" || ! "$allow_packages"; then
            echo 'Plan only or --no-packages; no packages changed. Use --apply without --no-packages to review pacman approval, or run the prerequisite command separately.' >&2
            return 1
        fi
        command -v sudo >/dev/null && command -v pacman >/dev/null || {
            echo 'Automatic prerequisites require sudo and Arch pacman. No alternative or privileged shell is attempted.' >&2; return 1;
        }
        echo "Review pacman's full-system update prompt; decline it to cancel." >&2
        sudo pacman -Syu --needed git python
        command -v git >/dev/null && command -v python3 >/dev/null || {
            echo 'Git/Python are still unavailable after the prerequisite command; stopping before download.' >&2; return 1;
        }
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
    # Public source needs no account, CLI authentication or credential helper.
    GIT_TERMINAL_PROMPT=0 git -C "$tmp" -c credential.helper= fetch --depth=1 origin "$ref"
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
