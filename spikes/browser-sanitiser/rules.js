// Masking rules for the browser sanitiser spike. Pure functions, no DOM.
// Zones (docs/adr/0003-masking-in-the-browser-and-a-second-check.md):
// - the results table is kept, except personal and people lines, PESEL numbers and long numbers;
// - outside the table only labelled date fields are kept (never the date of birth);
// - without a table, only date fields are kept.

const PARAMETER_WORDS = `
hemoglobina hemoglobin hgb hb hematokryt hct erytrocyty erytrocytów rbc leukocyty leukocytów wbc
płytki płytek krwi plt trombocyty mcv mch mchc rdw rdw-cv rdw-sd mpv pdw pct p-lcr
neutrofile neutrocyty limfocyty monocyty eozynofile bazofile granulocyty niedojrzałe ig
neu lym mono eos baso retikulocyty ob odczyn biernackiego
glukoza glukozy hba1c hemoglobina glikowana insulina
cholesterol całkowity hdl ldl nie-hdl triglicerydy trójglicerydy lipidogram
kreatynina egfr mocznik kwas moczowy sód potas chlorki wapń magnez fosfor fosforany żelazo
ferrytyna transferyna tibc uibc wysycenie
alt ast alat aspat ggtp ggt fosfataza alkaliczna alp bilirubina bezpośrednia pośrednia
białko albumina albuminy globuliny amylaza lipaza ldh ck cpk crp hscrp prokalcytonina
tsh ft3 ft4 anty-tpo anty-tg atpo atg tyreoglobulina
witamina vit wit 25-oh 25(oh)d d3 b12 kwas foliowy foliany
psa fpsa testosteron estradiol progesteron prolaktyna lh fsh kortyzol dhea dhea-s shbg
inr pt aptt fibrynogen d-dimer d-dimery czas protrombinowy
mocz ciężar właściwy ph bakterie nabłonki wałeczki kryształy urobilinogen ketony azotyny
leukocyty erytrocyty barwa przejrzystość
`;

const UNITS = `
% g/dl g/l mg/dl mg/l µg/dl ug/dl µg/l ug/l ng/ml ng/dl pg/ml pg mmol/l µmol/l umol/l nmol/l pmol/l
u/l iu/l mu/l miu/l µiu/ml uiu/ml miu/ml iu/ml u/ml mlu/ml fl fL tys/µl tys/ul tys./µl mln/µl mln/ul
10^3/µl 10^6/µl 10^9/l 10^12/l 10³/µl 10⁶/µl g/ml mm/h mm/godz s sek ratio inr ml/min ml/min/1,73m2
ml/min/1.73m2 mg/g /µl /ul /wpw wpw
`;

const FLAGS = ['h', 'l', '↑', '↓', '*', '!', '+', '-', '--', '++', '+++', '(+)', '(-)'];

// Lines naming the patient or people who ordered, performed, validated or signed the result.
// Masked in full even inside the table, except their date fields.
const PERSONAL_LINE_LABELS = [
  'pacjent', 'pacjenta', 'imię', 'nazwisko', 'pesel', 'urodzenia', 'ur', 'adres', 'ulica', 'ul',
  'telefon', 'tel', 'e-mail', 'email', 'lekarz', 'lekarza', 'zlecający', 'zleceniodawca', 'kierujący',
  'npwz', 'pwz', 'podpis', 'pieczątka', 'kod', 'kreskowy', 'nr', 'numer', 'id',
  'mgr', 'dr', 'lek', 'prof', 'diagnosta', 'diagnostka', 'technik', 'analityk',
  'wykonał', 'wykonała', 'autoryzował', 'autoryzowała', 'zatwierdził', 'zatwierdziła',
  'walidował', 'walidowała', 'zwalidował', 'zwalidowała', 'sprawdził', 'sprawdziła',
];

// Date field labels, matched as word stems so abbreviations work: "Data rej.:", "Data pob.:".
const DATE_LABELS = ['wyniku', 'zlecenia'];
const DATE_LABEL_STEMS = ['rej', 'pob', 'przyj', 'wyk', 'wyd', 'aut', 'zatw', 'wyst'];
const BIRTH_LABELS = /^(ur|urodz|urodzenia|urodzony|urodzona)$/;
const DATE_PREFIX = /^(data|godz|godzina|data\/godz|data\/godzina|i)$/;
const DATE_FILLERS = ['prób', 'próbki', 'próbek', 'materiału', 'pdf/wydruku', 'wydruku', 'pdf', 'godz', 'godzina', ''];

