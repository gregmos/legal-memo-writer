#!/usr/bin/env python3
"""Resolve and manage user style profiles for memoforge.

Profiles live globally under:

    ~/.claude/plugin-data/memoforge/
    |-- default-profile.txt           # one line: name of the current default
    `-- profiles/
        `-- <profile-name>/
            |-- prose-style.md        # custom prose style (always present)
            |-- template.md           # custom template (may be absent if rules-only)
            |-- meta.json             # name, created_at, input_type, mode_binding, ...
            |-- rules.md              # copy of text-rules (if provided as input)
            `-- sources/              # copies of example memos (optional, audit)

The directory and the default file are read/written by `skills/style/SKILL.md`
(direct user actions) and read by `skills/memo/SKILL.md` (Phase 1.5 style
resolve). The schema for `meta.json` is documented inline below.

Sub-commands (invoked from Bash by the skill):

    list                                 # JSON array of profiles with metadata
    get-default                          # prints current default name, or empty
    set-default <name>                   # writes <name> to default-profile.txt
    clear-default                        # removes default-profile.txt
    validate-name <name>                 # exit 0 if name is valid, else exit 2
    validate-profile <name>              # checks required files + meta schema
    delete <name>                        # removes the profile directory
    read-meta <name>                     # prints meta.json content
    resolve-paths <name>                 # prints prose_style_path / template_path / ...
    ensure-dirs                          # mkdir -p profiles dir (no-op if exists)
    init-profile <name> <input_type> <mode> [--rules-provided]
                                         # creates an empty profile dir and meta stub
    write-meta <name> <json-string>      # atomically writes meta.json from JSON

Output is plain text or JSON depending on the sub-command. Errors go to stderr
with non-zero exit codes. The skill never assumes Python is the only way to
read these files — it can also Read the JSON directly. This script is the
canonical write path and the contract for name validation.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import datetime
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
#
# Default: ~/.claude/plugin-data/memoforge/
# Override via env var MEMOFORGE_PROFILES_HOME (used in tests and for users
# who want profiles stored elsewhere on disk). The env var, if set, replaces
# the entire plugin-data dir — `profiles/` and `default-profile.txt` live
# directly under it.

def plugin_data_dir() -> Path:
    override = os.environ.get("MEMOFORGE_PROFILES_HOME")
    if override:
        return Path(override)
    return Path.home() / ".claude" / "plugin-data" / "memoforge"


def profiles_dir() -> Path:
    return plugin_data_dir() / "profiles"


def default_file() -> Path:
    return plugin_data_dir() / "default-profile.txt"


NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")

REQUIRED_META_KEYS = {
    "name",
    "created_at",
    "input_type",
    "mode_binding",
    "has_template",
}
VALID_INPUT_TYPES = {"examples", "rules", "both"}
VALID_MODE_BINDINGS = {"brief", "full"}


def profile_dir(name: str) -> Path:
    return profiles_dir() / name


def profile_files(name: str) -> dict[str, Path]:
    base = profile_dir(name)
    return {
        "dir": base,
        "prose_style": base / "prose-style.md",
        "template": base / "template.md",
        "meta": base / "meta.json",
        "rules": base / "rules.md",
        "sources_dir": base / "sources",
    }


def as_posix(p: Path) -> str:
    """Return a path in POSIX form for cross-platform storage in state.json."""
    return str(p).replace("\\", "/")


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate_name(name: str) -> Optional[str]:
    """Return None if name is valid, else an error message."""
    if not name:
        return "name is empty"
    if len(name) > 64:
        return f"name too long ({len(name)} > 64)"
    if not NAME_PATTERN.match(name):
        return (
            "name must match [a-z0-9][a-z0-9_-]{0,63} "
            "(lowercase letters, digits, dashes, underscores; "
            "cannot start with - or _)"
        )
    return None


def validate_profile(name: str) -> tuple[bool, list[str]]:
    """Check that the profile dir has the required shape.

    Required files: prose-style.md, meta.json (with required keys).
    template.md is optional (allowed when input_type=rules without structure).
    """
    errors: list[str] = []
    files = profile_files(name)

    if not files["dir"].is_dir():
        return False, [f"profile directory does not exist: {as_posix(files['dir'])}"]

    if not files["prose_style"].is_file():
        errors.append(f"missing required file: prose-style.md")

    if not files["meta"].is_file():
        errors.append(f"missing required file: meta.json")
    else:
        try:
            meta = json.loads(files["meta"].read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"meta.json is not valid JSON: {exc}")
            meta = None

        if meta is not None:
            missing = REQUIRED_META_KEYS - set(meta.keys())
            if missing:
                errors.append(
                    f"meta.json missing required keys: {sorted(missing)}"
                )
            if meta.get("input_type") not in VALID_INPUT_TYPES:
                errors.append(
                    f"meta.json input_type must be one of {sorted(VALID_INPUT_TYPES)}, "
                    f"got {meta.get('input_type')!r}"
                )
            if meta.get("mode_binding") not in VALID_MODE_BINDINGS:
                errors.append(
                    f"meta.json mode_binding must be one of {sorted(VALID_MODE_BINDINGS)}, "
                    f"got {meta.get('mode_binding')!r}"
                )
            if meta.get("has_template") and not files["template"].is_file():
                errors.append(
                    "meta.json says has_template=true but template.md is missing"
                )
            if not meta.get("has_template") and files["template"].is_file():
                errors.append(
                    "template.md exists but meta.json says has_template=false"
                )

    return len(errors) == 0, errors


# ---------------------------------------------------------------------------
# Filesystem ops
# ---------------------------------------------------------------------------


def ensure_dirs() -> None:
    profiles_dir().mkdir(parents=True, exist_ok=True)


def list_profiles() -> list[dict]:
    """Return a list of profile records with metadata.

    Each record: {name, valid, errors, meta} where meta is the parsed
    meta.json or None.
    """
    pdir = profiles_dir()
    if not pdir.is_dir():
        return []
    default_name = get_default()
    records: list[dict] = []
    for entry in sorted(pdir.iterdir()):
        if not entry.is_dir():
            continue
        name = entry.name
        valid, errors = validate_profile(name)
        meta: Optional[dict] = None
        meta_path = profile_files(name)["meta"]
        if meta_path.is_file():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                meta = None
        records.append(
            {
                "name": name,
                "valid": valid,
                "errors": errors,
                "meta": meta,
                "is_default": name == default_name,
                "dir": as_posix(entry),
            }
        )
    return records


def get_default() -> Optional[str]:
    f = default_file()
    if not f.is_file():
        return None
    name = f.read_text(encoding="utf-8").strip()
    return name or None


def set_default(name: str) -> None:
    err = validate_name(name)
    if err:
        raise ValueError(f"invalid profile name: {err}")
    if not profile_dir(name).is_dir():
        raise FileNotFoundError(f"profile not found: {name}")
    ensure_dirs()
    write_atomic_text(default_file(), name + "\n")


def clear_default() -> None:
    f = default_file()
    if f.is_file():
        f.unlink()


def delete_profile(name: str) -> None:
    err = validate_name(name)
    if err:
        raise ValueError(f"invalid profile name: {err}")
    target = profile_dir(name)
    if not target.is_dir():
        raise FileNotFoundError(f"profile not found: {name}")
    shutil.rmtree(target)
    if get_default() == name:
        clear_default()


def init_profile(
    name: str, input_type: str, mode_binding: str, rules_provided: bool = False
) -> dict[str, Path]:
    """Create an empty profile dir + meta.json stub. Called by style-extractor
    after it has finished reading inputs but before writing prose-style.md /
    template.md / rules.md. Returns the files dict for downstream writes.
    """
    err = validate_name(name)
    if err:
        raise ValueError(f"invalid profile name: {err}")
    if input_type not in VALID_INPUT_TYPES:
        raise ValueError(
            f"input_type must be one of {sorted(VALID_INPUT_TYPES)}, got {input_type!r}"
        )
    if mode_binding not in VALID_MODE_BINDINGS:
        raise ValueError(
            f"mode_binding must be one of {sorted(VALID_MODE_BINDINGS)}, got {mode_binding!r}"
        )

    files = profile_files(name)
    files["dir"].mkdir(parents=True, exist_ok=True)
    files["sources_dir"].mkdir(parents=True, exist_ok=True)

    meta = {
        "name": name,
        "created_at": datetime.datetime.now(datetime.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
        "input_type": input_type,
        "examples_count": 0,
        "rules_provided": rules_provided,
        "mode_binding": mode_binding,
        "has_template": False,
        "jurisdictions": [],
        "language": None,
        "confidence": None,
        "summary": "",
    }
    write_atomic_text(files["meta"], json.dumps(meta, indent=2, ensure_ascii=False))
    return files


def write_meta(name: str, meta_json: str) -> None:
    """Atomically write meta.json from a JSON string. Called by style-extractor
    after extraction completes to fill in real values (examples_count, language,
    has_template, confidence, summary, etc.)."""
    try:
        meta = json.loads(meta_json)
    except json.JSONDecodeError as exc:
        raise ValueError(f"meta is not valid JSON: {exc}")

    missing = REQUIRED_META_KEYS - set(meta.keys())
    if missing:
        raise ValueError(f"meta is missing required keys: {sorted(missing)}")

    files = profile_files(name)
    if not files["dir"].is_dir():
        raise FileNotFoundError(f"profile not found: {name}")
    write_atomic_text(files["meta"], json.dumps(meta, indent=2, ensure_ascii=False))


def write_atomic_text(path: Path, content: str) -> None:
    """Atomic write: write to .tmp then replace.

    Matches the pattern used by scripts/log_event.py and the orchestrator's
    state.json writes (write-then-rename). Prevents torn writes if the process
    is killed mid-write.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(path)


