"""Smoke test of a deployed extractor (ADR-0019): one synthetic document goes through it as the test user.

It renders one page of a synthetic document, writes its clean ZIP to clean/{testUser}/{docId}/{verId}.zip,
sends ExtractRequested to the extract queue, and waits for text/{testUser}/{docId}/{verId}.json. The blob
must validate against the contract and hold at least one result. Prints identifiers and counts only.

Usage: python tools/smoke/extractor_smoke.py --generated DIR --storage URL --namespace HOST --user UUIDv7
       [--doc a1-vitamin-d] [--timeout 600]
The signed-in identity may write clean and read text under the test user's path only, and send to extract.
"""
import argparse
import io
import json
import os
import secrets
import sys
import time
import zipfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.normpath(os.path.join(_HERE, '..', '..'))
sys.path.insert(0, os.path.join(_ROOT, 'services', 'extractor'))
sys.path.insert(0, os.path.join(_ROOT, 'evals', 'extraction'))


def uuid7(now_ms=None):
    """A UUIDv7 (RFC 9562): 48 bits of Unix time in ms, version 7, variant 10, random bits."""
    ms = int(time.time() * 1000) if now_ms is None else now_ms
    value = (ms & ((1 << 48) - 1)) << 80 | 0x7 << 76 | secrets.randbits(12) << 64 | 0b10 << 62 | secrets.randbits(62)
    h = f'{value:032x}'
    return f'{h[:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:]}'


def clean_zip(pages):
    """The clean ZIP of ADR-0005: stored, manifest.json with the page order, pages/{sha256}.png."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_STORED) as z:
        z.writestr('manifest.json', json.dumps({'schemaVersion': '1.0', 'order': [p.sha256 for p in pages]}))
        for p in pages:
            z.writestr(f'pages/{p.sha256}.png', p.png)
    return buffer.getvalue()


def extract_requested(user, doc, ver):
    return {'type': 'ExtractRequested', 'schemaVersion': '1.0', 'userId': user, 'docId': doc, 'verId': ver}


ROLE_WAIT = 300


def refused(error):
    """True for an authorization refusal (HTTP 403, or Service Bus's unauthorized error)."""
    # A missing Service Bus role surfaces as either error, depending on where the AMQP sign-in fails.
    return getattr(error, 'status_code', None) == 403 or type(error).__name__ in (
        'ServiceBusAuthorizationError', 'ServiceBusAuthenticationError')


def until_roles(call, wait, pause=15, clock=time.monotonic, sleep=time.sleep):
    """Runs call(); while it is refused and the wait is not over, tries again."""
    deadline = clock() + wait
    while True:
        try:
            return call()
        except Exception as e:  # noqa: BLE001  only refusals are retried
            if not refused(e) or clock() >= deadline:
                raise
            print(f'refused ({type(e).__name__}), roles may not be applied yet; retrying', flush=True)
            sleep(pause)


def readable_elsewhere(blobs):
    """Tries to read a blob of a random other user. A refusal is right; "not found" means the read was allowed."""
    try:
        blobs.get_blob_client('text', f'{uuid7()}/{uuid7()}/{uuid7()}.json').download_blob()
    except Exception as e:  # noqa: BLE001  azure.core's HttpResponseError, or a fake in the tests
        if getattr(e, 'status_code', None) is None:
            raise
        return e.status_code != 403
    return True


def errors(schema_name, data):
    from jsonschema import Draft202012Validator
    from extractor import contracts
    return [e.message for e in Draft202012Validator(contracts.schema(schema_name)).iter_errors(data)]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--generated', required=True)
    ap.add_argument('--storage', required=True)
    ap.add_argument('--namespace', required=True)
    ap.add_argument('--user', required=True)
    ap.add_argument('--doc', default='a1-vitamin-d')
    ap.add_argument('--timeout', type=int, default=600)
    args = ap.parse_args(argv)

    from azure.identity import DefaultAzureCredential
    from azure.servicebus import ServiceBusClient, ServiceBusMessage
    from azure.storage.blob import BlobServiceClient
    from extractor import contracts
    from live import pages_of

    pages = pages_of(os.path.join(args.generated, args.doc), 'text', 1)[:1]
    doc, ver = uuid7(), uuid7()
    path = f'{args.user}/{doc}/{ver}'
    credential = DefaultAzureCredential()
    blobs = BlobServiceClient(args.storage, credential)
    msg = extract_requested(args.user, doc, ver)
    if errors('messages.v1', msg):
        sys.exit('ExtractRequested breaks its contract')

    def upload():
        blobs.get_blob_client('clean', path + '.zip').upload_blob(clean_zip(pages), overwrite=True)

    def send():
        with ServiceBusClient(args.namespace, credential) as bus, bus.get_queue_sender('extract') as sender:
            sender.send_messages(ServiceBusMessage(json.dumps(msg), content_type='application/json',
                                                   subject=msg['type'],
                                                   application_properties={'docId': doc, 'verId': ver}))

    # New role assignments can take minutes to apply: retry a refusal for a while.
    until_roles(upload, ROLE_WAIT)
    until_roles(send, ROLE_WAIT)
    print(f'sent ExtractRequested docId={doc} verId={ver}, waiting up to {args.timeout} s', flush=True)

    text = blobs.get_blob_client('text', path + '.json')
    deadline = time.monotonic() + args.timeout
    while time.monotonic() < deadline:
        try:
            found = text.exists()
        except Exception as e:  # noqa: BLE001  the read role may still be on its way
            if not refused(e):
                raise
            found = False
        if found:
            blob = json.loads(text.download_blob().readall())
            if errors('text.v1', blob):
                sys.exit('text blob breaks its schema')
            problems = contracts.text_checks.problems(blob)
            if problems:
                sys.exit(f'text blob breaks {len(problems)} rule(s)')
            if not blob['results']:
                sys.exit('text blob has no results')
            # G3: after its own text was read, a refusal elsewhere comes from the condition, not a missing role.
            if readable_elsewhere(blobs):
                sys.exit('the smoke identity can read outside the test user: check the role condition')
            print(f'ok: {len(blob["results"])} result(s), {len(blob["unread"])} unread, '
                  f'model {blob["extraction"]["model"]}, extractor {blob["extraction"]["extractorVersion"]}')
            return
        time.sleep(10)
    sys.exit(f'no text blob after {args.timeout} s')


if __name__ == '__main__':
    main()
