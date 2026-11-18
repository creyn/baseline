// Masking rules for the browser sanitiser spike. Pure functions, no DOM.
// Zones (docs/adr/0006-zone-based-masking.md):
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
const TABLE_WORDS = ['badanie', 'badania', 'parametr', 'nazwa', 'wynik', 'wyniki', 'wartość', 'jednostka', 'jednostki',
  'jedn', 'j.m', 'norma', 'normy', 'zakres', 'referencyjny', 'referencyjne'];

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
  const w = bare(n);
  if (BIRTH_LABELS.test(w)) return false;
  return DATE_LABELS.includes(w) || DATE_LABEL_STEMS.some(s => w.startsWith(s));
}

// Facts about one OCR line, shared by the table finder and the decisions.
function describeLine(words) {
  const norm = words.map(w => normalise(w.text));
  const kinds = words.map(w => classifyWord(w.text));
  const has = k => kinds.includes(k);
  return {
    norm,
    kinds,
    personal: norm.some(n => PERSONAL_LINE_LABELS.includes(bare(n))),
    tableHeader: norm.filter(n => TABLE_WORDS.includes(bare(n))).length >= 2,
    // A result row: a value with a unit, or a known parameter with a value. No dates, no personal labels.
    resultRow: has('number') && (has('unit') || has('parameter')) && !has('date'),
    methodLine: norm.some(n => METHOD_LABELS.includes(n)) || norm.some(n => ICD_MARKER.test(n)),
    y0: Math.min(...words.map(w => w.bbox?.y0 ?? 0)),
    y1: Math.max(...words.map(w => w.bbox?.y1 ?? 0)),
  };
}

// The results table of a page: { top, bottom } in px, or null.
// Top: the table header, or on a page without one (e.g. a continuation page) the first result row.
// Bottom: the last result row or method line below the top.
export function findTable(lines) {
  const facts = lines.map(describeLine).filter(f => !f.personal).sort((a, b) => a.y0 - b.y0);
  const start = facts.find(f => f.tableHeader) ?? facts.find(f => f.resultRow);
  if (!start) return null;
  const rows = facts.filter(f => f.y0 >= start.y0 && (f.resultRow || f.methodLine));
  if (!rows.length) return null;
  return { top: start.y0, bottom: Math.max(...rows.map(f => f.y1)) };
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
    for (let k = i - 1; k >= 0 && k >= i - 2 && DATE_PREFIX.test(bare(norm[k])); k--) keep.add(k);
    for (let k = i + 1; k < j; k++) keep.add(k);
    for (let k = j; k < norm.length && (kinds[k] === 'date' || kinds[k] === 'time'); k++) keep.add(k);
  });
  return keep;
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
