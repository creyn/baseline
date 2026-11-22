#!/usr/bin/env python3
"""Claude Code PreToolUse hook: scan for personal data and secrets before an agent commits or pushes.

Claude Code passes the tool call as JSON on stdin. Exit code 2 blocks the call, and stderr is shown to the agent.
"""
import json
import os
import re
import subprocess
import sys

call = json.load(sys.stdin)
command = call.get("tool_input", {}).get("command", "")
scan = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scan.py")

if re.search(r"\bgit\b.*\s--no-verify\b", command):
    print("Blocked: --no-verify skips the privacy scan. Fix the finding instead.", file=sys.stderr)
    sys.exit(2)

if re.search(r"\bgit\b.*\bcommit\b", command):
    mode = ["--staged"]
elif re.search(r"\bgit\b.*\bpush\b", command):
    mode = ["--diff", "origin/main"]
else:
    sys.exit(0)

result = subprocess.run([sys.executable, scan, *mode], capture_output=True, text=True)
if result.returncode != 0:
    print("Blocked by the privacy scan:\n" + result.stderr, file=sys.stderr)
    sys.exit(2)
