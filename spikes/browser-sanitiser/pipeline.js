// OCR → decisions → keep-only image → leak check. Works in the browser and in Node:
// the caller passes a Tesseract worker and a canvas factory.
import { decideLine, findLeaks } from './rules.js';

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
export function composeKeepOnly(source, lines, known, makeCanvas, pad = 3) {
  const out = makeCanvas(source.width, source.height);
  const ctx = out.getContext('2d');
  ctx.fillStyle = '#ffffff';
  ctx.fillRect(0, 0, out.width, out.height);
  const decisions = [];
  for (const words of lines) {
    const d = decideLine(words, known);
    words.forEach((w, i) => {
      decisions.push({ ...w, ...d[i] });
      if (!d[i].keep) return;
      const { x0, y0, x1, y1 } = w.bbox;
      const x = Math.max(0, x0 - pad), y = Math.max(0, y0 - pad);
      const width = Math.min(source.width - x, x1 - x0 + 2 * pad);
      const height = Math.min(source.height - y, y1 - y0 + 2 * pad);
      ctx.drawImage(source, x, y, width, height, x, y, width, height);
    });
  }
  return { canvas: out, decisions };
}

export async function sanitisePage(worker, source, known, makeCanvas) {
  const t0 = performance.now();
  const lines = await ocrLines(worker, source);
  const t1 = performance.now();
  const { canvas, decisions } = composeKeepOnly(source, lines, known, makeCanvas);
  const t2 = performance.now();
  const leaks = findLeaks(await ocrLines(worker, canvas), known);
  const t3 = performance.now();
  return {
    canvas,
    decisions,
    leaks,
    timings: { ocr: t1 - t0, compose: t2 - t1, leakCheck: t3 - t2 },
  };
}
