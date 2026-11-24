// Generates docs/sequences/: one sequence diagram per use case of docs/use-cases.md, for the chosen architecture
// (import pipeline C of ADR-0005). Usage: node sequences.js
// SLA targets are proposals, not measurements, except the browser masking times measured in the spike.
const path = require('path');
const render = require('./sequence.js');
const { P, mask, upload, check, extract, apply, applyExtracted, review, browse, ask } = require('./steps.js');

const out = process.argv[2] || path.join(__dirname, '../../docs/sequences');
const X = {
  ...P,
  owner: { id: 'owner', title: 'Owner', sub: 'administrator, by hand', kind: 'local' },
  entra: { id: 'entra', title: 'Entra External ID', sub: 'sign-in; sign-up disabled', kind: 'sec' },
  kv: { id: 'kv', title: 'Key Vault', sub: 'sign-in certificate', kind: 'sec' },
};
const ORDER = ['owner', 'ui', 'entra', 'api', 'kv', 'sql', 'inc', 'clean', 'text', 'qcheck', 'chk', 'qextract', 'ext', 'qstatus', 'di', 'oai'];
const last = 'oai';
const SWEEP = 'Always: the sweeper · every 5 min while the API is awake; a cron scale rule wakes the API once a day';

// The participants of a diagram are the ones its steps use, in a fixed order.
function participantsOf(steps) {
  const used = new Set();
  for (const s of steps) for (const k of ['from', 'to', 'self', 'over']) if (s[k]) used.add(s[k]);
  for (const s of steps) if (s.span) s.span.forEach((p) => used.add(p));
  return ORDER.filter((id) => used.has(id)).map((id) => X[id]);
}
// Frames may name an edge participant the diagram does not have; clamp them to the ones it has.
function clampSpans(steps, parts) {
  const ids = parts.map((p) => p.id);
  const idx = (id) => ORDER.indexOf(id);
  return steps.map((s) => {
    if (!s.span) return s;
    const lo = ids.find((id) => idx(id) >= idx(s.span[0])) || ids[0];
    const hi = [...ids].reverse().find((id) => idx(id) <= idx(s.span[1])) || ids[ids.length - 1];
    return { ...s, span: [lo, hi] };
  });
}
function diagram(file, title, subtitle, steps, colW = 200) {
  const used = participantsOf(steps.filter((s) => !s.span));
  const parts = participantsOf(steps).filter((p) => used.some((u) => u.id === p.id));
  render({ file, title, subtitle, colW, participants: parts, steps: clampSpans(steps, parts) }, out);
}

const COMMON = 'Alternatives are alt frames (success path in green); red ✗ = state after an infrastructure failure. SLA targets are proposals (p95).';
const failP = (who) => (reason) => [{ from: who, to: 'qstatus', text: `send status: Failed { userId, docId, verId, reason: ${reason} }`, labelAt: 'start' }];
const poll = [
  { section: 'Progress in the UI · polling every 3 s while the page is open' },
  { from: 'ui', to: 'api', text: 'GET /documents/{docId}', fail: 'API asleep: waits for the cold start' },
  { from: 'api', to: 'sql', text: 'SELECT Version.status, regions WHERE userId=@me AND docId', labelAt: 'start' },
  { from: 'api', to: 'ui', text: '{ verId, status: Uploaded | Blocked | PendingReview | Approved | Failed, reason?, regions? }', ret: true },
  { note: ['Browser closed: the server carries on.', 'Next visit: the list shows the status, PendingReview opens the review.'], over: 'ui', info: true },
];

