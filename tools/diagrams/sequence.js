// Sequence diagram renderer. Used by the scripts in this folder; it is not run on its own.
const fs = require('fs');
const path = require('path');


const KIND = {
  user: ['#f5f5f5', '#616161'],
  net: ['#e3f2fd', '#1565c0'],
  py: ['#fff4e5', '#e65100'],
  store: ['#eef5ea', '#2e7d32'],
  sec: ['#f3e8fd', '#6a1b9a'],
  ai: ['#e8f4f8', '#00838f'],
  queue: ['#f5f5f5', '#616161'],
  local: ['#f3e8fd', '#6a1b9a'],
};
const INK = '#1f2933', MUTED = '#52606d', LINE = '#3e4c59';
const FLOW = { raw: '#c62828', masked: '#00838f', normal: LINE };
const esc = s => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

function render({ file, title, subtitle, participants, steps, colW = 160 }, out) {
  fs.mkdirSync(out, { recursive: true });
  const X0 = 40 + colW / 2;
  const x = {};
  participants.forEach((p, i) => (x[p.id] = X0 + i * colW));
  const W = X0 + (participants.length - 1) * colW + colW / 2 + 40;
  const HEAD_Y = 80, HEAD_H = 56;
  let y = HEAD_Y + HEAD_H + (steps[0].section ? 30 : 46);
  let n = 0;
  const body = [];
  const frames = [];
  const bg = [];
  const halo = 'paint-order="stroke" stroke="#ffffff" stroke-width="4"';

  for (const st of steps) {
    if (st.section) {
      y += 14;
      body.push(`<line x1="20" y1="${y}" x2="${W - 20}" y2="${y}" stroke="#cbd2d9" stroke-width="1"/>`);
      body.push(`<text x="24" y="${y - 6}" font-size="13" font-weight="bold" fill="${MUTED}">${esc(st.section)}</text>`);
      y += 26;
    } else if (st.note) {
      const lines = Array.isArray(st.note) ? st.note : [st.note];
      const w = Math.max(...lines.map(l => l.length)) * 7.1 + 24;
      const h = 12 + lines.length * 17;
      let nx = x[st.over] - w / 2;
      nx = Math.max(20, Math.min(nx, W - 20 - w));
      const [nf, ns] = st.info ? ['#eceff1', '#546e7a'] : ['#fff8c5', '#b7950b'];
      body.push(`<path d="M${nx} ${y} h${w - 12} l12 12 v${h - 12} h-${w} z" fill="${nf}" stroke="${ns}" stroke-width="1.5"/>`);
      lines.forEach((l, i) => body.push(`<text x="${nx + 12}" y="${y + 20 + i * 17}" font-size="12" fill="${INK}" ${i === 0 ? 'font-weight="bold"' : ''}>${esc(l)}</text>`));
      y += h + 30;
    } else if (st.alt) {
      { const d = frames.length * 12; frames.push({ x1: x[st.span[0]] - colW / 2 + 12 + d, x2: x[st.span[1]] + colW / 2 - 12 - d, y1: y, label: st.alt, ok: st.ok, d, elses: [] }); }
      y += 44;
    } else if (st.else) {
      const f = frames[frames.length - 1];
      f.elses.push({ y, label: st.else, ok: st.ok });
      y += 40;
    } else if (st.end) {
      const f = frames.pop();
      y += 4;
      { const cuts = [{ y: f.y1, ok: f.ok }, ...f.elses.map(e => ({ y: e.y, ok: e.ok }))];
        cuts.forEach((c, i) => { const y2 = i + 1 < cuts.length ? cuts[i + 1].y : y;
          if (!c.ok) { bg.push({ d: f.d, s: `<rect x="${f.x1}" y="${c.y}" width="${f.x2 - f.x1}" height="${y2 - c.y}" fill="#ffffff"/>` }); return; }
          bg.push({ d: f.d, s: `<rect x="${f.x1}" y="${c.y}" width="${f.x2 - f.x1}" height="${y2 - c.y}" fill="#e8f5e9"/>` });
          bg.push({ d: f.d, s: `<rect x="${f.x1}" y="${c.y}" width="5" height="${y2 - c.y}" fill="#2e7d32"/>` }); }); }
      body.push(`<rect x="${f.x1}" y="${f.y1}" width="${f.x2 - f.x1}" height="${y - f.y1}" fill="none" stroke="${MUTED}" stroke-width="1.5"/>`);
      body.push(`<path d="M${f.x1} ${f.y1} h46 v14 l-8 8 h-38 z" fill="#e4e7eb" stroke="${MUTED}" stroke-width="1.5"/>`);
      body.push(`<text x="${f.x1 + 8}" y="${f.y1 + 16}" font-size="12" font-weight="bold" fill="${INK}">alt</text>`);
      body.push(`<text x="${f.x1 + 56}" y="${f.y1 + 16}" font-size="12" fill="${INK}">${esc(f.label)}</text>`);
      for (const e of f.elses) {
        body.push(`<line x1="${f.x1}" y1="${e.y}" x2="${f.x2}" y2="${e.y}" stroke="${MUTED}" stroke-width="1.5" stroke-dasharray="6 4"/>`);
        body.push(`<text x="${f.x1 + 8}" y="${e.y + 16}" font-size="12" fill="${INK}">${esc(e.label)}</text>`);
      }
      y += 22;
    } else if (st.self) {
      n++;
      const cx = x[st.self];
      const color = FLOW[st.flow || 'normal'];
      body.push(`<path d="M${cx} ${y} h28 v18 h-24" fill="none" stroke="${color}" stroke-width="2" marker-end="url(#a-${(st.flow || 'normal')})"/>`);
      body.push(`<text x="${cx + 36}" y="${y + 13}" font-size="12.5" fill="${color === LINE ? INK : color}" ${halo}>${n}. ${esc(st.text)}</text>`);
      if (st.fail) { body.push(`<text x="${cx + 36}" y="${y + 31}" font-size="11.5" font-style="italic" fill="#c62828" ${halo}>✗ ${esc(st.fail)}</text>`); y += 12; }
      y += 50;
    } else {
      n++;
      const x1 = x[st.from], x2 = x[st.to];
      const flow = st.flow || 'normal';
      const color = FLOW[flow];
      const dir = x2 > x1 ? 1 : -1;
      body.push(`<line x1="${x1}" y1="${y}" x2="${x2 - dir * 3}" y2="${y}" stroke="${color}" stroke-width="2" ${st.ret ? 'stroke-dasharray="7 5"' : ''} marker-end="url(#a-${flow})"/>`);
      const lx = st.labelAt === 'start' ? x1 + dir * 8 : (x1 + x2) / 2;
      const anchor = st.labelAt === 'start' ? (dir > 0 ? 'start' : 'end') : 'middle';
      body.push(`<text x="${lx}" y="${y - 7}" text-anchor="${anchor}" font-size="12.5" fill="${color === LINE ? INK : color}" ${halo}>${n}. ${esc(st.text)}</text>`);
      if (st.fail) { body.push(`<text x="${lx}" y="${y + 16}" text-anchor="${anchor}" font-size="11.5" font-style="italic" fill="#c62828" ${halo}>✗ ${esc(st.fail)}</text>`); y += 18; }
      y += 38;
    }
  }
  const END = y + 10;
  const H = END + HEAD_H + 70;

  const head = [];
  for (const p of participants) {
    const [f, s] = KIND[p.kind];
    const bx = x[p.id] - (colW - 20) / 2, bw = colW - 20;
    for (const by of [HEAD_Y, END]) {
      head.push(`<rect x="${bx}" y="${by}" width="${bw}" height="${HEAD_H}" rx="8" fill="${f}" stroke="${s}" stroke-width="2"/>`);
      head.push(`<text x="${x[p.id]}" y="${by + 24}" text-anchor="middle" font-size="14" font-weight="bold" fill="${INK}">${esc(p.title)}</text>`);
      head.push(`<text x="${x[p.id]}" y="${by + 43}" text-anchor="middle" font-size="12" fill="${MUTED}">${esc(p.sub)}</text>`);
    }
    head.push(`<line x1="${x[p.id]}" y1="${HEAD_Y + HEAD_H}" x2="${x[p.id]}" y2="${END}" stroke="#9aa5b1" stroke-width="1.5" stroke-dasharray="4 4"/>`);
  }

  const ly = H - 22;
  const legend = [
    [FLOW.raw, false, 'plaintext original or unmasked personal data'],
    [FLOW.masked, false, 'masked data only'],
    [LINE, false, 'call'],
    [LINE, true, 'response'],
  ];
  let lx = 40;
  const lg = [];
  for (const [c, dash, t] of legend) {
    lg.push(`<line x1="${lx}" y1="${ly - 4}" x2="${lx + 40}" y2="${ly - 4}" stroke="${c}" stroke-width="2" ${dash ? 'stroke-dasharray="7 5"' : ''}/>`);
    lg.push(`<text x="${lx + 50}" y="${ly}" font-size="13" fill="${INK}">${t}</text>`);
    lx += 70 + t.length * 7.6;
  }
  lg.push(`<path d="M${lx} ${ly - 14} h30 l10 10 v10 h-40 z" fill="#fff8c5" stroke="#b7950b" stroke-width="1.5"/>`);
  lg.push(`<text x="${lx + 50}" y="${ly}" font-size="13" fill="${INK}">open question</text>`);
  lx += 180;
  lg.push(`<path d="M${lx} ${ly - 14} h30 l10 10 v10 h-40 z" fill="#eceff1" stroke="#546e7a" stroke-width="1.5"/>`);
  lg.push(`<text x="${lx + 50}" y="${ly}" font-size="13" fill="${INK}">note: a fact, e.g. the user closes the browser</text>`);
  lx += 260;
  lg.push(`<rect x="${lx}" y="${ly - 14}" width="40" height="18" fill="#e8f5e9"/><rect x="${lx}" y="${ly - 14}" width="5" height="18" fill="#2e7d32"/>`);
  lg.push(`<text x="${lx + 50}" y="${ly}" font-size="13" fill="${INK}">success path in an alt</text>`);
  lx += 240;
  lg.push(`<text x="${lx}" y="${ly}" font-size="13" font-style="italic" fill="#c62828">✗ if this step fails: state of the system</text>`);

  const markers = Object.entries(FLOW).map(([k, c]) =>
    `<marker id="a-${k}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M0 0 L10 5 L0 10 z" fill="${c}"/></marker>`).join('');

  const svg = `<?xml version="1.0" encoding="UTF-8"?>
<!-- Generated by a script in tools/diagrams. Edit the script, not this file. -->
<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" font-family="DejaVu Sans, Arial, sans-serif">
<defs>${markers}</defs>
<rect width="100%" height="100%" fill="#ffffff"/>
<text x="40" y="40" font-size="24" font-weight="bold" fill="${INK}">${esc(title)}</text>
<text x="40" y="64" font-size="14" fill="${MUTED}">${esc(subtitle)}</text>
${bg.sort((a, b) => a.d - b.d).map(b => b.s).join('\n')}
${head.join('\n')}
${body.join('\n')}
${lg.join('\n')}
</svg>
`;
  fs.writeFileSync(path.join(out, file + '.svg'), svg);
  console.log(file, 'ok');
}

module.exports = render;

