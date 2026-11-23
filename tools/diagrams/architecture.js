// Generates docs/architecture.svg.
// Usage: node architecture.js
const fs = require('fs');
const path = require('path');

const out = process.argv[2] || path.join(__dirname, '../../docs');
const W = 2000, H = 1170;
const C = {
  ink: '#1f2933', muted: '#52606d', line: '#3e4c59',
  net: '#e3f2fd', netS: '#1565c0',
  py: '#fff4e5', pyS: '#e65100',
  store: '#eef5ea', storeS: '#2e7d32',
  sec: '#f3e8fd', secS: '#6a1b9a',
  ai: '#e8f4f8', aiS: '#00838f',
  ext: '#f5f5f5', extS: '#616161',
  raw: '#c62828', masked: '#00838f',
};
const esc = s => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
let s = [];

function box(x, y, w, h, fill, stroke, title, lines = [], opts = {}) {
  s.push(`<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="8" fill="${fill}" stroke="${stroke}" stroke-width="2"/>`);
  const align = opts.left ? 'start' : 'middle';
  const tx = opts.left ? x + 14 : x + w / 2;
  const total = 20 + lines.length * 18;
  let ty = opts.top ? y + 26 : y + (h - total) / 2 + 16;
  s.push(`<text x="${tx}" y="${ty}" text-anchor="${align}" font-weight="bold" font-size="15" fill="${C.ink}">${esc(title)}</text>`);
  for (const l of lines) { ty += 19; s.push(`<text x="${tx}" y="${ty}" text-anchor="${align}" font-size="12.5" fill="${C.muted}">${esc(l)}</text>`); }
}
function zone(x, y, w, h, color, label, dash = '10 6') {
  s.push(`<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="12" fill="none" stroke="${color}" stroke-width="2" stroke-dasharray="${dash}"/>`);
  s.push(`<text x="${x + 14}" y="${y + 22}" font-size="13" font-weight="bold" fill="${color}">${esc(label)}</text>`);
}
function arrow(pts, label, opts = {}) {
  const d = pts.map((p, i) => (i ? 'L' : 'M') + p[0] + ' ' + p[1]).join(' ');
  const color = opts.color || C.line;
  s.push(`<path d="${d}" fill="none" stroke="${color}" stroke-width="2" ${opts.dash ? 'stroke-dasharray="6 5"' : ''} marker-end="url(#arr${opts.color ? '-' + opts.color.slice(1) : ''})"/>`);
  if (label) {
    const [lx, ly] = opts.at;
    const anchor = opts.anchor || 'middle';
    s.push(`<text x="${lx}" y="${ly}" text-anchor="${anchor}" font-size="12" fill="${color}" paint-order="stroke" stroke="#ffffff" stroke-width="4">${esc(label)}</text>`);
  }
}

// ---- content (shifted down by 60 for the title) ----
s.push('<g transform="translate(0,60)">');

zone(330, 40, 1650, 760, C.extS, 'Azure subscription · Sweden Central · Managed Identity, no keys · everything scales to zero', '4 4');
zone(15, 100, 295, 400, C.raw, 'User device · raw zone');
zone(1705, 110, 265, 330, C.masked, 'Managed AI · masked data only');
zone(740, 545, 940, 200, C.storeS, 'Blob Storage · paths {userId}/{docId}/{verId}');
zone(15, 850, 1965, 200, C.extS, 'Development · outside Azure', '4 4');

// user device: the original never leaves it
box(30, 140, 265, 340, C.ext, C.extS, 'UI · browser', ['React + TypeScript', 'the original stays here', '1. PDF → PNG (PDF.js)', '2. OCR (Tesseract.js)', '3. zone masking, leak check', '4. user approves the masks', '5. ZIP of masked pages', 'results, trends, review, chat', 'chat history: this tab only'], { left: true, top: true });
box(30, 560, 265, 110, C.sec, C.secS, 'Entra External ID', ['sign-in: Google or e-mail code', 'by invitation; sign-up disabled', 'free up to 50k users/month']);

