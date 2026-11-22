#!/usr/bin/env python3
"""Scan text for personal data and secrets before it reaches the public repository.

Usage:
  scan.py --staged          scan lines added in the staged diff (pre-commit)
  scan.py --diff BASE       scan lines added since BASE (CI on a pull request)
  scan.py --all             scan every tracked text file (CI on main)

Exit code 1 if anything is found. Only the Python standard library is used.

An optional deny list of exact words (for example the owner's real names) is read from the file
named in the BASELINE_DENYLIST environment variable. The deny list itself never enters the repository.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from dataclasses import dataclass

PESEL = re.compile(r"(?<!\d)\d{11}(?!\d)")
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
# Reserved test domains (RFC 2606) and no-reply addresses used in commits.
ALLOWED_EMAIL = re.compile(r"(@users\.noreply\.github\.com|@example\.(com|org|net)|\.(test|example|invalid)|@anthropic\.com|^noreply@)$", re.I)
SECRETS = {
    "private key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "Azure connection string": re.compile(r"(AccountKey|SharedAccessKey)=[A-Za-z0-9+/=]{20,}"),
    "GitHub token": re.compile(r"\b(ghp|gho|ghs|ghu)_[A-Za-z0-9]{30,}|\bgithub_pat_[A-Za-z0-9_]{40,}"),
    "API key assignment": re.compile(r"(?i)\b(api[_-]?key|client[_-]?secret|password)\s*[:=]\s*['\"][^'\"\s]{12,}['\"]"),
}
BINARY_EXT = {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".gz", ".wasm", ".pfb", ".ttf", ".zip", ".ico"}


def pesel_is_valid(digits: str) -> bool:
    """True if the 11 digits form a PESEL with a correct checksum and a possible date of birth."""
    weights = (1, 3, 7, 9, 1, 3, 7, 9, 1, 3)
    d = [int(c) for c in digits]
    if (10 - sum(w * x for w, x in zip(weights, d)) % 10) % 10 != d[10]:
        return False
    month = (d[2] * 10 + d[3]) % 20
    day = d[4] * 10 + d[5]
    return 1 <= month <= 12 and 1 <= day <= 31


@dataclass
class Finding:
    path: str
    line: int
    kind: str

    def __str__(self) -> str:
        # The matched text is never printed, so the scanner cannot leak what it found.
        return f"{self.path}:{self.line}: {self.kind}"


def load_allowlist() -> set[str]:
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "allowlist.txt")
    if not os.path.exists(path):
        return set()
    with open(path, encoding="utf-8") as f:
        return {line.split("#")[0].strip() for line in f if line.split("#")[0].strip()}


ALLOWED = load_allowlist()


def load_denylist() -> list[str]:
    path = os.environ.get("BASELINE_DENYLIST")
    if not path or not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return [w.strip().lower() for w in f if w.strip() and not w.startswith("#")]


def scan_line(text: str, denylist: list[str]) -> list[str]:
    kinds = []
    if any(pesel_is_valid(m.group()) and m.group() not in ALLOWED for m in PESEL.finditer(text)):
        kinds.append("valid PESEL")
    if any(not ALLOWED_EMAIL.search(m.group()) for m in EMAIL.finditer(text)):
        kinds.append("e-mail address")
    kinds += [name for name, rx in SECRETS.items() if rx.search(text)]
    low = text.lower()
    if any(re.search(r"(?<!\w)" + re.escape(w) + r"(?!\w)", low) for w in denylist):
        kinds.append("word from the deny list")
    return kinds


def scan_lines(path: str, lines: list[tuple[int, str]], denylist: list[str]) -> list[Finding]:
    if os.path.splitext(path)[1].lower() in BINARY_EXT or "/vendor/" in path:
        return []
    return [Finding(path, n, k) for n, t in lines for k in scan_line(t, denylist)]


def git(*args: str) -> str:
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True).stdout


def added_lines(diff: str) -> dict[str, list[tuple[int, str]]]:
    files: dict[str, list[tuple[int, str]]] = {}
    path, line = None, 0
    for raw in diff.splitlines():
        if raw.startswith("+++ "):
            path = raw[6:] if raw.startswith("+++ b/") else None
        elif raw.startswith("@@"):
            line = int(re.search(r"\+(\d+)", raw).group(1))
        elif path and raw.startswith("+"):
            files.setdefault(path, []).append((line, raw[1:]))
            line += 1
        elif path and not raw.startswith("-"):
            line += 1
    return files


def main(argv: list[str]) -> int:
    denylist = load_denylist()
    if argv[:1] == ["--staged"]:
        files = added_lines(git("diff", "--cached", "-U0", "--no-color"))
    elif argv[:1] == ["--diff"] and len(argv) == 2:
        files = added_lines(git("diff", f"{argv[1]}...HEAD", "-U0", "--no-color"))
    elif argv[:1] == ["--all"]:
        files = {}
        for p in git("ls-files").splitlines():
            if os.path.splitext(p)[1].lower() in BINARY_EXT or "/vendor/" in p:
                continue
            try:
                with open(p, encoding="utf-8") as f:
                    files[p] = list(enumerate(f.read().splitlines(), 1))
            except (UnicodeDecodeError, FileNotFoundError):
                continue
    else:
        print(__doc__, file=sys.stderr)
        return 2
    findings = [f for p, ls in files.items() for f in scan_lines(p, ls, denylist)]
    for f in findings:
        print(f, file=sys.stderr)
    if findings:
        print(f"{len(findings)} finding(s). Remove the data, or use fictional data (see AGENTS.md).", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