// ------------------------------------------------------------------ U1
const u1 = [
  { section: 'U1 · Account · the owner invites each family member by hand; self-service sign-up is disabled in the user flow' },
  { from: 'owner', to: 'entra', text: 'Invite external user { e-mail }  (the Microsoft invitation e-mail off)' },
  { from: 'entra', to: 'owner', text: 'user { oid, state: PendingAcceptance }  (no identity provider yet)', ret: true },
  { from: 'owner', to: 'ui', text: 'own message with the link https://…/?domain_hint=google  (first sign-in only)' },
  { section: 'U1 · Sign in · once, then a session · target: < 2 s after the identity provider' },
  { from: 'ui', to: 'api', text: 'GET /  (no valid session cookie)', fail: 'API asleep: waits for the cold start' },
  { note: ['Every start after sleep is a new container. The cookie keys (ASP.NET Data Protection) are kept', 'in Blob Storage, wrapped by a Key Vault key, so sessions survive sleep and new deployments.'], over: 'api', info: true },
  { from: 'api', to: 'ui', text: '302 → Entra /authorize (code flow, PKCE, state, nonce)', ret: true },
  { from: 'ui', to: 'entra', text: 'sign in with Google, or e-mail with a one-time code (the first sign-in redeems the invitation)', fail: 'Entra down: no sign-in; nothing stored' },
  { alt: '[not invited: sign-up is disabled]', span: ['ui', 'sql'] },
  { from: 'entra', to: 'ui', text: '"account does not exist"; the API is never reached', ret: true },
  { else: '[the user cancels at Google, or Entra returns an error]' },
  { from: 'entra', to: 'ui', text: '302 → /signin-oidc?error=…', ret: true },
  { from: 'ui', to: 'api', text: 'GET /signin-oidc?error=…' },
  { from: 'api', to: 'ui', text: 'page "Sign-in did not finish. Try again."  (nothing stored)', ret: true },
  { else: '[signed in]', ok: true },
  { from: 'entra', to: 'ui', text: '302 → /signin-oidc?code&state', ret: true },
  { from: 'ui', to: 'api', text: 'GET /signin-oidc?code&state' },
  { from: 'api', to: 'kv', text: 'sign the client assertion with the certificate (managed identity; cached)', labelAt: 'start', fail: 'Key Vault down and nothing cached: 503, the user tries again' },
  { from: 'api', to: 'entra', text: 'POST /token { code, client_assertion }', labelAt: 'start', fail: 'code expired or used: as the error alt above' },
  { from: 'entra', to: 'api', text: 'id_token { oid, name }  (tokens stay on the server; e-mail not requested)', ret: true },
  { alt: '[state or nonce does not match]', span: ['ui', 'sql'] },
  { from: 'api', to: 'ui', text: '400, nothing stored', ret: true },
  { else: '[valid]', ok: true },
  { from: 'api', to: 'sql', text: 'SELECT User, Consent(current text version) WHERE User.ExternalId=@oid', labelAt: 'start' },
  { alt: '[User.status = Deleting (U10 still running)]', span: ['ui', 'sql'] },
  { from: 'api', to: 'ui', text: 'page "Your account is being deleted"; no session', ret: true },
  { else: '[no user yet, or an active user]', ok: true },
  { from: 'api', to: 'ui', text: '302 / + Set-Cookie: session { userId } (HttpOnly, Secure, SameSite=Lax; 8 h, sliding)', ret: true },
  { end: true },
  { end: true },
  { end: true },
  { section: 'U1 · Consent · before the first import; withdrawing it is U10' },
  { from: 'ui', to: 'api', text: 'GET /me' },
  { alt: '[no user yet, or consent to an older text version]', span: ['ui', 'sql'] },
  { from: 'api', to: 'ui', text: '{ consentRequired: true, text, version }', ret: true },
  { self: 'ui', text: 'what is stored and processed, by whom and for how long; a checkbox' },
  { alt: '[the person ticks the box]', span: ['ui', 'sql'], ok: true },
  { from: 'ui', to: 'api', text: 'POST /consent { version }' },
  { from: 'api', to: 'sql', text: 'TX: INSERT User(userId = new UUIDv7, ExternalId = oid) (if new); INSERT Consent(userId, version, givenAt); COMMIT', labelAt: 'start', fail: 'rollback: nothing stored; UI asks again' },
  { from: 'api', to: 'ui', text: '204', ret: true },
  { else: '[the person declines, and has an account (a newer consent text)]' },
  { self: 'ui', text: '"Without your consent we must delete your account and all your data." → confirm' },
  { from: 'ui', to: 'api', text: 'DELETE /me → U10' },
  { else: '[the person declines, with no account yet]' },
  { from: 'ui', to: 'api', text: 'POST /signout' },
  { from: 'api', to: 'ui', text: 'cookie cleared; nothing about the person in our database', ret: true },
  { self: 'api', text: 'log ConsentDeclined { oid }  → alert to the owner' },
  { from: 'api', to: 'owner', text: 'alert e-mail: remove the account in Entra (by hand)', labelAt: 'start' },
  { end: true },
  { else: '[consent to the current version exists]', ok: true },
  { from: 'api', to: 'ui', text: '{ user, consentGivenAt }', ret: true },
  { end: true },
  { note: ['The user row is created together with the consent, so a person who declines leaves nothing in our database.', 'Sign-in: oid → User.ExternalId → userId, our own UUIDv7 (ADR-0015). Every later request: cookie → userId; SQL sets SESSION_CONTEXT(userId) for Row-Level Security.'], over: 'sql', info: true },
  { section: 'U1 · Sign out, or the session ends' },
  { from: 'ui', to: 'api', text: 'POST /signout' },
  { from: 'api', to: 'ui', text: 'cookie cleared; 302 → Entra end-session → back to /', ret: true },
  { note: ['After 8 h without a request the cookie expires: the next request is "GET / with no valid session cookie" above.'], over: 'api', info: true },
];

