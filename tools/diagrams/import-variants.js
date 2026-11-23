// Generates docs/adr/0005/: the three import variants compared in ADR-0005, each with the most frequent reads.
// Usage: node import-variants.js
// SLA targets are proposals, not measurements, except the browser masking times measured in the spike.
// Alternative paths are drawn as alt frames with arrows. Red "✗" notes describe only infrastructure failures
// (a component is down, a process crashes before it acknowledges a message): the state the system is left in.
const path = require('path');
const render = require('./sequence.js');
const out = process.argv[2] || path.join(__dirname, '../../docs/adr/0005');

const { P, SUB, mask, upload, relaySend, check, extract, apply, applyExtracted, review, reads } = require('./steps.js');

// ------------------------------------------------------------------ A: API orchestrates
const lastA = 'oai';
const failA = (reason) => [{ from: 'w', to: 'qevents', text: `send api-events: Failed { userId, docId, verId, reason: ${reason} }`, labelAt: 'start' }];
const A = {
  file: 'a-api-orchestrates',
  title: 'A · API orchestrates every step (with outbox)',
  subtitle: 'The worker reports every result to the API; the API decides the next step and sends it through the outbox. ' + SUB,
  colW: 210,
  participants: [P.ui, P.api, P.sql, P.relay, P.inc, P.clean, P.text, P.qworker, P.qevents, P.w, P.di, P.oai],
  steps: [
    ...mask,
    ...upload({ outbox: true, sendCheck: [], last: lastA }),
    ...relaySend('qworker', 'worker: CheckRequested { userId, docId, verId }', 'Uploaded'),
    { section: 'Check · target: Blocked, or extraction started, within 1 min of the upload' },
    ...check({ who: 'w', inQ: 'qworker', last: lastA,
      onResumeClean: [{ from: 'w', to: 'qevents', text: 'send api-events: CheckDone { userId, docId, verId, verdict: clean }  (again)', labelAt: 'start' }],
      onClean: [{ from: 'w', to: 'qevents', text: 'send api-events: CheckDone { userId, docId, verId, verdict: clean }', labelAt: 'start', fail: 'crash before sending: redelivered, the resume alt sends it' }],
      onBlocked: [{ from: 'w', to: 'qevents', text: 'send api-events: CheckDone { userId, docId, verId, verdict: blocked, regions[] }', labelAt: 'start' }],
      onFailed: failA }),
    { from: 'qevents', to: 'api', text: 'CheckDone | Failed', fail: 'API asleep or down: the event waits; status stays Uploaded' },
    { note: ['No "Checked" status: it tells the user nothing.', 'The API marks the check in an internal column (checkedAt).'], over: 'sql', info: true },
    { from: 'api', to: 'sql', text: 'TX: SET checkedAt=now() [, status=Blocked|Failed] WHERE verId AND checkedAt IS NULL; if clean INSERT Outbox(ExtractRequested); COMMIT', labelAt: 'start', fail: 'rollback: abandon, delivered again' },
    { alt: '[1 row]', ok: true, span: ['api', lastA] },
    { self: 'api', text: 'complete' },
    { else: '[0 rows: a duplicate, an old version, or deleted]' },
    { self: 'api', text: 'complete and ignore' },
    { end: true },
    ...relaySend('qworker', 'worker: ExtractRequested { userId, docId, verId }', 'Uploaded'),
    { section: 'Extract · target: PendingReview within 3 min of the upload' },
    ...extract({ who: 'w', inQ: 'qworker', last: lastA,
      onDone: (how) => [{ from: 'w', to: 'qevents', text: `send api-events: Extracted { userId, docId, verId } ${how}`, labelAt: 'start' }],
      onFailed: failA }),
    ...applyExtracted('qevents', lastA),
    ...apply('qevents', 'Failed { reason }', 'UPDATE Version SET Failed + reason WHERE verId AND status=Uploaded', lastA),
    ...review(lastA),
    ...reads(lastA),
    { section: 'Always: the sweeper (every 5 min)' },
    { from: 'api', to: 'sql', text: 'SELECT Version WHERE status=Uploaded AND updatedAt < now() − 9 min (SLA × 3)', labelAt: 'start' },
    { alt: '[found]', span: ['api', lastA] },
    { from: 'api', to: 'sql', text: 'UPDATE SET Failed(timeout) WHERE status=Uploaded', labelAt: 'start' },
    { self: 'api', text: 'the UI shows "Retry"; the outbox already guarantees every command was sent' },
    { end: true },
  ],
};

