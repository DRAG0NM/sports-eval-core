#!/usr/bin/env python3
"""Fail closed when public-release privacy or Obsidian-link boundaries regress."""

import json
import os
import re
import sys

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
IGNORED_DIRS = {".git", "__pycache__", "node_modules", ".trash"}
FORBIDDEN_SUFFIXES = {".fit", ".tcx", ".gpx", ".har"}
FORBIDDEN_NAMES = {".env", "解析索引.json", "个人档案.md"}
FORBIDDEN_SCRIPT_TEXT = {"accesstoken", "sessionstorage", "dbankcloud", "health.cloud", "华为", "huawei"}
WIKILINK = re.compile(r"\[\[([^\]]+)\]\]")


def files():
    for base, dirs, names in os.walk(ROOT):
        dirs[:] = [name for name in dirs if name not in IGNORED_DIRS]
        for name in names:
            yield os.path.join(base, name)


def read_text(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def link_exists(source, target, markdown_files):
    target = target.split("|", 1)[0].split("#", 1)[0].strip()
    if not target or "://" in target:
        return True
    direct = [os.path.join(ROOT, target), os.path.join(ROOT, target + ".md"),
              os.path.join(os.path.dirname(source), target),
              os.path.join(os.path.dirname(source), target + ".md")]
    if any(os.path.exists(path) for path in direct):
        return True
    if "/" not in target and "\\" not in target:
        return any(os.path.splitext(os.path.basename(path))[0] == target for path in markdown_files)
    return False


def audit():
    errors = []
    all_files = list(files())
    markdown_files = [path for path in all_files if path.endswith(".md")]
    for path in all_files:
        name = os.path.basename(path)
        relative = os.path.relpath(path, ROOT)
        if os.path.islink(path):
            errors.append("symbolic link is not allowed: %s" % relative)
        if name.lower() in FORBIDDEN_NAMES or os.path.splitext(name)[1].lower() in FORBIDDEN_SUFFIXES:
            errors.append("forbidden public file: %s" % relative)
        if (path.endswith(".py") and name != "release_audit.py" and
                os.path.sep + "scripts" + os.path.sep in path):
            lowered = read_text(path).lower()
            for needle in FORBIDDEN_SCRIPT_TEXT:
                if needle in lowered:
                    errors.append("vendor/browser coupling in %s: %s" % (relative, needle))
    for path in markdown_files:
        for match in WIKILINK.finditer(read_text(path)):
            if not link_exists(path, match.group(1), markdown_files):
                errors.append("broken wikilink in %s: [[%s]]" % (
                    os.path.relpath(path, ROOT), match.group(1)))
    for relative in ("examples/synthetic_week.json", "schemas/weekly_input.schema.json"):
        path = os.path.join(ROOT, relative)
        try:
            with open(path, encoding="utf-8") as handle:
                json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            errors.append("invalid JSON %s: %s" % (relative, exc))
    if errors:
        for error in errors:
            print("FAIL:", error)
        return 1
    print("PASS: no forbidden health/location/credential file types")
    print("PASS: public scripts contain no vendor endpoint or browser-token logic")
    print("PASS: all Obsidian wikilinks resolve")
    print("PASS: example and schema JSON are valid")
    return 0


if __name__ == "__main__":
    sys.exit(audit())