// ------------------------------------------------------------------ U2: import
const u2 = [
  ...mask,
  ...upload({ outbox: false, last,
    sendCheck: [{ from: 'api', to: 'qcheck', text: 'send check: CheckRequested { userId, docId, verId }', labelAt: 'start',
      fail: 'API dies after COMMIT: Uploaded without a message; the sweeper sends it' }] }),
  { section: 'Checker · target: Blocked, or handed to the extractor, within 1 min of the upload' },
  ...check({ who: 'chk', inQ: 'qcheck', last,
    onResumeClean: [{ from: 'chk', to: 'qextract', text: 'send extract: ExtractRequested { userId, docId, verId }  (again; the extractor is idempotent)', labelAt: 'start' }],
    onClean: [{ from: 'chk', to: 'qextract', text: 'send extract: ExtractRequested { userId, docId, verId }', labelAt: 'start', fail: 'crash before sending: redelivered, the resume alt sends it' }],
    onBlocked: [{ from: 'chk', to: 'qstatus', text: 'send status: Blocked { userId, docId, verId, regions[]: {page,x,y,w,h,rule} }  (U4)', labelAt: 'start' }],
    onFailed: failP('chk') }),
  ...apply('qstatus', 'Blocked | Failed', 'UPDATE Version SET Blocked + regions | Failed + reason WHERE verId AND status=Uploaded', last),
  { section: 'Extractor · target: PendingReview within 3 min of the upload' },
  ...extract({ who: 'ext', inQ: 'qextract', last,
    onDone: (how) => [{ from: 'ext', to: 'qstatus', text: `send status: Extracted { userId, docId, verId } ${how}`, labelAt: 'start' }],
    onFailed: failP('ext') }),
  ...applyExtracted('qstatus', last),
  ...apply('qstatus', 'Failed { reason }', 'UPDATE Version SET Failed + reason WHERE verId AND status=Uploaded', last),
  ...poll,
  { section: SWEEP },
  { from: 'api', to: 'sql', text: 'SELECT Version WHERE status=Uploaded AND updatedAt < now() − 10 min', labelAt: 'start' },
  { alt: '[found and resends < 3]', span: ['api', last] },
  { from: 'api', to: 'qcheck', text: 'send CheckRequested again (ExtractRequested for a version made from a checked ZIP, U9); receivers are idempotent', labelAt: 'start' },
  { from: 'api', to: 'sql', text: 'UPDATE SET resends = resends + 1, updatedAt = now()', labelAt: 'start' },
  { else: '[found and resends = 3]' },
  { from: 'api', to: 'sql', text: 'UPDATE SET Failed(timeout) WHERE status=Uploaded', labelAt: 'start' },
  { end: true },
  { note: ['A pipeline down for more than about 30 minutes ends its imports in Failed (timeout).', 'The UI then offers "Retry" (U9).'], over: 'api', info: true },
];