// ------------------------------------------------------------------ B and C: pipeline
const lastP = 'oai';
const failP = (who) => (reason) => [{ from: who, to: 'qstatus', text: `send status: Failed { userId, docId, verId, reason: ${reason} }`, labelAt: 'start' }];
const pipeline = (outbox) => [
  ...mask,
  ...upload({ outbox, last: lastP,
    sendCheck: outbox ? [] : [{ from: 'api', to: 'qcheck', text: 'send check: CheckRequested { userId, docId, verId }', labelAt: 'start',
      fail: 'API dies after COMMIT: Uploaded without a message; the sweeper sends it' }] }),
  ...(outbox ? relaySend('qcheck', 'check: CheckRequested { userId, docId, verId }', 'Uploaded') : []),
  { section: 'Checker · target: Blocked, or handed to the extractor, within 1 min of the upload' },
  ...check({ who: 'chk', inQ: 'qcheck', last: lastP,
    onResumeClean: [{ from: 'chk', to: 'qextract', text: 'send extract: ExtractRequested { userId, docId, verId }  (again; the extractor is idempotent)', labelAt: 'start' }],
    onClean: [{ from: 'chk', to: 'qextract', text: 'send extract: ExtractRequested { userId, docId, verId }', labelAt: 'start', fail: 'crash before sending: redelivered, the resume alt sends it' }],
    onBlocked: [{ from: 'chk', to: 'qstatus', text: 'send status: Blocked { userId, docId, verId, regions[]: {page,x,y,w,h,rule} }', labelAt: 'start' }],
    onFailed: failP('chk') }),
  { note: ['No "Checked" status: a clean document goes straight on to the extractor.', 'One version gets exactly one of: Blocked, Extracted, Failed.'], over: 'sql', info: true },
  ...apply('qstatus', 'Blocked | Failed', 'UPDATE Version SET Blocked + regions | Failed + reason WHERE verId AND status=Uploaded', lastP),
  { section: 'Extractor · target: PendingReview within 3 min of the upload' },
  ...extract({ who: 'ext', inQ: 'qextract', last: lastP,
    onDone: (how) => [{ from: 'ext', to: 'qstatus', text: `send status: Extracted { userId, docId, verId } ${how}`, labelAt: 'start' }],
    onFailed: failP('ext') }),
  ...applyExtracted('qstatus', lastP),
  ...apply('qstatus', 'Failed { reason }', 'UPDATE Version SET Failed + reason WHERE verId AND status=Uploaded', lastP),
  ...review(lastP),
  ...reads(lastP),
  { section: 'Always: the sweeper (every 5 min while the API is awake; a cron rule wakes it once a day)' },
  { from: 'api', to: 'sql', text: 'SELECT Version WHERE status=Uploaded AND updatedAt < now() − 10 min', labelAt: 'start' },
  ...(outbox
    ? [{ alt: '[found]', span: ['api', lastP] },
       { from: 'api', to: 'sql', text: 'UPDATE SET Failed(timeout) WHERE status=Uploaded', labelAt: 'start' },
       { self: 'api', text: 'the UI shows "Retry"; the outbox already guarantees the message was sent' },
       { end: true }]
    : [{ alt: '[found and resends < 3]', span: ['api', lastP] },
       { from: 'api', to: 'qcheck', text: 'send check: CheckRequested { userId, docId, verId }  (again; the checker is idempotent)', labelAt: 'start' },
       { from: 'api', to: 'sql', text: 'UPDATE SET resends = resends + 1, updatedAt = now()', labelAt: 'start' },
       { else: '[found and resends = 3]' },
       { from: 'api', to: 'sql', text: 'UPDATE SET Failed(timeout) WHERE status=Uploaded', labelAt: 'start' },
       { self: 'api', text: 'the UI shows "Retry"' },
       { end: true }]),
];
const parts = (outbox) => [P.ui, P.api, P.sql, ...(outbox ? [P.relay] : []), P.inc, P.clean, P.text, P.qcheck, P.chk, P.qextract, P.ext, P.qstatus, P.di, P.oai];
const B = { file: 'b-pipeline-with-outbox', title: 'B · pipeline: each stage hands work to the next queue (with outbox)',
  subtitle: 'Work: check → extract. Stages report to the status queue (read only by the API) when the user should know. ' + SUB,
  colW: 200, participants: parts(true), steps: pipeline(true) };
const C = { file: 'c-pipeline-without-outbox', title: 'C · pipeline without an outbox',
  subtitle: 'Like B, but the API sends to Service Bus itself after COMMIT, and the sweeper resends a lost message. ' + SUB,
  colW: 200, participants: parts(false), steps: pipeline(false) };
[A, B, C].forEach((d) => render(d, out));