// Words of a results table header, e.g. "Badanie Wynik Jedn. Zakres referencyjny".
const TABLE_WORDS = ['badanie', 'badania', 'parametr', 'nazwa', 'wynik', 'wyniki', 'wartość', 'wartości', 'jednostka', 'jednostki',
  'jedn', 'j.m', 'norma', 'normy', 'zakres', 'zakresy', 'referencyjny', 'referencyjne', 'referencyjna', 'oznaczenie', 'materiał',
  'min', 'max', 'flaga', 'icd9', 'icd-9', 'procedura', 'badawcza', 'metoda'];

// Results given as words instead of numbers, e.g. "HBs ujemny".
const QUALITATIVE = new Set(['ujemny', 'ujemna', 'ujemne', 'dodatni', 'dodatnia', 'dodatnie', 'nieobecny', 'nieobecna',
  'nieobecne', 'obecny', 'obecna', 'obecne', 'niereaktywny', 'reaktywny', 'wykryto', 'niewykrywalny', 'niewykrywalne']);

// A method line under a result, e.g. "Badanie wykonano metodą ... na aparacie Cobas ...".
const METHOD_LABELS = ['metodą', 'metoda', 'metody', 'aparacie', 'aparat', 'aparatem', 'analizatorze', 'analizator', 'analizatora'];
const ICD_MARKER = /^icd-?9(-?pl)?:?$/;

const set = s => new Set(s.split(/\s+/).filter(Boolean).map(normalise));

export function stripDiacritics(s) {
  return s.normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/ł/g, 'l').replace(/Ł/g, 'L');
}