// ------------------------------------------------------------------ U4: blocked
const u4 = [
  { section: 'U4 · Blocked document · about 1 in 10 imports · the user fixes the masks and sends again' },
  { from: 'ui', to: 'api', text: 'GET /documents/{docId}' },
  { from: 'api', to: 'sql', text: 'SELECT newest Version WHERE userId=@me AND docId', labelAt: 'start' },
  { from: 'api', to: 'ui', text: '{ verId, status: Blocked, regions[]: { page, x, y, w, h, rule } }  (no text)', ret: true },
  { note: ['The server kept nothing of the pages: the checker deleted them.', 'The user needs their own original again.'], over: 'api', info: true },
  { alt: '[the original is still open in this tab]', span: ['ui', 'sql'], ok: true },
  { self: 'ui', text: 'show the regions on the local masked pages', flow: 'raw' },
  { else: '[the tab was closed]' },
  { self: 'ui', text: 'the user picks the original file again; render, OCR and mask again', flow: 'raw' },
  { alt: '[originalSha256 ≠ the document\'s]', span: ['ui', 'sql'] },
  { self: 'ui', text: '"This is a different file": start a new import instead (U2)' },
  { end: true },
  { end: true },
  { self: 'ui', text: 'the user draws mask boxes over the regions (masking can be added, never removed) and approves', flow: 'raw' },
  { from: 'ui', to: 'api', text: 'POST /documents/{docId}/versions (application/zip: pages + manifest)', flow: 'masked', labelAt: 'start', fail: 'network error: the UI sends the same ZIP again; the zipSha256 index returns the version made by the first try' },
  { self: 'api', text: 'validate as in U2; zipSha256 = SHA-256 of the ZIP' },
  { from: 'api', to: 'sql', text: 'SELECT Document WHERE userId=@me AND docId (else 404); SELECT Version WHERE docId AND ((zipSha256=@z AND status IN (Uploaded, Blocked, PendingReview, Approved)) OR newest status=Uploaded)', labelAt: 'start' },
  { alt: '[same zipSha256, a live version: a retry]', span: ['ui', 'sql'] },
  { from: 'api', to: 'ui', text: '200 { verId, status }  (the version made by the first try)', ret: true },
  { else: '[the newest version is still Uploaded]' },
  { from: 'api', to: 'ui', text: '409 { status: Uploaded }  (wait for it to finish)', ret: true },
  { else: '[new]', ok: true },
  { self: 'api', text: 'verId = new UUIDv7' },
  { from: 'api', to: 'inc', text: 'PUT incoming/{userId}/{docId}/{verId}.zip', flow: 'masked', labelAt: 'start' },
  { from: 'api', to: 'sql', text: 'TX: INSERT Version(Uploaded, zipSha256; UNIQUE docId + zipSha256 among live versions, ADR-0016); SET Superseded on older Blocked, PendingReview versions; DELETE older Failed versions (ADR-0016); COMMIT', labelAt: 'start', fail: 'unique violation (parallel retry): 200 with that version; this try\'s incoming ZIP is an orphan, the lifecycle deletes it after 24 h' },
  { from: 'api', to: 'clean', text: 'DELETE the blobs of the deleted Failed versions (incoming, clean, text)', labelAt: 'start', fail: 'API dies here: orphan blobs; the daily orphan sweep deletes them' },
  { from: 'api', to: 'qcheck', text: 'send check: CheckRequested { userId, docId, verId }', labelAt: 'start', fail: 'API dies here: the sweeper sends it' },
  { from: 'api', to: 'ui', text: '202 { verId, status: Uploaded }', ret: true },
  { end: true },
  { note: ['From here on exactly as U2: checker, extractor, status, review.', 'The blocked version stays as history (Superseded, with its regions); the UI shows the newest version.'], over: 'api', info: true },
  { from: 'qcheck', to: 'chk', text: 'CheckRequested … (as in U2)' },
];

