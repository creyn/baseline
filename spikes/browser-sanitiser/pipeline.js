// OCR → decisions → keep-only image → leak check. Works in the browser and in Node:
// the caller passes a Tesseract worker and a canvas factory.
import { decideLine, findTable, findLeaks, pageRows } from './rules.js';

// Returns lines of words: [[{ text, confidence, bbox: { x0, y0, x1, y1 } }]]
export async function ocrLines(worker, image) {
  const { data } = await worker.recognize(image, {}, { blocks: true });
  const lines = [];
  for (const block of data.blocks ?? []) {
    for (const para of block.paragraphs) {
      for (const line of para.lines) {
        const words = line.words
          .filter(w => w.text.trim())
          .map(w => ({ text: w.text, confidence: w.confidence, bbox: w.bbox }));
        if (words.length) lines.push(words);
      }
    }
  }
  return lines;
}

// Keep-only composition: start from a white page and copy only the allowed words.
// Everything else (unknown text, stamps, signatures, logos, barcodes) never reaches the output.
// Zones (ADR-0006): the results table is kept, outside it only date fields.
// style 'boxes' draws a dark box over each run of masked words. The boxes are drawn on the
// new page, not over the original, so nothing of the masked pixels can show at their edges.
// Kept words get a vertical margin of a third of the row's text height, so that descenders
// and accents (g, ę, Ó) are not cut off at the edge of the OCR box.
export function composeKeepOnly(source, lines, makeCanvas, { style = 'boxes', pad = 3 } = {}) {
  const out = makeCanvas(source.width, source.height);
  const ctx = out.getContext('2d');
  ctx.fillStyle = '#ffffff';
  ctx.fillRect(0, 0, out.width, out.height);
  const rows = pageRows(lines);
  const table = findTable(rows);
  const decisions = [];
  const kept = [];
  const boxes = [];
  for (const words of rows) {
    const d = decideLine(words, table);
    const heights = words.map(w => w.bbox.y1 - w.bbox.y0).sort((a, b) => a - b);
    const padY = Math.max(pad, Math.round(heights[heights.length >> 1] / 3));
    let run = null;
    words.forEach((w, i) => {
      decisions.push({ ...w, ...d[i] });
      if (d[i].keep) { kept.push({ ...w.bbox, padY }); run = null; return; }
      const b = w.bbox;
      if (run) { run.x1 = Math.max(run.x1, b.x1); run.y0 = Math.min(run.y0, b.y0); run.y1 = Math.max(run.y1, b.y1); }
      else { run = { ...b }; boxes.push(run); }
    });
  }
  if (style === 'boxes') {
    ctx.fillStyle = '#1f1f1f';
    for (const b of boxes) ctx.fillRect(b.x0 - pad, b.y0 - pad, b.x1 - b.x0 + 2 * pad, b.y1 - b.y0 + 2 * pad);
  }
  for (const { x0, y0, x1, y1, padY } of kept) {
    const x = Math.max(0, x0 - pad), y = Math.max(0, y0 - padY);
    const width = Math.min(source.width - x, x1 - x0 + 2 * pad);
    const height = Math.min(source.height - y, y1 - y0 + 2 * padY);
    ctx.drawImage(source, x, y, width, height, x, y, width, height);
  }
  return { canvas: out, decisions, table };
}

export async function sanitisePage(worker, source, makeCanvas, options = {}) {
  const t0 = performance.now();
  const lines = await ocrLines(worker, source);
  const t1 = performance.now();
  const { canvas, decisions, table } = composeKeepOnly(source, lines, makeCanvas, options);
  const t2 = performance.now();
  const leaks = findLeaks(pageRows(await ocrLines(worker, canvas)), table);
  const t3 = performance.now();
  return {
    canvas,
    decisions,
    table,
    leaks,
    timings: { ocr: t1 - t0, compose: t2 - t1, leakCheck: t3 - t2 },
  };
}