// API
box(370, 110, 310, 360, C.net, C.netS, 'Baseline API', ['.NET 10 · Container App', 'serves the UI (BFF, one domain)', 'OIDC sign-in (cert. in Key Vault)', 'consent: stored, revocable', 'upload, review, results', 'agent: Agent Framework + MEAI', '  tools: SQL, vector search', '  guardrails: numbers, citations', 'status consumer, sweeper', 'deletion of documents, account'], { left: true, top: true });
box(370, 560, 310, 160, C.store, C.storeS, 'Azure SQL', ['serverless, free offer, auto-pause', 'users, consent, documents,', 'versions, results, vectors', 'Row-Level Security by userId']);

// pipeline
box(735, 150, 135, 70, C.ext, C.extS, 'queue: check', ['Service Bus Basic']);
box(925, 110, 265, 200, C.py, C.pyS, 'Checker', ['Python · Container App', 'no role on AI services (RBAC)', 'verify page hashes', 'shape check, OCR + zone rules', 'fail-closed, nothing stored', 'scales on the queue'], { left: true, top: true });
box(1245, 150, 135, 70, C.ext, C.extS, 'queue: extract', ['Service Bus Basic']);
box(1435, 110, 245, 200, C.py, C.pyS, 'Extractor', ['Python · Container App', 'ZIP → PDF in memory', 'DI layout + LLM → JSON', 'pydantic validation', 'results saved for resume', 'scales on the queue'], { left: true, top: true });
box(1100, 390, 160, 70, C.ext, C.extS, 'queue: status', ['Service Bus Basic']);

// storage
box(765, 590, 270, 130, C.store, C.storeS, 'incoming', ['masked ZIP from the API', 'deleted after the check', 'lifecycle: 24 h']);
box(1075, 590, 270, 130, C.store, C.storeS, 'clean', ['checked masked ZIP', 'review, sources']);
box(1385, 590, 270, 130, C.store, C.storeS, 'text', ['words + bbox, results', 'highlighting, resume']);

// managed AI
box(1725, 150, 225, 100, C.ai, C.aiS, 'Document Intelligence', ['prebuilt-layout, S0']);
box(1725, 280, 225, 140, C.ai, C.aiS, 'Azure OpenAI', ['gpt-5.4 mini', 'text-embedding-3-small', 'Data Zone EU']);

// operations
box(1725, 545, 225, 110, C.ext, C.extS, 'Application Insights', ['all services', 'ids only, no content', 'tokens and cost']);
box(1725, 675, 225, 100, C.sec, C.secS, 'Key Vault', ['sign-in certificate for', 'Entra External ID (API)']);

// development
box(40, 900, 320, 120, C.ext, C.extS, 'VPS · Claude Code', ['writes code, no local build', 'hook: PII and secrets scan', 'subagent: code review']);
box(420, 900, 320, 120, C.ext, C.extS, 'MCP server · project docs', ['local (stdio), no health data', 'ADRs, use cases, criteria']);
box(820, 900, 520, 120, C.ext, C.extS, 'GitHub', ['repo · PR to main merged by the owner', 'Actions: build, tests on emulators, evals,', 'PII scan, deploy with azd + Bicep (OIDC, no secrets)', 'GHCR: container images'], { left: true });

// arrows: user and identity
arrow([[295, 300], [368, 300]], 'masked ZIP', { at: [332, 290], color: C.masked });
arrow([[368, 330], [297, 330]], 'pages, results', { at: [332, 350] });
arrow([[160, 480], [160, 558]], 'sign-in', { at: [170, 525], anchor: 'start' });
arrow([[370, 450], [340, 450], [340, 615], [297, 615]], 'OIDC', { at: [345, 540], anchor: 'start' });

// pipeline
arrow([[680, 185], [733, 185]], null);
arrow([[870, 185], [923, 185]], null);
arrow([[1190, 185], [1243, 185]], 'if clean', { at: [1217, 175] });
arrow([[1380, 185], [1433, 185]], null);
arrow([[1170, 310], [1170, 388]], 'Blocked, Failed', { at: [1160, 360], anchor: 'end' });
arrow([[1500, 310], [1500, 425], [1262, 425]], 'Extracted, Failed', { at: [1380, 415] });
arrow([[1100, 440], [682, 440]], 'status events', { at: [890, 430] });

