// Generates docs/architecture.svg.
// Usage: node architecture.js
const fs = require('fs');
const path = require('path');

const out = process.argv[2] || path.join(__dirname, '../../docs');
const W = 1700, H = 1060;
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

zone(250, 30, 1430, 900, C.extS, 'Azure subscription · EU region · private endpoints · Managed Identity', '4 4');
zone(560, 90, 500, 310, C.raw, 'Raw zone · plaintext original · no internet');
zone(560, 650, 1100, 250, C.masked, 'Managed AI services · masked data only');

// outside Azure
box(30, 440, 180, 100, C.ext, C.extS, 'User', ['browser']);
box(30, 700, 180, 110, C.py, C.pyS, 'Evals', ['Python · pytest', 'GitHub Actions', 'API as a black box']);

// .NET core
box(290, 430, 210, 130, C.net, C.netS, 'Baseline API + UI', ['.NET 10 · ASP.NET Core', 'Entra ID sign-in', 'Agent: Agent Framework', '+ MEAI · RAG']);
box(270, 720, 150, 80, C.store, C.storeS, 'Azure SQL', ['results · EF Core']);

// raw zone
box(590, 130, 200, 100, C.store, C.storeS, 'Quarantine blob', ['DEK wrapped by', 'quarantine-kek', 'deleted after masking']);
box(590, 290, 200, 80, C.ext, C.extS, 'Service Bus', ['import queue']);
box(830, 130, 210, 240, C.py, C.pyS, 'Sanitiser · Python', ['1. PDF → PNG, 300 DPI', '2. in-house OCR (Tesseract)', '3. allowlist masking', '4. denylist + PESEL', '5. leak check, fail-closed'], { left: true, top: true });

// right side
box(1110, 130, 200, 100, C.store, C.storeS, 'Clean blob', ['masked PNG only']);
box(1110, 290, 200, 80, C.sec, C.secS, 'Key Vault', ['quarantine-kek', 'known identifiers']);
box(1380, 130, 270, 130, C.py, C.pyS, 'Extraction worker · Python', ['FastAPI · pydantic', 'structured output', 'chunks + embeddings']);

// managed AI
box(600, 720, 240, 90, C.ai, C.aiS, 'Azure OpenAI', ['EU Data Zone']);
box(900, 720, 240, 90, C.ai, C.aiS, 'Azure AI Search', ['chunks + embeddings']);
box(1380, 720, 240, 90, C.ai, C.aiS, 'Document Intelligence', ['layout + tables']);

// arrows
arrow([[210, 490], [288, 490]], 'HTTPS', { at: [250, 480] });
arrow([[500, 445], [530, 445], [530, 180], [588, 180]], 'upload copy', { at: [522, 300], anchor: 'end' });
arrow([[500, 480], [545, 480], [545, 330], [588, 330]], 'message', { at: [520, 410] , anchor: 'end'});
arrow([[340, 560], [340, 718]], null);
arrow([[790, 180], [828, 180]], null);
arrow([[790, 330], [828, 330]], null);
arrow([[1040, 180], [1108, 180]], null);
arrow([[1040, 330], [1108, 330]], 'unwrap', { at: [1075, 320] });
arrow([[1310, 180], [1378, 180]], null);
arrow([[1420, 260], [1420, 520], [502, 520]], 'results → status: pending review', { at: [960, 510] });
arrow([[1460, 260], [1460, 580], [780, 580], [780, 718]], 'masked text → extraction', { at: [1120, 570] });
arrow([[1500, 260], [1500, 600], [1080, 600], [1080, 718]], 'index', { at: [1290, 616] });
arrow([[1580, 260], [1580, 718]], 'masked PNG', { at: [1590, 480], anchor: 'start' });
arrow([[440, 560], [440, 765], [598, 765]], 'chat · tools', { at: [520, 755] });
arrow([[470, 560], [470, 850], [1020, 850], [1020, 812]], 'retrieval with citations', { at: [745, 868] });
arrow([[210, 750], [240, 750], [240, 535], [288, 535]], null);

s.push('</g>');

// title + legend
const head = `<text x="30" y="40" font-size="24" font-weight="bold" fill="${C.ink}">Baseline · architecture</text>
<text x="380" y="40" font-size="14" fill="${C.muted}">see docs/adr for the decisions behind each part</text>`;
const lg = [];
let lx = 30, ly = H - 25;
const items = [[C.net, C.netS, '.NET'], [C.py, C.pyS, 'Python'], [C.store, C.storeS, 'storage'], [C.sec, C.secS, 'keys and secrets'], [C.ai, C.aiS, 'managed AI service']];
for (const [f, st, t] of items) {
  lg.push(`<rect x="${lx}" y="${ly - 13}" width="18" height="18" rx="3" fill="${f}" stroke="${st}" stroke-width="2"/>`);
  lg.push(`<text x="${lx + 26}" y="${ly + 1}" font-size="13" fill="${C.ink}">${t}</text>`);
  lx += 40 + t.length * 8;
}

const markers = [C.line, C.secS].map(c => `<marker id="arr${c === C.line ? '' : '-' + c.slice(1)}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M0 0 L10 5 L0 10 z" fill="${c}"/></marker>`).join('');

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
