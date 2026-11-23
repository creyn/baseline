"""Tests for the documentation MCP server. Run: python3 -m unittest discover -s tools/docs-mcp"""
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
import unittest.mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import server  # noqa: E402

REPO = os.path.realpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))


def call(docs, name, **args):
    reply = server.handle(docs, {'jsonrpc': '2.0', 'id': 7, 'method': 'tools/call', 'params': {'name': name, 'arguments': args}})
    return reply


def text(reply):
    return reply['result']['content'][0]['text']


class Fixture(unittest.TestCase):
    """A small fake repository, so the tests do not depend on the real documents."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.away = tempfile.TemporaryDirectory()
        r = os.path.join(self.tmp.name, 'repo')
        os.makedirs(r)
        self.root = r
        files = {
            'README.md': '# Readme\n',
            'AGENTS.md': '# Agents\nEvery receiver is idempotent.\n',
            'docs/decision-criteria.md': '# Criteria\n\n## Gates\n\n| # | Gate |\n|---|---|\n| G1 | Mask first. |\n\n## Weighted criteria\n\nK1\n',
            'docs/use-cases.md': '| # | Use case | Target |\n|---|---|---|\n| U1 | Sign in | < 2 s |\n| U3 | Review | < 2 s |\n',
            'docs/sequences/README.md': '| # | Use case | Diagram | Decisions |\n|---|---|---|---|\n| U3 | Review | [03](03-review.svg) | ADR-0006 |\n',
            'docs/adr/0006-document-lifecycle-and-review.md': '# 6. Document lifecycle\n\nDate: x\n\n## Status\n\nAccepted. Carried over.\n\n## Context\n\nStatuses are forward-only.\n',
            'docs/adr/0005/a.svg': '<svg/>',
            'openspec/config.yaml': 'context: test\n',
            'tools/secret.md': 'not documentation\n',
            'docs/private/real.md': 'ignored by git\n',
            '.gitignore': 'private/\n',
        }
        for rel, body in files.items():
            p = os.path.join(r, rel)
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, 'w', encoding='utf-8') as f:
                f.write(body)
        subprocess.run(['git', 'init', '-q', r], check=True)
        # A file next to the repository, and one in an unrelated folder.
        with open(os.path.join(self.tmp.name, 'outside.md'), 'w') as f:
            f.write('outside')
        self.outside = os.path.join(self.away.name, 'far.md')
        with open(self.outside, 'w') as f:
            f.write('far away')
        self.docs = server.Docs(r)

    def tearDown(self):
        self.tmp.cleanup()
        self.away.cleanup()


class ProtocolTest(Fixture):
    def test_initialize_echoes_a_supported_version(self):
        r = server.handle(self.docs, {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'protocolVersion': '2025-06-18'}})
        self.assertEqual(r['result']['protocolVersion'], '2025-06-18')
        self.assertIn('tools', r['result']['capabilities'])
        self.assertEqual(r['result']['serverInfo']['name'], 'baseline-docs')

    def test_initialize_offers_the_latest_version_for_an_unknown_one(self):
        r = server.handle(self.docs, {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'protocolVersion': '1999-01-01'}})
        self.assertEqual(r['result']['protocolVersion'], server.PROTOCOL_VERSIONS[0])

    def test_notification_gets_no_reply(self):
        self.assertIsNone(server.handle(self.docs, {'jsonrpc': '2.0', 'method': 'notifications/initialized'}))

    def test_ping_and_unknown_method(self):
        self.assertEqual(server.handle(self.docs, {'jsonrpc': '2.0', 'id': 2, 'method': 'ping'})['result'], {})
        self.assertEqual(server.handle(self.docs, {'jsonrpc': '2.0', 'id': 3, 'method': 'nope'})['error']['code'], -32601)

    def test_tools_list_has_valid_schemas(self):
        tools = server.handle(self.docs, {'jsonrpc': '2.0', 'id': 4, 'method': 'tools/list'})['result']['tools']
        self.assertEqual({t['name'] for t in tools},
                         {'list_decisions', 'get_decision', 'get_gates', 'get_use_case', 'search_docs', 'list_docs', 'read_doc'})
        for t in tools:
            self.assertEqual(t['inputSchema']['type'], 'object')
            self.assertTrue(t['annotations']['readOnlyHint'])

    def test_unknown_tool_is_a_protocol_error_and_bad_arguments_a_tool_error(self):
        self.assertEqual(call(self.docs, 'rm_rf')['error']['code'], -32602)
        self.assertTrue(call(self.docs, 'get_gates', x=1)['result']['isError'])
        self.assertTrue(call(self.docs, 'search_docs', query='x', limit='5')['result']['isError'])
        self.assertTrue(call(self.docs, 'search_docs', query='x', limit=True)['result']['isError'])

    def test_params_that_are_not_an_object(self):
        for params in ([1], 'x', 5):
            r = server.handle(self.docs, {'jsonrpc': '2.0', 'id': 9, 'method': 'tools/call', 'params': params})
            self.assertEqual(r['error']['code'], -32602)
        r = server.handle(self.docs, {'jsonrpc': '2.0', 'id': 9, 'method': 'tools/call', 'params': {'name': 'get_gates', 'arguments': [1]}})
        self.assertTrue(r['result']['isError'])

    def test_missing_argument_is_a_tool_error(self):
        r = call(self.docs, 'get_decision')
        self.assertTrue(r['result']['isError'])

    def test_stdio_survives_bad_input(self):
        bad = [b'{"jsonrpc":"2.0","id":1,"method":"ping"}', b'not json', b'', b'\xff\xfe broken utf-8',
               b'[' * 100000, b'{"jsonrpc":"2.0","id":2,"method":"tools/call","params":[1]}',
               b'{"jsonrpc":"2.0","id":3,"method":"ping"}']
        out = io.StringIO()
        server.serve(self.docs, iter(line + b'\n' for line in bad), out)
        replies = [json.loads(line) for line in out.getvalue().splitlines()]
        self.assertEqual(len(replies), 6)
        self.assertEqual(replies[0]['result'], {})
        self.assertEqual([r['error']['code'] for r in replies[1:4]], [-32700, -32700, -32700])
        self.assertEqual(replies[4]['error']['code'], -32602)
        self.assertEqual(replies[5]['id'], 3)


class ToolsTest(Fixture):
    def test_list_and_get_decision(self):
        listing = text(call(self.docs, 'list_decisions'))
        self.assertIn('| 0006 | Document lifecycle | Accepted | docs/adr/0006-document-lifecycle-and-review.md |', listing)
        self.assertIn('forward-only', text(call(self.docs, 'get_decision', number=6)))
        missing = call(self.docs, 'get_decision', number=99)
        self.assertTrue(missing['result']['isError'])
        self.assertIn('list_decisions', text(missing))
        self.assertTrue(call(self.docs, 'get_decision', number=10 ** 400)['result']['isError'])

    def test_gates_come_from_the_criteria_only(self):
        gates = text(call(self.docs, 'get_gates'))
        self.assertIn('G1', gates)
        self.assertNotIn('K1', gates)

    def test_gates_as_the_last_section_with_crlf(self):
        with open(os.path.join(self.root, 'docs/decision-criteria.md'), 'w', newline='') as f:
            f.write('# Criteria\r\n\r\n## Gates\r\n\r\n| G1 | Mask first. |\r\n')
        self.assertIn('| G1 | Mask first. |', text(call(self.docs, 'get_gates')))

    def test_use_case_joins_workload_and_diagram(self):
        uc = text(call(self.docs, 'get_use_case', id='u3'))
        self.assertIn('| U3 | Review | < 2 s |', uc)
        self.assertIn('03-review.svg', uc)
        self.assertTrue(call(self.docs, 'get_use_case', id='U99')['result']['isError'])

    def test_search_needs_all_words(self):
        self.assertIn('AGENTS.md:2:', text(call(self.docs, 'search_docs', query='Receiver IDEMPOTENT')))
        self.assertIn('No line', text(call(self.docs, 'search_docs', query='receiver banana')))

    def test_search_returns_at_most_50_lines(self):
        with open(os.path.join(self.root, 'docs/many.md'), 'w') as f:
            f.write('needle\n' * 80)
        lines = text(call(self.docs, 'search_docs', query='needle', limit=500)).splitlines()
        self.assertEqual(len([l for l in lines if 'needle' in l]), server.MAX_RESULTS)

    def test_a_broken_file_does_not_break_search(self):
        with open(os.path.join(self.root, 'docs/broken.md'), 'wb') as f:
            f.write(b'\xff\xfe idempotent')
        os.symlink(os.path.join(self.root, 'tools/secret.md'), os.path.join(self.root, 'docs/inrepo.md'))
        r = call(self.docs, 'search_docs', query='idempotent')
        self.assertFalse(r['result']['isError'])
        self.assertIn('AGENTS.md:2:', text(r))
        self.assertFalse(call(self.docs, 'list_decisions')['result']['isError'])
        self.assertTrue(call(self.docs, 'read_doc', path='docs/broken.md')['result']['isError'])

    def test_only_documentation_is_listed(self):
        listed = text(call(self.docs, 'list_docs')).splitlines()
        self.assertIn('openspec/config.yaml', listed)
        self.assertNotIn('tools/secret.md', listed)
        self.assertNotIn('docs/private/real.md', listed)
        self.assertFalse(any(f.endswith('.svg') for f in listed))

    def test_read_doc_refuses_everything_else(self):
        self.assertIn('Readme', text(call(self.docs, 'read_doc', path='README.md')))
        for bad in ['tools/secret.md', '../outside.md', '/etc/passwd', 'docs/../tools/secret.md', 'docs/adr/0005/a.svg', '',
                    'docs/private/real.md', 'DOCS/use-cases.md', 'docs\\..\\tools\\secret.md', 'README.MD']:
            r = call(self.docs, 'read_doc', path=bad)
            self.assertTrue(r['result']['isError'], bad)

    def test_symlinks_to_other_files_are_refused(self):
        os.symlink(self.outside, os.path.join(self.root, 'docs', 'link.md'))
        os.symlink(os.path.join(self.root, 'tools/secret.md'), os.path.join(self.root, 'docs', 'inrepo.md'))
        listed = text(call(self.docs, 'list_docs')).splitlines()
        for name in ('docs/link.md', 'docs/inrepo.md'):
            self.assertTrue(call(self.docs, 'read_doc', path=name)['result']['isError'], name)
            self.assertNotIn(name, listed)

    def test_nothing_is_opened_for_a_refused_path(self):
        opened = []
        real_open = open
        def spy(path, *a, **k):
            opened.append(path)
            return real_open(path, *a, **k)
        with unittest.mock.patch('builtins.open', spy):
            call(self.docs, 'read_doc', path='tools/secret.md')
            call(self.docs, 'read_doc', path='../outside.md')
        self.assertEqual(opened, [])

    def test_without_git_nothing_is_served(self):
        bare = server.Docs(self.away.name)
        self.assertTrue(call(bare, 'list_docs')['result']['isError'])


class RealRepositoryTest(unittest.TestCase):
    """End to end over stdio against the real documents."""

    def test_session(self):
        msgs = [
            {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'protocolVersion': '2025-11-25', 'capabilities': {}, 'clientInfo': {'name': 'test', 'version': '1'}}},
            {'jsonrpc': '2.0', 'method': 'notifications/initialized'},
            {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call', 'params': {'name': 'get_gates', 'arguments': {}}},
            {'jsonrpc': '2.0', 'id': 3, 'method': 'tools/call', 'params': {'name': 'list_decisions', 'arguments': {}}},
            {'jsonrpc': '2.0', 'id': 4, 'method': 'tools/call', 'params': {'name': 'search_docs', 'arguments': {'query': 'sweeper role'}}},
        ]
        proc = subprocess.run([sys.executable, os.path.join(REPO, 'tools', 'docs-mcp', 'server.py')],
                              input='\n'.join(json.dumps(m) for m in msgs) + '\n', capture_output=True, text=True, timeout=30)
        # Everything on stdout is an MCP message; nothing else is printed there.
        replies = [json.loads(line) for line in proc.stdout.splitlines()]
        self.assertEqual([r['id'] for r in replies], [1, 2, 3, 4])
        self.assertIn('G6', replies[1]['result']['content'][0]['text'])
        self.assertIn('0001', replies[2]['result']['content'][0]['text'])
        hits = replies[3]['result']['content'][0]['text'].splitlines()
        self.assertTrue(hits and all('sweeper' in h.lower() and 'role' in h.lower() for h in hits))


if __name__ == '__main__':
    unittest.main()
