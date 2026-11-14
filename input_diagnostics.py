#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Bounded, read-only Xorg configuration intent; never infer the effective scheme."""
from fnmatch import fnmatchcase
import os
from pathlib import Path
import shlex
import stat

CONFIG = Path('/etc/X11/xorg.conf')
DIRECTORIES = (Path('/etc/X11/xorg.conf.d'), Path('/usr/share/X11/xorg.conf.d'))
MAX_FILES, MAX_FILE, MAX_TOTAL = 64, 65536, 262144
SCHEMES = {'none', 'predictable', 'lightweight'}


def normalized(value):
    return value.lower().replace('_', '').replace(' ', '')


def parse_configuration(text):
    rules, issues, section, entries = [], set(), None, []
    for line in text.splitlines():
        try:
            tokens = shlex.split(line, comments=True)
        except ValueError:
            issues.add('malformed'); continue
        if not tokens: continue
        key = normalized(tokens[0])
        if key == 'section':
            if section is not None or len(tokens) != 2: issues.add('malformed')
            section = normalized(tokens[1]) if len(tokens) == 2 else 'unknown'; entries = []
        elif key == 'endsection':
            if section is None or len(tokens) != 1: issues.add('malformed')
            schemes = [values[1] for name, values in entries
                       if name == 'option' and len(values) == 2 and normalized(values[0]) == 'accelerationscheme']
            if schemes:
                if section != 'inputclass': issues.add('unsupported')
                elif len([v for k, v in entries if k == 'identifier' and len(v) == 1 and v[0]]) != 1:
                    issues.add('malformed')
                else: rules.append((entries, [normalized(s) for s in schemes]))
            section, entries = None, []
        elif section is not None:
            entries.append((key, tokens[1:]))
            if key in ('identifier','driver') and len(tokens) != 2: issues.add('malformed')
            if key == 'option' and len(tokens) not in (2,3): issues.add('malformed')
            if key == 'option' and tokens[1:] and normalized(tokens[1]) == 'accelerationscheme' and len(tokens) != 3:
                issues.add('malformed')
        elif key != '': issues.add('malformed')
    if section is not None: issues.add('malformed')
    # A malformed file cannot supply a trusted match, even if a subsection looked valid.
    return ([] if 'malformed' in issues else rules), issues


def read_configuration(config=CONFIG, directories=DIRECTORIES):
    """Read fixed standard locations as this user; no logs, /proc or privileged helper."""
    paths, issues, rules = [], set(), []
    try:
        config.lstat(); paths.append(config)
    except FileNotFoundError: pass
    except OSError: issues.add('unreadable')
    for directory in directories:
        try:
            if directory.is_symlink(): issues.add('unreadable'); continue
            with os.scandir(directory) as listing:
                for entry in listing:
                    if not entry.name.endswith('.conf'): continue
                    if len(paths) >= MAX_FILES: issues.add('bounded'); break
                    paths.append(Path(entry.path))
        except FileNotFoundError: pass
        except OSError: issues.add('unreadable')
    remaining = MAX_TOTAL
    for path in sorted(paths):
        fd = None
        try:
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            before = os.fstat(fd)
            if not stat.S_ISREG(before.st_mode): issues.add('unreadable'); continue
            limit = min(MAX_FILE, remaining)
            if before.st_size > limit: issues.add('bounded'); continue
            payload = os.read(fd, limit + 1); after = os.fstat(fd)
            remaining -= len(payload)
            if len(payload) > limit: issues.add('bounded'); continue
            if len(payload) != before.st_size or (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                issues.add('changed'); continue
            parsed, problems = parse_configuration(payload.decode('utf-8'))
            rules.extend(parsed); issues.update(problems)
        except UnicodeError: issues.add('malformed')
        except OSError: issues.add('unreadable')
        finally:
            if fd is not None: os.close(fd)
    return rules, issues


def rule_matches(entries, device):
    """Only resolve selectors whose facts the existing device inventory supplies."""
    unknown = False
    for name, values in entries:
        if name in ('identifier', 'driver'):
            if len(values) != 1: unknown = True
            continue
        if name == 'option': continue
        negative = name.startswith('nomatch')
        key = name[2:] if negative else name
        if len(values) != 1: unknown = True; continue
        parts = values[0].split('|')
        if not all(parts): unknown = True; continue
        if key == 'matchproduct': matched = any(part in device['name'] for part in parts)
        elif key == 'matchdevicepath': matched = any(fnmatchcase(device['node'], part) for part in parts)
        elif name in ('matchispointer', 'matchistouchpad'):
            value = normalized(values[0])
            if value not in ('on','true','yes','1','off','false','no','0'): unknown = True; continue
            actual = device['kind'] in ('mouse','touchpad') if name == 'matchispointer' else device['kind'] == 'touchpad'
            matched = actual == (value in ('on','true','yes','1'))
        else: unknown = True; continue
        if matched == negative: return False
    return None if unknown else True


def describe(device, evidence, profile_available=False):
    rules, issues = evidence; issues = set(issues); requested = set()
    for entries, schemes in rules:
        matches = rule_matches(entries, device)
        if matches is None: issues.add('unsupported')
        elif matches:
            if not set(schemes) <= SCHEMES: issues.add('malformed')
            else: requested.update(schemes)
    if len(requested) > 1: configuration = 'conflicting matching scheme requests; effective scheme unknown'
    elif requested: configuration = 'matching rule requests '+next(iter(requested))+' (intent only)'
    else: configuration = 'no matching scheme request established in standard locations'
    if issues: configuration += '; incomplete: '+', '.join(sorted(issues))
    runtime = 'available' if profile_available else 'unavailable for this device/driver'
    return ('Runtime acceleration-profile control: '+runtime+'.\n'
            'System configuration: '+configuration+'.\n'
            'Current Xorg initialization: unverified; XInput supplies no current-device/session proof. '
            'Historical logs and a missing profile do not prove acceleration is disabled.\n'
            'This page cannot change the system scheme. No physical motion test is performed.')