// ------------------------------------------------------------------ U7: summary
const u7 = [
  { section: 'U7 · Pre-visit summary · once a month · target: < 30 s when warm; nothing is stored' },
  { self: 'ui', text: 'the user picks a period (default: the last 6 months)' },
  { from: 'ui', to: 'api', text: 'POST /summary { from, to }', fail: 'API asleep: waits for the cold start' },
  { self: 'api', text: 'today\'s summaries < 10, else 429' },
  { from: 'api', to: 'sql', text: 'period_summary: approved results in the period + the last value of each parameter before it; ranges, flags, sources', labelAt: 'start', fail: 'SQL paused: waits; on timeout 503, UI retries' },
  { alt: '[no approved results in the period]', span: ['ui', last] },
  { from: 'api', to: 'ui', text: '200 { empty: true }  (no model call)', ret: true },
  { else: '[results found]', ok: true },
  { from: 'api', to: 'oai', text: 'chat(system: organise, never diagnose; data: rows + sources; task: changes, out of range, questions for the doctor)', labelAt: 'start', fail: 'OpenAI down or 429: the UI shows the tables without the text' },
  { from: 'oai', to: 'api', text: 'summary text + citations[]', ret: true },
  { self: 'api', text: 'guardrail: every number matches a row; every claim cites a row; out of range only from flags computed by code' },
  { alt: '[passed]', span: ['ui', last], ok: true },
  { from: 'api', to: 'ui', text: '{ text, tables, citations }', ret: true },
  { else: '[failed]' },
  { from: 'api', to: 'ui', text: '{ tables, citations, note: "ask your doctor" }  (no generated text)', ret: true },
  { end: true },
  { end: true },
  { self: 'ui', text: 'printable page; the user prints it or saves it as PDF in the browser' },
  { note: ['The summary is not stored on the server.', 'Generating it again gives the same facts, because they come from stored results.'], over: 'api', info: true },
];