# ---------------------------------------------------------------------------
# Resolved paths (for state.json)
# ---------------------------------------------------------------------------


def resolve_paths(name: str) -> dict[str, Optional[str]]:
    """Return the POSIX paths to write into state.json.config.

    Returns a dict with style_profile, style_profile_path, prose_style_path,
    template_path. template_path is None if the profile has no template.md
    (rules-only profile without structural rules).
    """
    files = profile_files(name)
    if not files["dir"].is_dir():
        raise FileNotFoundError(f"profile not found: {name}")
    template_path: Optional[str] = (
        as_posix(files["template"]) if files["template"].is_file() else None
    )
    return {
        "style_profile": name,
        "style_profile_path": as_posix(files["dir"]),
        "prose_style_path": as_posix(files["prose_style"]),
        "template_path": template_path,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Manage user style profiles for memoforge."
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list", help="List profiles as JSON.")
    sub.add_parser("get-default", help="Print current default profile name.")
    sub.add_parser("clear-default", help="Remove the default-profile.txt file.")
    sub.add_parser("ensure-dirs", help="Create profiles directory if missing.")

    p_set = sub.add_parser("set-default", help="Set the default profile.")
    p_set.add_argument("name")

    p_vn = sub.add_parser("validate-name", help="Exit 0 if name is valid, 2 if not.")
    p_vn.add_argument("name")

    p_vp = sub.add_parser("validate-profile", help="Check profile dir shape.")
    p_vp.add_argument("name")

    p_del = sub.add_parser("delete", help="Delete a profile directory.")
    p_del.add_argument("name")

    p_rm = sub.add_parser("read-meta", help="Print meta.json contents.")
    p_rm.add_argument("name")

    p_rp = sub.add_parser(
        "resolve-paths",
        help="Print POSIX paths to write into state.json (JSON output).",
    )
    p_rp.add_argument("name")

    p_init = sub.add_parser(
        "init-profile",
        help="Create empty profile dir and meta.json stub (used by extractor).",
    )
    p_init.add_argument("name")
    p_init.add_argument("input_type", choices=sorted(VALID_INPUT_TYPES))
    p_init.add_argument("mode_binding", choices=sorted(VALID_MODE_BINDINGS))
    p_init.add_argument(
        "--rules-provided", action="store_true", help="Mark rules_provided=true."
    )

    p_wm = sub.add_parser(
        "write-meta",
        help="Atomically write meta.json from a JSON string (positional arg).",
    )
    p_wm.add_argument("name")
    p_wm.add_argument(
        "meta_json",
        help="Full meta.json content as a JSON string.",
    )

    args = parser.parse_args(argv)

    try:
        if args.cmd == "list":
            print(json.dumps(list_profiles(), indent=2, ensure_ascii=False))
            return 0

        if args.cmd == "get-default":
            d = get_default()
            if d:
                print(d)
            return 0

        if args.cmd == "set-default":
            set_default(args.name)
            return 0

        if args.cmd == "clear-default":
            clear_default()
            return 0

        if args.cmd == "ensure-dirs":
            ensure_dirs()
            return 0

        if args.cmd == "validate-name":
            err = validate_name(args.name)
            if err:
                print(err, file=sys.stderr)
                return 2
            return 0

        if args.cmd == "validate-profile":
            valid, errors = validate_profile(args.name)
            if not valid:
                for e in errors:
                    print(e, file=sys.stderr)
                return 2
            return 0

        if args.cmd == "delete":
            delete_profile(args.name)
            return 0

        if args.cmd == "read-meta":
            files = profile_files(args.name)
            if not files["meta"].is_file():
                print(f"meta.json not found for profile {args.name!r}", file=sys.stderr)
                return 2
            print(files["meta"].read_text(encoding="utf-8"))
            return 0

        if args.cmd == "resolve-paths":
            paths = resolve_paths(args.name)
            print(json.dumps(paths, indent=2, ensure_ascii=False))
            return 0

        if args.cmd == "init-profile":
            init_profile(
                args.name,
                args.input_type,
                args.mode_binding,
                rules_provided=args.rules_provided,
            )
            return 0

        if args.cmd == "write-meta":
            write_meta(args.name, args.meta_json)
            return 0

        parser.error(f"unknown command: {args.cmd}")
        return 2  # not reached

    except (FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
