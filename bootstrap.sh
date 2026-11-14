#!/usr/bin/env bash
# Download a complete revision first. Never execute a partially downloaded script.
set -euo pipefail
main() (
    local channel=development ref=main apply=false allow_packages=true arg root tmp revision destination
    local plan=false guidance=false remove=false recover=false help=false undo='' panel='' config_root=''
    local modules_set=false panel_module=false clipboard_module=false extra_clipboard=false config_module_count=0
    local module_count=0 extra_count=0
    local shortcut_module=false extra_shortcut=false replace_shortcut=false
    local -a forwarded=() missing=()
    invalid() { echo "Bootstrap arguments: $1. No prerequisites requested." >&2; exit 2; }
    # Pure shell syntax/action gate: runs before acquisition tools or authentication.
    # Layout, saved-state and ownership semantics still belong to deploy/profile.
    while (($#)); do
        case "$1" in
            --channel|--ref|--home|--theme|--panel|--config-root|--with|--undo)
                (($# >= 2)) && [[ -n "$2" && "$2" != -* && ! "$2" =~ [[:cntrl:]] ]] || invalid "Missing or invalid value for $1"
                case "$1" in
                    --channel) channel=$2 ;;
                    --ref) ref=$2 ;;
                    --panel) [[ "$2" =~ ^panel[1-9][0-9]*$ ]] || invalid 'Choose an existing panelN ID with --panel'; panel=$2 ;;
                    --config-root) [[ "$2" == /* && "$2" != / && "$2" != */ && "$2" != *//* && "$2" != */../* && "$2" != */.. && "$2" != */./* && "$2" != */. ]] || invalid "Configuration root must be an absolute canonical path"; config_root=$2 ;;
                    --theme) case "$2" in windows|polar|heretic|spring) ;; *) invalid 'Unknown theme' ;; esac ;;
                    --with) extra_count=$((extra_count+1)); case "$2" in clipboard) extra_clipboard=true ;; start-shortcut) extra_shortcut=true ;; wallpaper|wallpaper-glass|display) ;; *) invalid 'Unknown optional module' ;; esac ;;
                    --undo) [[ "$2" =~ ^[0-9]{8}T[0-9]{6}-[0-9a-f]{12}$ ]] || invalid 'Invalid undo transaction ID'; undo=$2 ;;
                esac
                case "$1" in --channel|--ref) ;; *) forwarded+=("$1" "$2") ;; esac
                shift 2 ;;
            --modules)
                forwarded+=(--modules); shift
                (($#)) && [[ "$1" != -* ]] || invalid 'Missing module list'
                modules_set=true; panel_module=false; clipboard_module=false; shortcut_module=false; config_module_count=0; module_count=0
                while (($#)) && [[ "$1" != -* ]]; do
                    case "$1" in
                        core|native-panel) panel_module=true ;;
                        clipboard) clipboard_module=true ;;
                        start-shortcut) shortcut_module=true ;;
                        single-desktop|snapping) config_module_count=$((config_module_count+1)) ;;
                        menu|theme|cursor|screenshots|maintenance|wallpaper|wallpaper-glass|display) ;;
                        *) invalid 'Unknown module' ;;
                    esac
                    module_count=$((module_count+1)); forwarded+=("$1"); shift
                done ;;
            --apply) apply=true; forwarded+=(--apply); shift ;;
            --replace-start-shortcut) replace_shortcut=true; forwarded+=(--replace-start-shortcut); shift ;;
            --no-packages) allow_packages=false; forwarded+=(--no-packages); shift ;;
            --plan) plan=true; shift ;;
            --prerequisites) guidance=true; forwarded+=(--prerequisites); shift ;;
            --remove) remove=true; forwarded+=(--remove); shift ;;
            --recover) recover=true; forwarded+=(--recover); shift ;;
            --help|-h) help=true; shift ;;
            *) invalid 'Unknown option or positional argument (use exact long options and separate values)' ;;
        esac
    done
    "$plan" && "$apply" && invalid '--plan cannot combine with --apply'
    if "$replace_shortcut"; then
        if "$guidance" || "$help" || "$remove" || [[ -n "$undo" ]]; then invalid 'Shortcut replacement cannot combine with guidance/help/remove/undo'; fi
        if ! "$shortcut_module" && ! "$extra_shortcut" && ! "$recover"; then invalid 'Explicitly select start-shortcut before choosing replacement'; fi
    fi
    if "$guidance" || "$help"; then
        if "$apply" || "$remove" || "$recover" || [[ -n "$undo" ]]; then invalid 'Guidance/help cannot combine with an action'; fi
    fi
    if [[ -n "$undo" ]] && { "$remove" || "$recover" || [[ -n "$panel" ]]; }; then invalid '--undo cannot combine with remove/recover/panel'; fi
    if [[ -n "$panel" ]] && "$modules_set" && ! "$panel_module" && ! "$recover"; then
        if "$remove" || { ! "$clipboard_module" && ! "$extra_clipboard"; }; then invalid '--panel requires the native-panel module'; fi
    fi
    if [[ -n "$config_root" ]]; then
        if "$guidance" || "$help" || [[ -n "$undo" || -n "$panel" ]]; then invalid 'Config root cannot combine with guidance/help/undo/panel'; fi
        if ((extra_count)) || { ! "$recover" && { ((module_count==0 || config_module_count!=module_count)); }; }; then invalid 'Config root requires only --modules snapping and/or single-desktop'; fi
    fi
    case "$channel" in development) ;; stable) ref=stable ;; *) invalid 'Choose development or stable' ;; esac
    [[ "$ref" =~ ^[A-Za-z0-9][A-Za-z0-9._/-]*$ && "$ref" != *..* ]] || invalid 'Invalid revision'
    if "$help"; then
        echo 'Usage: bash bootstrap.sh [--plan | --apply] [--no-packages] [--panel panelN]'
        echo 'Also: --modules NAME... --with NAME --theme NAME --home PATH --config-root PATH --channel development|stable --ref REV'
        echo 'Guidance: --prerequisites. Maintenance: --remove --recover --undo TRANSACTION. Use separate option values.'
        return 0
    fi
    [[ $EUID != 0 ]] || { echo 'Run as your normal desktop user, not root.' >&2; return 1; }
    for arg in git python3; do
        command -v "$arg" >/dev/null || missing+=("$arg")
    done
    if ((${#missing[@]})); then
        printf 'Missing acquisition commands: %s\n' "${missing[*]}" >&2
        echo 'Prerequisite plan: sudo pacman -Syu --needed git python' >&2
        echo 'This may update the whole system before layout validation. No DoroShell configuration is written at this step.' >&2
        if ! "$apply" || ! "$allow_packages"; then
            echo 'Plan/guidance only or --no-packages; no packages changed. Run the prerequisite command separately, or choose an installation with --apply without --prerequisites/--no-packages.' >&2
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