// ------------------------------------------------------------------ U8: delete a document
const deleteBlobs = (prefix) => [
  { from: 'api', to: 'inc', text: `DELETE every blob under incoming/${prefix}`, labelAt: 'start' },
  { from: 'api', to: 'clean', text: `DELETE every blob under clean/${prefix}`, labelAt: 'start' },
  { from: 'api', to: 'text', text: `DELETE every blob under text/${prefix}`, labelAt: 'start', fail: 'API dies here: the marker stays; the sweeper finishes the blobs' },
];
const u8 = [
  { section: 'U8 · Delete a document · about once a quarter · target: confirmation < 2 s, done < 5 min' },
  { self: 'ui', text: '"Delete this document and its results? This cannot be undone." → confirm' },
  { from: 'ui', to: 'api', text: 'DELETE /documents/{docId}' },
  { from: 'api', to: 'sql', text: 'TX: DELETE Fragments, LabResults, Extractions, Versions, Document WHERE userId=@me AND docId; if 0 rows: ROLLBACK; else INSERT DeletionMarker(prefix = {userId}/{docId}/); COMMIT', labelAt: 'start',
    fail: 'rollback: nothing deleted; 500, UI retries' },
  { alt: '[0 rows: not this user\'s document, or deleted already]', span: ['ui', last] },
  { from: 'api', to: 'ui', text: '404', ret: true },
  { else: '[deleted]', ok: true },
  { from: 'api', to: 'ui', text: '202  (gone from the application at once)', ret: true },
  ...deleteBlobs('{userId}/{docId}/'),
  { from: 'api', to: 'sql', text: 'DELETE DeletionMarker', labelAt: 'start', fail: 'not deleted: the sweeper deletes the blobs again (no error if already gone) and removes it' },
  { end: true },
  { section: 'A pipeline still running for this document' },
  { from: 'qextract', to: 'ext', text: 'ExtractRequested { userId, docId, verId }' },
  { from: 'ext', to: 'clean', text: 'GET clean/{userId}/{docId}/{verId}.zip', flow: 'masked' },
  { alt: '[ZIP missing: deleted]', span: ['api', last] },
  { self: 'ext', text: 'nothing to do; complete' },
  { else: '[the ZIP was read before the delete]' },
  { self: 'ext', text: 'extraction as in U2' },
  { from: 'ext', to: 'text', text: 'PUT text/{userId}/{docId}/{verId}.json  (a late orphan)', flow: 'masked', labelAt: 'start' },
  { from: 'ext', to: 'qstatus', text: 'send status: Extracted { … }', labelAt: 'start' },
  { from: 'qstatus', to: 'api', text: 'Extracted' },
  { from: 'api', to: 'sql', text: 'INSERT … WHERE the version exists → 0 rows: complete and ignore', labelAt: 'start' },
  { end: true },
  { section: SWEEP },
  { from: 'api', to: 'sql', text: 'SELECT DeletionMarker', labelAt: 'start' },
  { alt: '[marker found]', span: ['api', last] },
  ...deleteBlobs('{prefix}'),
  { from: 'api', to: 'sql', text: 'DELETE DeletionMarker', labelAt: 'start' },
  { end: true },
  { from: 'api', to: 'text', text: 'list the text/ and clean/ prefixes (once a day)', labelAt: 'start' },
  { alt: '[a blob whose version does not exist: the extractor\'s late text, a clean ZIP the checker wrote during the delete, a failed U9 copy]', span: ['api', last] },
  { from: 'api', to: 'text', text: 'DELETE the orphan blob', labelAt: 'start' },
  { end: true },
  { note: ['SQL backups keep the deleted rows for 7 days. Masked data may stay in Azure OpenAI', 'for up to 30 days and in Document Intelligence for up to 24 hours (ADR-0012).'], over: 'sql', info: true },
];

