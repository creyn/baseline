#!/usr/bin/env python3
"""A local MCP server that gives coding agents the project documentation.

It speaks the Model Context Protocol over stdio (one JSON-RPC message per line)
and only reads Markdown and YAML files of this repository: README.md, AGENTS.md,
docs/ and openspec/. Files that Git ignores (for example private/) are never
served. It holds no health data, makes no network calls and writes nothing.
Standard library and the git command only, so it runs wherever Python 3.10+ runs.

Usage: python3 tools/docs-mcp/server.py [--root PATH]
"""
import json
import os
import re
import subprocess
import sys

SERVER_INFO = {'name': 'baseline-docs', 'version': '1.0.0'}
# Newest first. The server answers with the client's version when it supports it.
PROTOCOL_VERSIONS = ['2025-11-25', '2025-06-18', '2025-03-26', '2024-11-05']
ALLOWED_TOP_FILES = {'README.md', 'AGENTS.md'}
ALLOWED_DIRS = ('docs', 'openspec')
ALLOWED_SUFFIXES = ('.md', '.yaml')
MAX_RESULTS = 50
MAX_FILE_BYTES = 1_000_000

INSTRUCTIONS = (
    'Project documentation of Baseline: architecture decisions (ADRs), gates, use cases, '
    'sequence diagrams and OpenSpec specs. Check the gates and the relevant ADRs before you change code.'
)


class ToolError(Exception):
    """An error the model can correct, reported as a tool result with isError."""


class Docs:
    def __init__(self, root):
        self.root = os.path.realpath(root)

    # ---------------------------------------------------------------- files
    def _allowed(self, rel):
        parts = rel.split('/')
        if not rel.endswith(ALLOWED_SUFFIXES):
            return False
        if len(parts) == 1:
            return parts[0] in ALLOWED_TOP_FILES
        return parts[0] in ALLOWED_DIRS

    def _candidates(self):
        """Files Git tracks or would track: ignored files (e.g. private/) are left out. No Git, no files."""
        try:
            out = subprocess.run(['git', '-C', self.root, 'ls-files', '-z', '--cached', '--others', '--exclude-standard'],
                                 capture_output=True, timeout=10, check=True).stdout
        except (OSError, subprocess.SubprocessError):
            raise ToolError('The documentation is served only from a Git working tree, and Git failed here.')
        return sorted({f for f in out.decode('utf-8', 'replace').split('\0') if f})

    def _resolved(self, rel):
        """The real path of rel if it and its link target are allowed documentation files, else None."""
        if '\\' in rel or '\x00' in rel or rel.startswith('/'):
            return None
        full = os.path.realpath(os.path.join(self.root, rel))
        inside = os.path.relpath(full, self.root).replace(os.sep, '/')
        if inside.startswith('..') or not self._allowed(inside) or not self._allowed(rel):
            return None
        return full if os.path.isfile(full) else None

    def files(self):
        return [rel for rel in self._candidates() if self._resolved(rel)]

    def path(self, rel):
        """Resolve a repository-relative path; refuse anything that is not served documentation."""
        if not isinstance(rel, str) or not rel:
            raise ToolError('Give a path relative to the repository root, e.g. docs/use-cases.md.')
        rel = os.path.normpath(rel).replace(os.sep, '/')
        full = self._resolved(rel)
        if full is None or rel not in self._candidates():
            raise ToolError(f'Not readable: {rel}. Only README.md, AGENTS.md and .md or .yaml files under docs/ and openspec/ '
                            'that Git does not ignore are. Use list_docs to see them.')
        return full

    def read(self, rel):
        return self._load(rel, self.path(rel))

    def _load(self, rel, full):
        if os.path.getsize(full) > MAX_FILE_BYTES:
            raise ToolError(f'{rel} is larger than {MAX_FILE_BYTES} bytes.')
        try:
            with open(full, encoding='utf-8') as f:
                return f.read().replace('\r\n', '\n')
        except UnicodeDecodeError:
            raise ToolError(f'{rel} is not valid UTF-8.')

    def _readable(self):
        """(path, text) of every served file; a file that cannot be read is skipped, not fatal."""
        for rel in self._candidates():
            full = self._resolved(rel)
            if full is None:
                continue
            try:
                yield rel, self._load(rel, full)
            except ToolError:
                continue

    # ---------------------------------------------------------------- tools
    def list_docs(self):
        return '\n'.join(self.files())

    def read_doc(self, path):
        return self.read(path)

    def list_decisions(self):
        rows = ['| # | Decision | Status | File |', '|---|---|---|---|']
        for rel, text in self._readable():
            m = re.fullmatch(r'docs/adr/(\d{4})-[^/]+\.md', rel)
            if not m:
                continue
            title = re.search(r'^# \d+\. (.*)$', text, re.M)
            status = re.search(r'^## Status\s*\n+(\S[^\n]*)', text, re.M)
            rows.append(f'| {m.group(1)} | {title.group(1) if title else "?"} | {status.group(1).split(".")[0] if status else "?"} | {rel} |')
        return '\n'.join(rows)

    def get_decision(self, number):
        try:
            n = int(str(number).upper().replace('ADR-', ''))
        except (ValueError, OverflowError):
            raise ToolError('Give the ADR number, e.g. 5 or "ADR-0005".')
        for rel in self.files():
            if re.fullmatch(rf'docs/adr/{n:04d}-[^/]+\.md', rel):
                return self.read(rel)
        raise ToolError(f'No ADR {n:04d}. Use list_decisions to see the numbers.')

    def get_gates(self):
        text = self.read('docs/decision-criteria.md')
        m = re.search(r'^## Gates[ \t]*\n(.*?)(?=^## |\Z)', text, re.S | re.M)
        if not m:
            raise ToolError('docs/decision-criteria.md has no "## Gates" section.')
        return '## Gates (from docs/decision-criteria.md)\n' + m.group(1).strip()

    def get_use_case(self, id):
        uc = str(id).strip().upper()
        if not re.fullmatch(r'U\d{1,2}', uc):
            raise ToolError('Give a use case id such as "U3".')
        out = []
        for rel, label in (('docs/use-cases.md', 'Workload and targets'), ('docs/sequences/README.md', 'Diagram and decisions')):
            lines = self.read(rel).splitlines()
            for i, line in enumerate(lines):
                if line.startswith(f'| {uc} |'):
                    header = next((lines[j] for j in range(i, -1, -1) if lines[j].startswith('| # |')), '')
                    out.append(f'{label} ({rel}):\n{header}\n{line}')
                    break
        if not out:
            raise ToolError(f'No use case {uc}. The use cases are listed in docs/use-cases.md.')
        return '\n\n'.join(out)

    def search_docs(self, query, limit=20):
        words = [w.lower() for w in str(query).split() if w]
        if not words:
            raise ToolError('Give one or more words to search for.')
        if isinstance(limit, bool) or not isinstance(limit, int):
            raise ToolError(f'limit must be a whole number from 1 to {MAX_RESULTS}.')
        limit = max(1, min(limit, MAX_RESULTS))
        hits = []
        for rel, text in self._readable():
            for no, line in enumerate(text.splitlines(), 1):
                low = line.lower()
                if all(w in low for w in words):
                    hits.append(f'{rel}:{no}: {line.strip()[:300]}')
                    if len(hits) >= limit:
                        return '\n'.join(hits) + f'\n(first {limit} matches)'
        return '\n'.join(hits) if hits else f'No line contains all of: {" ".join(words)}'


