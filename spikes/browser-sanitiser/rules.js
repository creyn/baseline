// Masking rules for the browser sanitiser spike. Pure functions, no DOM.
// Deny by default: a word stays visible only if a rule below allows it.
// See docs/adr/0003-mask-personal-data-before-ai.md.

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

const HEADER_WORDS = `
wynik wyniki wartość wartości jednostka jednostki jedn j.m. norma normy zakres zakresy referencyjny
referencyjne referencyjna przedział badanie badania parametr parametry nazwa oznaczenie
morfologia rozmaz krwi surowica surowicy osocze osocza materiał metoda hematologia biochemia
immunologia hormony koagulologia analityka ogólna ogólne badanie mocz moczu
data godzina godz data/godz data/godzina pobrania pobranie wykonania wykonano wyniku rejestracji przyjęcia autoryzacji
laboratorium laboratoria diagnostyka alab synevo medicover luxmed enelmed
poniżej powyżej niski wysoki ujemny dodatni nieobecne obecne brak w normie
od do oraz i z w na
`;

const UNITS = `
% g/dl g/l mg/dl mg/l µg/dl ug/dl µg/l ug/l ng/ml ng/dl pg/ml pg mmol/l µmol/l umol/l nmol/l pmol/l
u/l iu/l mu/l miu/l µiu/ml uiu/ml miu/ml iu/ml u/ml mlu/ml fl fL tys/µl tys/ul tys./µl mln/µl mln/ul
10^3/µl 10^6/µl 10^9/l 10^12/l 10³/µl 10⁶/µl g/ml mm/h mm/godz s sek ratio inr ml/min ml/min/1,73m2
ml/min/1.73m2 mg/g /µl /ul /wpw wpw
`;

const FLAGS = ['h', 'l', '↑', '↓', '*', '!', '+', '-', '--', '++', '+++', '(+)', '(-)'];

// Labels that make a whole line personal: the line is masked in full.
const PERSONAL_LINE_LABELS = [
  'pacjent', 'pacjenta', 'imię', 'nazwisko', 'pesel', 'urodzenia', 'adres', 'ulica', 'ul.',
  'telefon', 'tel.', 'tel', 'e-mail', 'email', 'lekarz', 'lekarza', 'zlecający', 'zleceniodawca',
  'npwz', 'pwz', 'podpis', 'pieczątka', 'kod', 'kreskowy', 'nr', 'numer', 'id', 'zlecenie', 'zlecenia',
];

// Labels that allow a date on the same line.
const DATE_LABELS = ['pobrania', 'pobranie', 'wykonania', 'wykonano', 'wyniku', 'przyjęcia', 'rejestracji', 'autoryzacji',
  'wydania', 'wystawienia', 'zatwierdzenia'];

// Labels of a method line, e.g. "Badanie wykonano metodą ... na aparacie Cobas ...".
// The whole line is kept (except denylist hits), because method and analyser names are open-ended.
const METHOD_LABELS = ['metodą', 'metoda', 'metody', 'aparacie', 'aparat', 'aparatem', 'analizatorze', 'analizator', 'analizatora'];

// ICD-9 PL procedure code printed next to a test name, e.g. "TSH (ICD-9: L69)".
const ICD_MARKER = /^icd-?9(-?pl)?:?$/;
const ICD_CODE = /^[a-z]\d{2}[a-z0-9]?$/;

// Laboratory header: lines above the first patient or referrer label, in the top part of the page,
// are kept (lab name, address, logo text), except denylist hits. Stems, matched at word start.
const HEADER_STOP_STEMS = ['pacjen', 'pesel', 'imię', 'imie', 'nazwisk', 'urodz', 'adres', 'lekarz', 'kieruj',
  'zlecaj', 'zleceniodaw', 'kontrahent', 'płatnik', 'platnik'];
const HEADER_MAX_FRACTION = 0.25;

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
const HEADERS = set(HEADER_WORDS);
const UNIT_SET = set(UNITS);
const PARAMS_ASCII = new Set([...PARAMS].map(stripDiacritics));
const HEADERS_ASCII = new Set([...HEADERS].map(stripDiacritics));

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

export function levenshtein(a, b) {
  if (a === b) return 0;
  const m = a.length, n = b.length;
  let prev = Array.from({ length: n + 1 }, (_, j) => j);
  for (let i = 1; i <= m; i++) {
    const cur = [i];
    for (let j = 1; j <= n; j++) {
      cur[j] = Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
    }
    prev = cur;
  }
  return prev[n];
}

// Known identifiers typed by the user: split into tokens, normalised, without diacritics.
export function prepareKnownIdentifiers(text) {
  return text
    .split(/[\n,;]+/)
    .flatMap(entry => [entry, ...entry.split(/\s+/)])
    .map(t => stripDiacritics(normalise(t)).replace(/\s+/g, ''))
    .filter(t => t.length >= 3);
}

