import * as pdfjs from './vendor/pdfjs/pdf.min.mjs';
import { sanitisePage } from './pipeline.js';
import { prepareKnownIdentifiers } from './rules.js';

const MAX_PAGES = 5;
const url = p => new URL(p, location.href).href;
const $ = id => document.getElementById(id);
const makeCanvas = (w, h) => Object.assign(document.createElement('canvas'), { width: w, height: h });
const ms = t => `${(t / 1000).toFixed(1)} s`;

pdfjs.GlobalWorkerOptions.workerSrc = url('vendor/pdfjs/pdf.worker.min.mjs');

let worker;
let objectUrls = [];

$('env').textContent =
  `CPU threads: ${navigator.hardwareConcurrency ?? '?'} · memory: ${navigator.deviceMemory ?? '?'} GB · ${navigator.userAgent}`;

async function init() {
  const t0 = performance.now();
  worker = await Tesseract.createWorker('pol', 1, {
    workerPath: url('vendor/tesseract/worker.min.js'),
    corePath: url('vendor/tesseract-core'),
    langPath: url('vendor/lang'),
    workerBlobURL: false,
  });
  setStatus(`OCR engine ready in ${ms(performance.now() - t0)}. Choose a file.`);
  $('run').disabled = !$('file').files.length;
}

function setStatus(text) {
  $('status').textContent = text;
}

async function loadPages(file, dpi) {
  if (file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf')) {
    const task = pdfjs.getDocument({
      data: new Uint8Array(await file.arrayBuffer()),
      standardFontDataUrl: url('vendor/pdfjs/standard_fonts/'),
      wasmUrl: url('vendor/pdfjs/wasm/'),
      enableXfa: false,
    });
    const pdf = await task.promise;
    const pages = [];
    for (let n = 1; n <= Math.min(pdf.numPages, MAX_PAGES); n++) {
      const page = await pdf.getPage(n);
      const viewport = page.getViewport({ scale: dpi / 72 });
      const canvas = makeCanvas(Math.floor(viewport.width), Math.floor(viewport.height));
      await page.render({ canvas, viewport }).promise;
      pages.push(canvas);
    }
    const skipped = pdf.numPages - pages.length;
    await task.destroy();
    return { pages, skipped };
  }
  const bitmap = await createImageBitmap(file, { imageOrientation: 'from-image' });
  const canvas = makeCanvas(bitmap.width, bitmap.height);
  canvas.getContext('2d').drawImage(bitmap, 0, 0);
  bitmap.close();
  return { pages: [canvas], skipped: 0 };
}

function toImage(canvas, alt) {
  return new Promise(resolve =>
    canvas.toBlob(blob => {
      const u = URL.createObjectURL(blob);
      objectUrls.push(u);
      const img = Object.assign(document.createElement('img'), { src: u, alt });
      resolve({ img, href: u });
    }, 'image/png'));
}

function drawDecisions(source, decisions) {
  const c = makeCanvas(source.width, source.height);
  const ctx = c.getContext('2d');
  ctx.drawImage(source, 0, 0);
  ctx.lineWidth = Math.max(2, source.width / 800);
  for (const d of decisions) {
    const { x0, y0, x1, y1 } = d.bbox;
    ctx.strokeStyle = d.keep ? '#2e7d32' : '#c62828';
    ctx.strokeRect(x0, y0, x1 - x0, y1 - y0);
  }
  return c;
}

async function run() {
  const file = $('file').files[0];
  if (!file || !worker) return;
  objectUrls.forEach(URL.revokeObjectURL);
  objectUrls = [];
  $('pages').replaceChildren();
  $('summary').hidden = true;
  $('run').disabled = true;

  const dpi = Number($('dpi').value);
  const known = prepareKnownIdentifiers($('known').value);
  const totals = { render: 0, ocr: 0, compose: 0, leakCheck: 0 };
  let leakCount = 0;

  try {
    setStatus('Rendering…');
    const tr = performance.now();
    const { pages, skipped } = await loadPages(file, dpi);
    totals.render = performance.now() - tr;

    for (const [i, source] of pages.entries()) {
      setStatus(`Page ${i + 1} of ${pages.length}: OCR, masking, leak check…`);
      const r = await sanitisePage(worker, source, known, makeCanvas);
      for (const k of ['ocr', 'compose', 'leakCheck']) totals[k] += r.timings[k];
      leakCount += r.leaks.length;

      const kept = r.decisions.filter(d => d.keep).length;
      const section = document.createElement('section');
      section.className = 'card page';
      const { img, href } = await toImage(r.canvas, `Masked page ${i + 1}`);
      const verdict = r.leaks.length ? `BLOCKED: ${r.leaks.length} suspicious word(s)` : 'Clean';
      section.innerHTML = `
        <h2>Page ${i + 1} <span class="badge ${r.leaks.length ? 'bad' : 'good'}">${verdict}</span></h2>
        <p class="meta">${source.width}×${source.height} px · words kept ${kept} of ${r.decisions.length} ·
          OCR ${ms(r.timings.ocr)} · compose ${ms(r.timings.compose)} · leak check ${ms(r.timings.leakCheck)}</p>`;
      if (r.leaks.length) {
        const ul = document.createElement('ul');
        ul.className = 'leaks';
        r.leaks.forEach(l => ul.appendChild(Object.assign(document.createElement('li'), { textContent: `${l.reason}: ${l.text}` })));
        section.appendChild(ul);
      }
      section.appendChild(img);
      section.appendChild(Object.assign(document.createElement('a'), {
        href, download: `page-${i + 1}-masked.png`, textContent: 'Download masked PNG', className: 'button',
      }));
      if ($('debug').checked) {
        const dbg = await toImage(drawDecisions(source, r.decisions), `Decisions on page ${i + 1}`);
        const details = document.createElement('details');
        details.innerHTML = '<summary>Decisions on the original: green kept, red masked</summary>';
        details.appendChild(dbg.img);
        section.appendChild(details);
      }
      $('pages').appendChild(section);
      source.width = source.height = 0; // release the original pixels
    }

    const total = Object.values(totals).reduce((a, b) => a + b, 0);
    $('summary').innerHTML = `
      <h2>${leakCount ? 'Blocked' : 'Clean'} · ${pages.length} page(s) · ${ms(total)}</h2>
      <p class="meta">render ${ms(totals.render)} · OCR ${ms(totals.ocr)} · compose ${ms(totals.compose)} ·
        leak check ${ms(totals.leakCheck)} · per page ${ms(total / pages.length)} at ${dpi} DPI
        ${skipped ? ` · ${skipped} page(s) skipped (limit ${MAX_PAGES})` : ''}</p>`;
    $('summary').hidden = false;
    setStatus('Done. Nothing was sent anywhere.');
  } catch (e) {
    console.error(e);
    setStatus(`Error: ${e.message}`);
  } finally {
    $('run').disabled = false;
  }
}

$('file').addEventListener('change', () => { $('run').disabled = !worker || !$('file').files.length; });
$('run').addEventListener('click', run);
init().catch(e => setStatus(`Could not start the OCR engine: ${e.message}`));