// API and storage
arrow([[525, 470], [525, 558]], 'EF Core', { at: [535, 520], anchor: 'start' });
arrow([[680, 400], [712, 400], [712, 655], [763, 655]], 'PUT', { at: [738, 647], color: C.masked });
arrow([[620, 470], [620, 510], [1210, 510], [1210, 588]], 'GET pages and words (review, sources); DELETE on deletion', { at: [915, 502], color: C.masked });
arrow([[1210, 510], [1520, 510], [1520, 588]], null, { color: C.masked });

// checker and extractor with storage
arrow([[980, 310], [980, 588]], 'GET, DELETE', { at: [990, 528], anchor: 'start', color: C.masked });
arrow([[1060, 310], [1060, 480], [1120, 480], [1120, 588]], 'PUT', { at: [1128, 528], anchor: 'start', color: C.masked });
arrow([[1460, 310], [1460, 480], [1300, 480], [1300, 588]], 'GET', { at: [1308, 528], anchor: 'start', color: C.masked });
arrow([[1620, 310], [1620, 588]], 'PUT', { at: [1630, 528], anchor: 'start', color: C.masked });

// managed AI
arrow([[1680, 200], [1723, 200]], null, { color: C.masked });
arrow([[1680, 290], [1723, 290]], null, { color: C.masked });
arrow([[525, 110], [525, 85], [1712, 85], [1712, 380], [1723, 380]], 'agent: chat, embeddings (masked results only; questions checked for identifiers)', { at: [1110, 77], color: C.masked });

// development
arrow([[360, 960], [418, 960]], null);
arrow([[420, 980], [362, 980]], null);
arrow([[200, 900], [200, 880], [1080, 880], [1080, 898]], 'push a branch, open a PR', { at: [640, 872] });
arrow([[1340, 960], [1500, 960], [1500, 802]], 'deploy (OIDC)', { at: [1510, 900], anchor: 'start' });

s.push('</g>');

// title + legend
const head = `<text x="30" y="40" font-size="24" font-weight="bold" fill="${C.ink}">Baseline · architecture</text>
<text x="380" y="40" font-size="14" fill="${C.muted}">the decisions behind each part are in docs/adr</text>`;
const lg = [];
let lx = 30, ly = H - 25;
const items = [[C.net, C.netS, '.NET'], [C.py, C.pyS, 'Python'], [C.store, C.storeS, 'storage'], [C.sec, C.secS, 'identity, keys'], [C.ai, C.aiS, 'managed AI service'], [C.ext, C.extS, 'queue, operations, tools']];
lg.push(`<line x1="${lx}" y1="${ly - 4}" x2="${lx + 36}" y2="${ly - 4}" stroke="${C.masked}" stroke-width="2"/>`);
lg.push(`<text x="${lx + 44}" y="${ly + 1}" font-size="13" fill="${C.ink}">masked data only</text>`);
lx += 200;
for (const [f, st, t] of items) {
  lg.push(`<rect x="${lx}" y="${ly - 13}" width="18" height="18" rx="3" fill="${f}" stroke="${st}" stroke-width="2"/>`);
  lg.push(`<text x="${lx + 26}" y="${ly + 1}" font-size="13" fill="${C.ink}">${t}</text>`);
  lx += 40 + t.length * 8;
}

const markers = [C.line, C.secS, C.masked].map(c => `<marker id="arr${c === C.line ? '' : '-' + c.slice(1)}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M0 0 L10 5 L0 10 z" fill="${c}"/></marker>`).join('');

const svg = `<?xml version="1.0" encoding="UTF-8"?>
<!-- Generated by tools/diagrams/architecture.js. Edit the script, not this file. -->
<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" font-family="DejaVu Sans, Arial, sans-serif">
<defs>${markers}</defs>
<rect width="100%" height="100%" fill="#ffffff"/>
${head}
${s.join('\n')}
${lg.join('\n')}
</svg>
`;

fs.writeFileSync(path.join(out, 'architecture.svg'), svg);
console.log('architecture ok');