function matchesKnown(word, known) {
  const w = stripDiacritics(normalise(word)).replace(/\s+/g, '');
  if (w.length < 3) return false;
  return known.some(k => {
    if (w === k) return true;
    const tolerance = k.length >= 8 ? 2 : k.length >= 4 ? 1 : 0;
    return tolerance > 0 && levenshtein(w, k) <= tolerance;
  });
}

export function classifyWord(text) {
  const n = normalise(text);
  const a = stripDiacritics(n);
  if (!n) return 'empty';
  if (UNIT_SET.has(n) || UNIT_LIKE.test(n)) return 'unit';
  if (FLAGS.includes(n)) return 'flag';
  if (DATE.test(n)) return 'date';
  if (TIME.test(n)) return 'time';
  if (NUMBER.test(n) || RANGE.test(n.replace(/^\(|\)$/g, ''))) return 'number';
  if (PARAMS.has(n) || PARAMS_ASCII.has(a)) return 'parameter';
  if (HEADERS.has(n) || DATE_LABELS.includes(n) || HEADERS_ASCII.has(a)) return 'header';
  return 'unknown';
}

// Bottom edge (px) of the laboratory header, or 0 when there is none.
// lines: [[{ text, bbox }]], pageHeight in px.
export function findHeaderBottom(lines, pageHeight) {
  const sorted = [...lines].sort((a, b) => a[0].bbox.y0 - b[0].bbox.y0);
  for (const words of sorted) {
    const stop = words.some(w => {
      const n = normalise(w.text).replace(/:$/, '');
      return HEADER_STOP_STEMS.some(s => n.startsWith(s));
    });
    if (stop) {
      const y = Math.min(...words.map(w => w.bbox.y0));
      return y <= pageHeight * HEADER_MAX_FRACTION ? y : 0;
    }
  }
  return 0; // no patient label found: no header zone, everything goes through the normal rules
}

const isInHeader = (words, headerBottom) => headerBottom > 0 && words.every(w => w.bbox && w.bbox.y1 <= headerBottom);

// Decides for every word of one OCR line: { keep: boolean, reason: string }.
// words: [{ text, bbox }], known: output of prepareKnownIdentifiers,
// options.headerBottom: from findHeaderBottom.
export function decideLine(words, known = [], { headerBottom = 0 } = {}) {
  const norm = words.map(w => normalise(w.text));
  const inHeader = isInHeader(words, headerBottom);
  const methodLine = norm.some(n => METHOD_LABELS.includes(n));
  const icdAt = norm.findIndex(n => ICD_MARKER.test(n));
  const kinds = words.map(w => classifyWord(w.text));
  const personalLine = norm.some(n => PERSONAL_LINE_LABELS.includes(n) || PERSONAL_LINE_LABELS.includes(n.replace(/:$/, '')));
  const hasAnchor = icdAt >= 0 || kinds.some(k => k === 'parameter' || k === 'unit');
  const hasDateLabel = norm.some(n => DATE_LABELS.includes(n.replace(/:$/, '')));

  return words.map((w, i) => {
    const raw = w.text.replace(/\s+/g, '');
    if (isValidPesel(raw.replace(/\D/g, '')) && raw.replace(/\D/g, '').length === 11) return { keep: false, reason: 'pesel' };
    if (LONG_DIGITS.test(raw)) return { keep: false, reason: 'long-number' };
    if (matchesKnown(w.text, known)) return { keep: false, reason: 'known-identifier' };
    if (inHeader) return { keep: true, reason: 'lab-header' };
    if (personalLine) return { keep: false, reason: 'personal-line' };
    if (methodLine) return { keep: true, reason: 'method' };
    if (icdAt >= 0 && i <= icdAt) return { keep: true, reason: i === icdAt ? 'icd-9' : 'test-name' };
    if (icdAt >= 0 && i === icdAt + 1 && ICD_CODE.test(norm[i])) return { keep: true, reason: 'icd-9' };
    switch (kinds[i]) {
      case 'parameter':
      case 'header':
      case 'unit':
        return { keep: true, reason: kinds[i] };
      case 'flag':
      case 'number':
        return hasAnchor ? { keep: true, reason: kinds[i] } : { keep: false, reason: `${kinds[i]}-without-anchor` };
      case 'date':
      case 'time':
        return hasDateLabel ? { keep: true, reason: kinds[i] } : { keep: false, reason: `${kinds[i]}-without-label` };
      default:
        return { keep: false, reason: 'not-allowlisted' };
    }
  });
}

// Leak check on the OCR of the masked image. Any denylist hit or any
// confidently read word outside the allowlist blocks the document.
export function findLeaks(lines, known = [], { minConfidence = 60, headerBottom = 0 } = {}) {
  const leaks = [];
  for (const words of lines) {
    const decisions = decideLine(words, known, { headerBottom });
    words.forEach((w, i) => {
      const d = decisions[i];
      if (d.keep) return;
      const denylist = ['pesel', 'long-number', 'known-identifier'].includes(d.reason);
      const meaningful = /\p{L}{3,}/u.test(w.text) && (w.confidence ?? 100) >= minConfidence;
      if (denylist || meaningful) leaks.push({ text: w.text, reason: d.reason });
    });
  }
  return leaks;
}