NO_ARGS = {'type': 'object', 'properties': {}, 'additionalProperties': False}
TOOLS = [
    {'name': 'list_decisions', 'title': 'List architecture decisions',
     'description': 'Lists every ADR with its number, title, status and file.', 'inputSchema': NO_ARGS},
    {'name': 'get_decision', 'title': 'Read an architecture decision',
     'description': 'Returns the full text of one ADR: context, considered options, decision and consequences.',
     'inputSchema': {'type': 'object', 'properties': {'number': {'type': 'integer', 'description': 'ADR number, e.g. 5'}},
                     'required': ['number'], 'additionalProperties': False}},
    {'name': 'get_gates', 'title': 'Read the gates',
     'description': 'Returns the gates G1-G6 that every change must pass.', 'inputSchema': NO_ARGS},
    {'name': 'get_use_case', 'title': 'Read a use case',
     'description': 'Returns the workload, target time, sequence diagram and decisions of one use case (U1-U11).',
     'inputSchema': {'type': 'object', 'properties': {'id': {'type': 'string', 'description': 'e.g. "U3"'}},
                     'required': ['id'], 'additionalProperties': False}},
    {'name': 'search_docs', 'title': 'Search the documentation',
     'description': 'Finds lines that contain all the given words (case-insensitive) in README.md, AGENTS.md, docs/ and openspec/.',
     'inputSchema': {'type': 'object', 'properties': {
         'query': {'type': 'string', 'description': 'words that must all appear on the line'},
         'limit': {'type': 'integer', 'description': f'at most this many lines (1-{MAX_RESULTS}, default 20)'}},
         'required': ['query'], 'additionalProperties': False}},
    {'name': 'list_docs', 'title': 'List documentation files',
     'description': 'Lists every file the other tools can read.', 'inputSchema': NO_ARGS},
    {'name': 'read_doc', 'title': 'Read a documentation file',
     'description': 'Returns one file by its path relative to the repository root, e.g. docs/use-cases.md.',
     'inputSchema': {'type': 'object', 'properties': {'path': {'type': 'string'}},
                     'required': ['path'], 'additionalProperties': False}},
]
for t in TOOLS:
    # Hints for clients; the server never writes and never leaves the repository.
    t['annotations'] = {'readOnlyHint': True, 'openWorldHint': False}