// ------------------------------------------------------------------ U9: reprocess or retry
const u9 = [
  { section: 'U9 · Reprocess after an extraction fix, or "Retry" after Failed · the user starts it for one document' },
  { from: 'ui', to: 'api', text: 'POST /documents/{docId}/reprocess' },
  { from: 'api', to: 'sql', text: 'SELECT newest Version WHERE userId=@me AND docId', labelAt: 'start' },
  { from: 'api', to: 'clean', text: 'HEAD clean/{userId}/{docId}/{verOld}.zip', labelAt: 'start' },
  { alt: '[status = Uploaded: still processing]', span: ['ui', last] },
  { from: 'api', to: 'ui', text: '409 { status: Uploaded }', ret: true },
  { else: '[no clean ZIP: Blocked, or Failed before the check passed (integrity, check_error, timeout)]' },
  { from: 'api', to: 'ui', text: '409 { needsOriginal: true }', ret: true },
  { self: 'ui', text: '"Pick the original again": mask and send a new version, as U4' },
  { else: '[clean ZIP present: PendingReview, Approved, Failed in extraction (extract_*, no_results, timeout)]', ok: true },
  { self: 'api', text: 'verNew = new UUIDv7' },
  { from: 'api', to: 'clean', text: 'COPY clean/{userId}/{docId}/{verOld}.zip → {verNew}.zip  (server-side copy; same bytes and page hashes)', flow: 'masked', labelAt: 'start', fail: 'copy fails: 503, nothing changed' },
  { from: 'api', to: 'sql', text: 'TX: INSERT Version(verNew, Uploaded, reprocessOf = verOld); SET Superseded on older Blocked, PendingReview versions; DELETE older Failed versions, verOld too if Failed (ADR-0016); COMMIT', labelAt: 'start', fail: 'rollback: an orphan copy; the daily orphan sweep deletes it' },
  { from: 'api', to: 'clean', text: 'DELETE the blobs of the deleted Failed versions (incoming, clean, text)', labelAt: 'start', fail: 'API dies here: orphan blobs; the daily orphan sweep deletes them' },
  { from: 'api', to: 'qextract', text: 'send extract: ExtractRequested { userId, docId, verId: verNew }  (the pages were checked already)', labelAt: 'start', fail: 'API dies here: the sweeper resends ExtractRequested for versions made from a checked ZIP' },
  { from: 'api', to: 'ui', text: '202 { verId: verNew }', ret: true },
  { end: true },
  { note: ['An Approved version stays the one that is read until the user approves the new one (review as in U3);', 'then it becomes Archived. A PendingReview version is Superseded at once: the newer one matters more.'], over: 'sql', info: true },
  { from: 'qextract', to: 'ext', text: 'ExtractRequested … (as in U2, Extractor)' },
  { section: 'U9 · Reprocess after a masking fix · the user imports the original again' },
  { self: 'ui', text: 'the user picks the original; originalSha256 = the same', flow: 'raw' },
  { from: 'ui', to: 'api', text: 'GET /documents?originalSha256={h}  (before masking, as in U2)' },
  { from: 'api', to: 'sql', text: 'SELECT Document WHERE userId=@me AND originalSha256=@h → found', labelAt: 'start' },
  { from: 'api', to: 'ui', text: '200 { docId, newest version and status }', ret: true },
  { self: 'ui', text: '"Imported already. Import as a new version?" → yes; mask with the fixed rules' },
  { from: 'ui', to: 'api', text: 'POST /documents/{docId}/versions (ZIP) → as in U4: check, extract, review', flow: 'masked', labelAt: 'start' },
];

// ------------------------------------------------------------------ U10: delete the account
const u10 = [
  { section: 'U10 · Delete the account, or withdraw consent · once · target: our data gone < 1 h; the Entra account removed by the owner' },
  { self: 'ui', text: '"Withdraw consent and delete everything? This cannot be undone." → confirm' },
  { from: 'ui', to: 'api', text: 'DELETE /me  (also POST /consent/withdraw)' },
  { from: 'api', to: 'sql', text: 'TX: SET User.status = Deleting; INSERT DeletionMarker(prefix = {userId}/, oid); DELETE Consent; COMMIT', labelAt: 'start', fail: 'rollback: nothing changed; 500, UI retries' },
  { from: 'api', to: 'ui', text: '202; session cookie cleared; signed out', ret: true },
  { note: ['From now on a sign-in with this oid shows "Your account is being deleted" (U1),', 'and status events for its documents change 0 rows.'], over: 'api', info: true },
  ...deleteBlobs('{userId}/'),
  { from: 'api', to: 'sql', text: 'TX: DELETE Fragments, LabResults, Extractions, Versions, Documents, DailyUsage WHERE userId; DELETE User; COMMIT  (aliases are shared: kept)', labelAt: 'start', fail: 'API dies here: the marker stays; the sweeper repeats both steps (idempotent)' },
  { self: 'api', text: 'log AccountDeleted { oid }  (an identifier only) → alert rule' },
  { from: 'api', to: 'owner', text: 'alert e-mail: remove the account { oid } in Entra', labelAt: 'start' },
  { from: 'api', to: 'sql', text: 'DELETE DeletionMarker', labelAt: 'start' },
  { from: 'owner', to: 'entra', text: 'delete the user { oid } by hand; then delete it permanently from "Deleted users"', fail: 'not done: the e-mail stays in Entra; the soft-deleted user is purged by Entra after 30 days' },
  { note: ['Until the owner removes the account, the person can still sign in. With no User row they see', 'the consent screen again (U1): a new, empty account is made only if they consent again.'], over: 'entra', info: true },
  { section: SWEEP },
  { from: 'api', to: 'sql', text: 'SELECT DeletionMarker', labelAt: 'start' },
  { alt: '[marker of an account found]', span: ['api', last] },
  { self: 'api', text: 'repeat: blobs under {userId}/, rows, the AccountDeleted log (oid from the marker), marker' },
  { end: true },
];