// Lower case, without surrounding punctuation that OCR often attaches.
export function normalise(word) {
  return word
    .toLowerCase()
    .replace(/^[\s"'„”“,;:()[\]{}]+/, '')
    .replace(/[\s"'„”“,;:()[\]{}]+$/, '')
    .replace(/\.$/, '')
    .replace(/(?<=[^*])[*†]+$/, ''); // footnote markers such as pg/ml*; a lone * stays a flag
}

const PARAMS = set(PARAMETER_WORDS);
const UNIT_SET = set(UNITS);
const PARAMS_ASCII = new Set([...PARAMS].map(stripDiacritics));

const NUMBER = /^[<>≤≥]?[-+]?\d{1,6}([.,]\d{1,4})?$/;
const RANGE = /^[<>≤≥]?\d{1,6}([.,]\d{1,4})?\s*[-–—]\s*\d{1,6}([.,]\d{1,4})?$/;
const DATE = /^(\d{1,2}[.\-/]\d{1,2}[.\-/]\d{2,4}|\d{4}-\d{2}-\d{2})(r\.?)?$/;
const TIME = /^\d{1,2}:\d{2}(:\d{2})?$/;
const LONG_DIGITS = /\d{7,}/;
// Unit-like tokens such as tys/µl or µIU/ml. OCR often reads µ as u, l or ul, so the
// pattern is used instead of an exact list: letters on both sides of one slash, short, no long digits.
const UNIT_LIKE = /^(\d{1,2}\^?\d{0,2})?[\p{L}µ%.]{1,6}\/[\p{L}µ0-9.,]{1,8}$/u;

export function isValidPesel(s) {
  if (!/^\d{11}$/.test(s)) return false;
  const w = [1, 3, 7, 9, 1, 3, 7, 9, 1, 3];
  const sum = w.reduce((acc, wi, i) => acc + wi * Number(s[i]), 0);
  return (10 - (sum % 10)) % 10 === Number(s[10]);
}

export function classifyWord(text) {
  const n = normalise(text);
  if (!n) return 'empty';
  if (UNIT_SET.has(n) || UNIT_LIKE.test(n)) return 'unit';
  if (FLAGS.includes(n)) return 'flag';
  if (DATE.test(n)) return 'date';
  if (TIME.test(n)) return 'time';
  if (NUMBER.test(n) || RANGE.test(n.replace(/^\(|\)$/g, ''))) return 'number';
  if (PARAMS.has(n) || PARAMS_ASCII.has(stripDiacritics(n))) return 'parameter';
  return 'unknown';
}

const bare = n => n.replace(/[.:]+$/, '');

function isDateLabel(n) {
  // OCR sometimes glues the label to "Data": "Datarej:", "Dataur:"
  const w = bare(n).replace(/^data(?=\p{L})/u, '');
  if (BIRTH_LABELS.test(w)) return false;
  return DATE_LABELS.includes(w) || DATE_LABEL_STEMS.some(s => w.startsWith(s));
}

// Facts about one OCR line, shared by the table finder and the decisions.
function describeLine(words) {
  const norm = words.map(w => normalise(w.text));
  const kinds = words.map(w => classifyWord(w.text));
  const has = k => kinds.includes(k);
  // A header has at least two header words, they make up a good part of the line, and it holds no values.
  // "Wartość referencyjna: 2.0 - 7.0" under a result is not a header.
  const headerWords = norm.filter(n => TABLE_WORDS.includes(bare(n))).length;
  const tableHeader = headerWords >= 2 && headerWords >= 0.4 * norm.length && !kinds.some(k => ['number', 'date', 'time'].includes(k));
  return {
    norm,
    kinds,
    // "Procedura badawcza nr" in a header is not a people line
    personal: !tableHeader && norm.some(n => PERSONAL_LINE_LABELS.includes(bare(n))),
    tableHeader,
    // A result row: a value with a unit, a known parameter with a value, or a word result such as "ujemny".
    resultRow: ((has('number') && (has('unit') || has('parameter'))) || norm.some(n => QUALITATIVE.has(bare(n)))) && !has('date'),
    methodLine: norm.some(n => METHOD_LABELS.includes(n)) || norm.some(n => ICD_MARKER.test(n)),
    y0: Math.min(...words.map(w => w.bbox?.y0 ?? 0)),
    y1: Math.max(...words.map(w => w.bbox?.y1 ?? 0)),
  };
}

const median = xs => { const s = [...xs].sort((a, b) => a - b); return s.length ? s[s.length >> 1] : 0; };

// Tesseract splits a page into blocks, so one printed row (a table header with separate columns,
// a label and its value) may come back as several lines. Rows are rebuilt from geometry instead:
// a word joins a row when its vertical centre is within 0.4 of the smaller text height from the centre
// of the row's first word. A tall box (e.g. OCR noise on a masked run) does not swallow the small text
// next to it. Words are sorted left to right.
export function groupRows(lines) {
  const centre = b => (b.y0 + b.y1) / 2;
  const height = b => b.y1 - b.y0;
  const words = lines.flat().filter(w => w.bbox).sort((a, b) => centre(a.bbox) - centre(b.bbox));
  const rows = [];
  for (const w of words) {
    const row = rows.find(r => Math.abs(centre(w.bbox) - centre(r.first)) <= 0.4 * Math.min(height(w.bbox), height(r.first)));
    if (row) row.words.push(w);
    else rows.push({ first: w.bbox, words: [w] });
  }
  return rows.map(r => r.words.sort((a, b) => a.bbox.x0 - b.bbox.x0)).sort((a, b) => a[0].bbox.y0 - b[0].bbox.y0);
}

// The results table of a page: { top, bottom } in px, or null.
// Top: the table header, or on a page without one (e.g. a continuation page) the first result row.
// Bottom: the last result row or method line below the top, extended over the lines right below it
// (descriptions, word results) while they keep the table's line spacing and are neither personal nor date lines.
export function findTable(lines) {
  const all = lines.map(describeLine).sort((a, b) => a.y0 - b.y0);
  const facts = all.filter(f => !f.personal);
  // the header right above the first result row, or the first result row itself
  const first = facts.find(f => f.resultRow);
  if (!first) return null;
  const start = facts.filter(f => f.tableHeader && f.y0 < first.y0).pop() ?? first;
  if (!start) return null;
  const rows = facts.filter(f => f.y0 >= start.y0 && (f.resultRow || f.methodLine));
  if (!rows.length) return null;
  let bottom = Math.max(...rows.map(f => f.y1));
  const inside = all.filter(f => f.y0 >= start.y0 && f.y1 <= bottom);
  const gaps = inside.slice(1).map((f, i) => f.y0 - inside[i].y1).filter(g => g > 0);
  const lineHeight = median(inside.map(f => f.y1 - f.y0));
  const maxGap = Math.max(median(gaps) * 2, lineHeight);
  for (const f of all.filter(f => f.y0 > bottom)) {
    if (f.personal || dateFieldWords(f.norm, f.kinds).size || f.y0 - bottom > maxGap) break;
    bottom = f.y1;
  }
  return { top: start.y0, bottom };
}

const inTable = (f, table) => !!table && (f.y0 + f.y1) / 2 >= table.top && (f.y0 + f.y1) / 2 <= table.bottom;

// Indexes of the words of date fields: [Data[/godz.]] label [fillers] date [time].
function dateFieldWords(norm, kinds) {
  const keep = new Set();
  norm.forEach((n, i) => {
    if (!isDateLabel(n)) return;
    let j = i + 1;
    while (j < norm.length && DATE_FILLERS.includes(bare(norm[j]))) j++;
    if (j >= norm.length || kinds[j] !== 'date') return; // a label without a date: nothing to keep
    keep.add(i);
    // "Data i godz. pobrania": up to three prefix words
    for (let k = i - 1; k >= 0 && k >= i - 3 && DATE_PREFIX.test(bare(norm[k])); k--) keep.add(k);
    for (let k = i + 1; k < j; k++) keep.add(k);
    for (let k = j; k < norm.length && (kinds[k] === 'date' || kinds[k] === 'time'); k++) keep.add(k);
  });
  return keep;
}

// A date label whose date is printed a little higher or lower than the label, so the two end up
// in neighbouring rows: the nearest date to the right of the label, within 1.5 line heights up or down,
// is moved (with the time after it) into the label's row, right after the label.
export function attachOffsetDates(rows) {
  const out = rows.map(r => [...r]);
  out.forEach((row, ri) => {
    const norm = row.map(w => normalise(w.text));
    const kinds = row.map(w => classifyWord(w.text));
    // right to left, so that moving words in does not shift the labels still to be checked
    norm.map((n, i) => i).reverse().forEach(i => {
      if (!isDateLabel(norm[i])) return;
      let j = i + 1;
      while (j < norm.length && DATE_FILLERS.includes(bare(norm[j]))) j++;
      if (j < norm.length && kinds[j] === 'date') return; // the date is already in this row
      const label = row[j - 1].bbox;
      const h = label.y1 - label.y0;
      const next = row[j]?.bbox.x0 ?? Infinity;
      const centre = b => (b.y0 + b.y1) / 2;
      let best = null;
      out.forEach((other, oi) => {
        if (oi === ri) return;
        other.forEach((w, wi) => {
          const dy = Math.abs(centre(w.bbox) - centre(label));
          const dx = w.bbox.x0 - label.x1;
          if (classifyWord(w.text) !== 'date' || dy > 1.5 * h || dx <= 0 || dx > 15 * h || w.bbox.x0 >= next) return;
          if (!best || dx + dy < best.d) best = { other, wi, d: dx + dy };
        });
      });
      if (!best) return;
      let end = best.wi + 1;
      while (end < best.other.length && classifyWord(best.other[end].text) === 'time') end++;
      row.splice(j, 0, ...best.other.splice(best.wi, end - best.wi));
    });
  });
  return out.filter(r => r.length);
}

// OCR lines → printed rows, with offset dates attached to their labels. Use before findTable and decideLine.
export function pageRows(lines) {
  return attachOffsetDates(groupRows(lines));
}

function isDenylisted(text) {
  const raw = text.replace(/\s+/g, '');
  const digits = raw.replace(/\D/g, '');
  if (digits.length === 11 && isValidPesel(digits)) return 'pesel';
  if (LONG_DIGITS.test(raw)) return 'long-number';
  return null;
}

// Decides for every word of one OCR line: { keep, reason }.
// words: [{ text, bbox }], table: from findTable (null when there is none).
export function decideLine(words, table = null) {
  const f = describeLine(words);
  const dates = dateFieldWords(f.norm, f.kinds);
  const zone = inTable(f, table) ? 'table' : 'outside';
  return words.map((w, i) => {
    const deny = isDenylisted(w.text);
    if (deny) return { keep: false, reason: deny };
    if (dates.has(i)) return { keep: true, reason: 'date-field' };
    if (zone === 'outside') return { keep: false, reason: 'outside-table' };
    if (f.personal) return { keep: false, reason: 'personal-line' };
    return { keep: true, reason: 'table' };
  });
}

// Leak check on the OCR of the masked image, with the table found on the original.
// Outside the table any confidently read word that is not a date field is a leak.
// In the table only PESEL numbers, long numbers and personal or people lines are leaks.
export function findLeaks(lines, table = null, { minConfidence = 60 } = {}) {
  const leaks = [];
  for (const words of lines) {
    const decisions = decideLine(words, table);
    words.forEach((w, i) => {
      const d = decisions[i];
      if (d.keep) return;
      const denylist = ['pesel', 'long-number', 'personal-line'].includes(d.reason);
      const meaningful = /\p{L}{3,}/u.test(w.text) && (w.confidence ?? 100) >= minConfidence;
      if (denylist ? d.reason !== 'personal-line' || meaningful : meaningful) leaks.push({ text: w.text, reason: d.reason });
    });
  }
  return leaks;
}
