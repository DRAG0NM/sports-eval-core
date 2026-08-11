#!/usr/bin/env python3
"""Fail closed when public-release privacy, credentials, or links regress."""

import json
import os
import re
import sys

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
IGNORED_DIRS = {".git", "__pycache__", "node_modules", ".trash"}
FORBIDDEN_DIRS = {"原始数据", "_raw", "coach_jobs", "private", "data"}
FORBIDDEN_SUFFIXES = {".fit", ".tcx", ".gpx", ".har", ".jsonl"}
FORBIDDEN_NAMES = {".env", "解析索引.json", "个人档案.md", "state.json",
                   "coach_profile.json", "coach_metrics.jsonl", "教练事件.jsonl"}
FORBIDDEN_SCRIPT_TEXT = {"accesstoken", "sessionstorage", "dbankcloud", "health.cloud",
                         "huawei", "华为"}
FORBIDDEN_TEXT = {"obs" + "_lib", "运动评估" + "\\01_训练日志",
                  "users\\" + "21224", "drag" + "0nm"}
WINDOWS_ABSOLUTE = re.compile(r"(?i)(?<![A-Za-z0-9])[A-Z]:\\[^\\\s\"']+\\")
UNIX_ABSOLUTE = re.compile(r"/(?:home|Users)/[^/\s]+/")
CREDENTIAL_ASSIGNMENT = re.compile(
    r"(?i)(?:api[_-]?key|access[_-]?token|refresh[_-]?token|authorization|cookie)\s*[:=]\s*['\"][^'\"]+['\"]")
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
    json_files = [path for path in all_files if path.endswith(".json")]
    for path in all_files:
        name = os.path.basename(path)
        relative = os.path.relpath(path, ROOT)
        parts = set(os.path.normpath(relative).split(os.path.sep))
        if os.path.islink(path):
            errors.append("symbolic link is not allowed: %s" % relative)
        if parts.intersection(FORBIDDEN_DIRS):
            errors.append("forbidden public directory: %s" % relative)
        if name.lower() in FORBIDDEN_NAMES or os.path.splitext(name)[1].lower() in FORBIDDEN_SUFFIXES:
            errors.append("forbidden public file: %s" % relative)
        if path.endswith((".py", ".md", ".json", ".bat", ".ps1", ".txt")):
            content = read_text(path)
            lowered = content.lower()
            if WINDOWS_ABSOLUTE.search(content) or UNIX_ABSOLUTE.search(content):
                errors.append("absolute personal path in %s" % relative)
            if CREDENTIAL_ASSIGNMENT.search(content):
                errors.append("credential assignment in %s" % relative)
            for needle in FORBIDDEN_TEXT:
                if needle in lowered:
                    errors.append("local identity/path marker in %s: %s" % (relative, needle))
        if path.endswith(".py") and name != "release_audit.py" and os.path.sep + "scripts" + os.path.sep in path:
            lowered = read_text(path).lower()
            for needle in FORBIDDEN_SCRIPT_TEXT:
                if needle in lowered:
                    errors.append("vendor/browser coupling in %s: %s" % (relative, needle))
    for path in markdown_files:
        for match in WIKILINK.finditer(read_text(path)):
            if not link_exists(path, match.group(1), markdown_files):
                errors.append("broken wikilink in %s: [[%s]]" %
                              (os.path.relpath(path, ROOT), match.group(1)))
    for path in json_files:
        relative = os.path.relpath(path, ROOT)
        try:
            value = json.loads(read_text(path))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append("invalid JSON %s: %s" % (relative, exc))
            continue
        if os.path.sep + "examples" + os.path.sep in path and isinstance(value, dict):
            if value.get("synthetic") is not True:
                errors.append("example must declare synthetic=true: %s" % relative)
    if errors:
        for error in sorted(set(errors)):
            print("FAIL:", error)
        return 1
    print("PASS: no forbidden health/location/credential containers")
    print("PASS: no absolute personal paths or local identity markers")
    print("PASS: public scripts contain no vendor endpoint or browser-token logic")
    print("PASS: all Obsidian wikilinks resolve")
    print("PASS: all JSON is valid and input examples are synthetic")
    return 0


if __name__ == "__main__":
    sys.exit(audit())