// ------------------------------------------------------------------ U11: export
const u11 = [
  { section: 'U11 · Export my data · rarely · target: < 10 s when warm' },
  { from: 'ui', to: 'api', text: 'GET /export?format=json|csv' },
  { from: 'api', to: 'sql', text: 'SELECT Documents, approved LabResults (original and normalised values, ranges, dates, sources), Consent WHERE userId=@me', labelAt: 'start', fail: 'SQL paused: waits; on timeout 503, UI retries' },
  { from: 'api', to: 'ui', text: 'file: results.json or results.csv  (no generated text; nothing logged)', ret: true },
  { alt: '[the user also wants the masked pages of a document]', span: ['ui', 'text'] },
  { from: 'ui', to: 'api', text: 'GET /documents/{docId}/versions/{verId}/pages', labelAt: 'start' },
  { from: 'api', to: 'clean', text: 'GET clean/{userId}/{docId}/{verId}.zip', flow: 'masked' },
  { from: 'api', to: 'ui', text: 'ZIP (masked pages)', ret: true, flow: 'masked' },
  { end: true },
  { note: ['The export is the person\'s own backup: there is no recycle bin and no restore of single documents (ADR-0012).'], over: 'api', info: true },
];

diagram('01-sign-in-and-consent', 'U1 · Account, sign in and consent', 'Accounts by invitation only. Entra External ID through the API (backend for frontend): tokens stay on the server, the browser gets an HTTP-only cookie (ADR-0010). ' + COMMON, u1, 230);
diagram('02-import', 'U2 · Import a lab result', 'Masking in the browser (ADR-0003), the pipeline of queues (ADR-0005), statuses and identifiers (ADR-0006). ' + COMMON, u2);
diagram('03-review', 'U3 · Review and approve the extracted values', 'Every value is checked against the masked page before it is used (ADR-0006); vectors are written on approval (ADR-0008). ' + COMMON, review(last));
diagram('04-blocked-document', 'U4 · Fix a blocked document and send it again', 'The checker found ink or personal data outside the kept regions (ADR-0003). ' + COMMON, u4, 230);
diagram('05-browse-results', 'U5 · Browse results and trends', 'The most frequent use case: SQL only, no AI. ' + COMMON, browse(last), 230);
diagram('06-ask-the-agent', 'U6 · Ask the agent a question', 'One agent with tools and guardrails, identifiers blocked in questions (ADR-0009), vectors in Azure SQL (ADR-0008). ' + COMMON, ask(last), 230);
diagram('07-pre-visit-summary', 'U7 · Pre-visit summary', 'Generated on demand for a chosen period, never stored (ADR-0009). ' + COMMON, u7, 230);
diagram('08-delete-document', 'U8 · Delete a document', 'A saga with a deletion marker, finished by the sweeper after a crash (ADR-0012). ' + COMMON, u8);
diagram('09-reprocess-document', 'U9 · Reprocess or retry a document', 'A new version of the same document; an approved one stays readable until the new one is approved (ADR-0006). ' + COMMON, u9);
diagram('10-delete-account', 'U10 · Delete the account or withdraw consent', 'Everything of a person lies under one prefix and one userId (ADR-0006, 0012); the owner removes the Entra account by hand (ADR-0010). ' + COMMON, u10, 230);
diagram('11-export', 'U11 · Export my data', 'Approved results with their sources; masked pages per document. ' + COMMON, u11, 230);
