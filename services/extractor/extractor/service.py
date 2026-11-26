"""The service shell: one ExtractRequested message in, a status out (ADR-0005, ADR-0007).

Standard library only; the queue and the blobs are behind small interfaces, so the
rules are tested with fakes:

- a retry never calls the AI services when the text blob exists;
- the blob is written only if it does not exist (If-None-Match: *);
- a transient error abandons the message until its fifth delivery, then Failed(extract_error);
- logs carry identifiers and counts, never content (ADR-0015).
"""
import json
import logging
import re

from . import core
from .pages import BadZip, read_zip

log = logging.getLogger('extractor')

MAX_DELIVERIES = 5
_UUID7 = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$')
_VERSION = re.compile(r'^(\d+)\.(\d+)$')

COMPLETE, ABANDON, DEAD_LETTER = 'complete', 'abandon', 'dead-letter'


class Transient(Exception):
    """A service is down, throttling or timed out. The adapters raise it; the message is retried."""


def handle(body, delivery_count, store, status, extract):
    """Processes one message body (bytes). Returns COMPLETE, ABANDON or DEAD_LETTER.

    store: text_exists(ids), read_clean(ids) -> bytes | None, write_text_if_absent(ids, blob) -> bool
    status: send(message dict)
    extract: callable(pages, ids) -> (blob, usage); core.extract with its services bound
    """
    try:
        msg = json.loads(body)
        ids = {k: msg[k] for k in ('userId', 'docId', 'verId')}
        version = _VERSION.match(str(msg.get('schemaVersion', '')))
    except (ValueError, KeyError, TypeError):
        log.error('unreadable message')
        return DEAD_LETTER
    if not all(isinstance(v, str) and _UUID7.match(v) for v in ids.values()):
        log.error('identifiers are not UUIDv7')  # never log what is not an identifier
        return DEAD_LETTER
    ctx = {'userId': ids['userId'], 'docId': ids['docId'], 'verId': ids['verId'], 'deliveryCount': delivery_count}
    if msg.get('type') != 'ExtractRequested' or not version or version.group(1) != '1':
        log.error('message type or major version not supported', extra=ctx)
        return DEAD_LETTER
    try:
        return _process(ids, ctx, delivery_count, store, status, extract)
    except Transient as e:
        if delivery_count < MAX_DELIVERIES:
            log.warning('transient error, abandoned: %s', type(e).__name__, extra=ctx)
            return ABANDON
        log.error('transient error on the last delivery: %s', type(e).__name__, extra=ctx)
        return _fail_last(ids, store, status)
    except Exception as e:  # a bug or a non-transient refusal: retrying would call the AI services again
        log.error('unexpected error: %s', type(e).__name__, extra=ctx)  # the type only: messages may quote content
        return _fail_last(ids, store, status)


def _fail_last(ids, store, status):
    """Ends the version with Failed(extract_error), unless its results were saved meanwhile."""
    try:
        saved = store.text_exists(ids)
        status.send(_status('Extracted', ids) if saved else _status('Failed', ids, reason='extract_error'))
    except Exception:
        return ABANDON  # delivered again; the queue's max delivery count ends in dead-letter, which alerts
    return COMPLETE


def _process(ids, ctx, delivery_count, store, status, extract):
    if store.text_exists(ids):
        log.info('results already saved; reporting again', extra=ctx)
        status.send(_status('Extracted', ids))
        return COMPLETE
    data = store.read_clean(ids)
    if data is None:
        log.warning('clean ZIP missing: the version was deleted or replaced', extra=ctx)
        return COMPLETE
    try:
        pages = read_zip(data)
    except BadZip as e:
        log.error('clean ZIP breaks its contract: %s', e, extra=ctx)
        status.send(_status('Failed', ids, reason='extract_error'))
        return COMPLETE
    try:
        blob, usage = extract(pages, ids)
    except core.InvalidAnswer as e:
        log.warning('answer invalid after a retry', extra={**ctx, 'problems': len(e.problems)})
        status.send(_status('Failed', ids, reason='extract_invalid'))
        return COMPLETE
    except core.NoResults:
        log.info('no results: not a lab result', extra=ctx)
        status.send(_status('Failed', ids, reason='no_results'))
        return COMPLETE
    written = store.write_text_if_absent(ids, json.dumps(blob, ensure_ascii=False).encode('utf-8'))
    log.info('extracted', extra={**ctx, 'pages': len(pages), 'results': len(blob['results']),
                                 'written': written, 'inputTokens': usage['input'],
                                 'outputTokens': usage['output'], 'llmCalls': usage['calls'],
                                 'unread': len(blob['unread'])})
    status.send(_status('Extracted', ids))
    return COMPLETE


def _status(kind, ids, reason=None):
    msg = {'type': kind, 'schemaVersion': '1.0', **ids}
    if reason:
        msg['reason'] = reason
    return msg