def handle(docs, msg):
    """Returns the response for one JSON-RPC message, or None for a notification."""
    if not isinstance(msg, dict) or msg.get('jsonrpc') != '2.0' or not isinstance(msg.get('method'), str):
        return {'jsonrpc': '2.0', 'id': msg.get('id') if isinstance(msg, dict) else None,
                'error': {'code': -32600, 'message': 'Invalid request'}}
    method, params, mid = msg['method'], msg.get('params'), msg.get('id')
    if 'id' not in msg:
        return None  # notifications, e.g. notifications/initialized: nothing to answer
    if params is None:
        params = {}
    if not isinstance(params, dict):
        return {'jsonrpc': '2.0', 'id': mid, 'error': {'code': -32602, 'message': 'params must be an object'}}

    def ok(result):
        return {'jsonrpc': '2.0', 'id': mid, 'result': result}

    def err(code, text):
        return {'jsonrpc': '2.0', 'id': mid, 'error': {'code': code, 'message': text}}

    if method == 'initialize':
        asked = params.get('protocolVersion')
        version = asked if asked in PROTOCOL_VERSIONS else PROTOCOL_VERSIONS[0]
        return ok({'protocolVersion': version, 'capabilities': {'tools': {'listChanged': False}},
                   'serverInfo': SERVER_INFO, 'instructions': INSTRUCTIONS})
    if method == 'ping':
        return ok({})
    if method == 'tools/list':
        return ok({'tools': TOOLS})
    if method == 'tools/call':
        name, args = params.get('name'), params.get('arguments') or {}
        tool = next((t for t in TOOLS if t['name'] == name), None)
        if tool is None:
            return err(-32602, f'Unknown tool: {name}')
        # Input validation errors are tool execution errors, so the model can correct the call.
        def bad(text):
            return ok({'content': [{'type': 'text', 'text': text}], 'isError': True})
        if not isinstance(args, dict):
            return bad('arguments must be an object.')
        unknown = sorted(set(args) - set(tool['inputSchema']['properties']))
        if unknown:
            return bad(f'Unknown argument: {", ".join(unknown)}. Allowed: {", ".join(tool["inputSchema"]["properties"]) or "none"}.')
        missing = [k for k in tool['inputSchema'].get('required', []) if k not in args]
        if missing:
            return bad(f'Missing argument: {", ".join(missing)}')
        try:
            text = getattr(docs, name)(**args)
            return ok({'content': [{'type': 'text', 'text': text}], 'isError': False})
        except ToolError as e:
            return ok({'content': [{'type': 'text', 'text': str(e)}], 'isError': True})
        except Exception as e:  # never crash the server on one bad call
            print(f'{name} failed: {type(e).__name__}', file=sys.stderr)
            return err(-32603, 'Internal error')
    return err(-32601, f'Method not found: {method}')


def serve(docs, stdin, stdout):
    """stdin yields bytes lines; stdout takes str. One bad message never ends the session."""
    for raw in stdin:
        if isinstance(raw, bytes):
            raw = raw.decode('utf-8', 'replace')
        line = raw.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except (ValueError, RecursionError):
            reply = {'jsonrpc': '2.0', 'id': None, 'error': {'code': -32700, 'message': 'Parse error'}}
        else:
            try:
                reply = handle(docs, msg)
            except Exception as e:
                print(f'request failed: {type(e).__name__}', file=sys.stderr)
                reply = {'jsonrpc': '2.0', 'id': msg.get('id') if isinstance(msg, dict) else None,
                         'error': {'code': -32603, 'message': 'Internal error'}}
        if reply is not None:
            # One message per line: json.dumps never emits a raw newline.
            stdout.write(json.dumps(reply, ensure_ascii=False) + '\n')
            stdout.flush()


def main(argv):
    root = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')
    if len(argv) == 3 and argv[1] == '--root':
        root = argv[2]
    elif len(argv) != 1:
        print(__doc__, file=sys.stderr)
        return 2
    sys.stdout.reconfigure(encoding='utf-8')
    serve(Docs(root), sys.stdin.buffer, sys.stdout)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
