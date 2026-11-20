// Run with: node --test 'spikes/**/*.test.mjs'
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { isValidPesel, classifyWord, decideLine, findTable, findLeaks, pageRows } from './rules.js';

// One OCR line at height y: words 100 px apart, 40 px high.
const at = (s, y) => s.split(' ').map((text, i) => ({ text, confidence: 95, bbox: { x0: i * 100, y0: y, x1: i * 100 + 90, y1: y + 40 } }));
const keptIn = (line, table) => line.filter((_, i) => decideLine(line, table)[i].keep).map(w => w.text);

// A page shaped like a real result: header, patient block, table, date table, footer.
const page = [
  at('LABORATORIUM PRZYKŁADOWE', 100),
  at('ul. Testowa 12/3, 00-950 Warszawa tel. 500 600 700', 150),
  at('Wynik zatwierdził: Anna Walidująca', 300),
  at('Lekarz kierujący: - Data rej.: 2026-05-28', 400),
  at('Odbiór wyniku: Osobiście Data/godz. pobrania: 2026-05-28 09:36', 450),
  at('Jan Testowy Data ur.: 1980-01-01', 500),
  at('Badanie Wynik Jedn. Zakres referencyjny', 1000),
  at('TSH (ICD-9: L69) 7,640 ulU/ml* 0,270 - 4,200 H', 1100),
  at('Badanie wykonano metodą elektrochemiluminescencji na aparacie Cobas 8000.', 1160),
  at('Tyreotropina 2,15 0,27-4,20', 1250),
  at('Autoryzował: mgr Anna Walidująca', 1300),
  at('FT4 1,42 ng/dl* 0,92 - 1,68', 1400),
  at('Data/godz. przyjęcia prób.: 2026-05-28 09:36 SUROWICA DIAGNOSTYKA Jan', 1700),
  at('Data/godz wykonania: 2026-05-28 11:38:53 LABORATORIUM DIAGNOSTYKA, Prosta 100, 02-231', 1740),
  at('Data wystawienia pdf/wydruku: 2026-05-28 12:00:01', 3200),
  at('mgr Piotr Diagnosta', 3250),
];
const table = findTable(page);

test('PESEL checksum', () => {
  assert.equal(isValidPesel('44051401359'), true); // public example number
  assert.equal(isValidPesel('44051401358'), false);
  assert.equal(isValidPesel('4405140135'), false);
});

test('word classes', () => {
  assert.equal(classifyWord('Hemoglobina'), 'parameter');
  assert.equal(classifyWord('g/dl'), 'unit');
  assert.equal(classifyWord('13,5'), 'number');
  assert.equal(classifyWord('12.0-16.0'), 'number');
  assert.equal(classifyWord('17.11.2026'), 'date');
  assert.equal(classifyWord('Kowalski'), 'unknown');
  assert.equal(classifyWord('tys/l'), 'unit'); // tys/µl as read by OCR
  assert.equal(classifyWord('ulU/ml'), 'unit'); // µIU/ml as read by OCR
  assert.equal(classifyWord('pg/ml*'), 'unit'); // footnote marker after a unit
  assert.equal(classifyWord('*'), 'flag');
  assert.notEqual(classifyWord('12/3'), 'unit'); // an address number is not a unit
});

test('the table spans from its header to the last result or method line', () => {
  assert.deepEqual(table, { top: 1000, bottom: 1440 });
});

test('everything in the table is kept, including tests missing from the dictionary', () => {
  for (const i of [6, 7, 8, 9, 11]) assert.deepEqual(keptIn(page[i], table), page[i].map(w => w.text), page[i].map(w => w.text).join(' '));
});

test('people lines and PESEL numbers are masked inside the table', () => {
  assert.deepEqual(keptIn(page[10], table), []);
  assert.deepEqual(keptIn(at('Glukoza 44051401359 95 mg/dl', 1200), table), ['Glukoza', '95', 'mg/dl']);
});

test('outside the table only date fields are kept', () => {
  assert.deepEqual(keptIn(page[0], table), []);
  assert.deepEqual(keptIn(page[1], table), []);
  assert.deepEqual(keptIn(page[2], table), []);
  assert.deepEqual(keptIn(page[3], table), ['Data', 'rej.:', '2026-05-28']);
  assert.deepEqual(keptIn(page[4], table), ['Data/godz.', 'pobrania:', '2026-05-28', '09:36']);
  assert.deepEqual(keptIn(page[5], table), []); // date of birth
  assert.deepEqual(keptIn(page[12], table), ['Data/godz.', 'przyjęcia', 'prób.:', '2026-05-28', '09:36']);
  assert.deepEqual(keptIn(page[13], table), ['Data/godz', 'wykonania:', '2026-05-28', '11:38:53']);
  assert.deepEqual(keptIn(page[14], table), ['Data', 'wystawienia', 'pdf/wydruku:', '2026-05-28', '12:00:01']);
  assert.deepEqual(keptIn(page[15], table), []);
});

test('a page without a table keeps only date fields', () => {
  const noTable = [at('Pacjent: Jan Testowy', 300), at('Data pobrania: 2026-05-28', 400), at('Uwagi: brak', 600)];
  assert.equal(findTable(noTable), null);
  assert.deepEqual(keptIn(noTable[1], null), ['Data', 'pobrania:', '2026-05-28']);
  assert.deepEqual(keptIn(noTable[2], null), []);
});

test('a continuation page without a header starts at the first result row', () => {
  const page2 = [at('Jan Testowy strona 2', 100), at('Glukoza 95 mg/dl 70-99', 300), at('Kreatynina 0,9 mg/dl 0,7-1,2', 360)];
  assert.deepEqual(findTable(page2), { top: 300, bottom: 400 });
});

test('an address with a postcode does not start a table', () => {
  assert.equal(findTable([at('ul. Prosta 100, 02-231 Warszawa', 200), at('Uwagi: brak', 400)]), null);
});

test('leak check', () => {
  assert.equal(findLeaks([page[7]], table).length, 0); // table content is trusted
  assert.equal(findLeaks([page[2]], table).length, 4); // words outside the table
  assert.equal(findLeaks([at('Glukoza 44051401359 95 mg/dl', 1200)], table).length, 1); // PESEL in the table
  assert.equal(findLeaks([page[10]], table).length, 4); // a people line in the table
  assert.equal(findLeaks([[{ text: 'xq', confidence: 20, bbox: { x0: 0, y0: 10, x1: 9, y1: 20 } }]], table).length, 0); // noise
});

// Words placed by hand: [text, x, y], 40 px high, 90 px wide.
const placed = (...ws) => ws.map(([text, x, y]) => ({ text, confidence: 95, bbox: { x0: x, y0: y, x1: x + 90, y1: y + 40 } }));
const keptOnPage = lines => {
  const rows = pageRows(lines);
  const t = findTable(rows);
  return rows.map(r => r.filter((_, i) => decideLine(r, t)[i].keep).map(w => w.text));
};

test('three prefix words before a date label are kept: "Data i godz. pobrania"', () => {
  assert.deepEqual(keptIn(at('Data i godz. pobrania: 2026-05-28 09:36', 400), null), ['Data', 'i', 'godz.', 'pobrania:', '2026-05-28', '09:36']);
});

test('a date printed a little higher than its label is attached to it', () => {
  // OCR returns the label and the date as separate lines; the label sits 24 px (about 2 mm at 300 DPI) lower.
  const lines = [placed(['Pacjent:', 0, 300], ['Jan', 100, 300]), placed(['Data', 0, 424], ['rej.:', 100, 424]), placed(['2026-05-28', 400, 400], ['09:36', 500, 400])];
  assert.deepEqual(keptOnPage(lines).flat(), ['Data', 'rej.:', '2026-05-28', '09:36']);
});

test('a table header split by OCR into separate columns is still found', () => {
  const lines = [placed(['Pacjent:', 0, 100], ['Jan', 100, 100]), placed(['Badanie', 0, 300]), placed(['Wynik', 400, 302]), placed(['Jednostka', 600, 299]),
    placed(['Glukoza', 0, 360], ['95', 400, 360], ['mg/dl', 600, 360])];
  assert.deepEqual(findTable(pageRows(lines)), { top: 299, bottom: 400 });
});

test('word results start and extend the table; description lines right below it stay inside', () => {
  const lines = [at('Antygen HBs ujemny', 300), at('Glukoza 95 mg/dl 70-99', 360), at('Przeciwciała anty-HCV ujemny', 420),
    at('Uwaga: oznaczenie wykonano z powtórzeniem', 480), at('Data wydania: 2026-05-28', 700), at('mgr Anna Walidująca', 760)];
  const t = findTable(lines);
  assert.deepEqual(t, { top: 300, bottom: 520 });
  assert.deepEqual(keptIn(lines[3], t), lines[3].map(w => w.text));
  assert.deepEqual(keptIn(lines[5], t), []);
});

test('the table does not extend over a personal line or past a large gap', () => {
  const lines = [at('Glukoza 95 mg/dl 70-99', 300), at('Kreatynina 0,9 mg/dl 0,7-1,2', 360), at('Autoryzował: Jan Testowy', 420), at('Uwagi końcowe', 480)];
  assert.equal(findTable(lines).bottom, 400);
  const far = [at('Glukoza 95 mg/dl 70-99', 300), at('Kreatynina 0,9 mg/dl 0,7-1,2', 360), at('Stopka laboratorium Prosta 1', 900)];
  assert.equal(findTable(far).bottom, 400);
});

test('a header with "nr" is a header, and "Wartość referencyjna: 2.0 - 7.0" under a result is not', () => {
  const lines = [at('Pacjent: Jan Testowy', 100), at('ICD9 Nazwa Wynik j.m. Wartość referencyjna Procedura badawcza nr', 300),
    at('Profil: Hormony - krew', 340), at('O55 Trójjodotyronina wolna (FT3) 5.20 pmol/l', 400), at('Wartość referencyjna: 2.0 - 7.0', 440)];
  const t = findTable(lines);
  assert.equal(t.top, 300);
  assert.deepEqual(keptIn(lines[1], t), lines[1].map(w => w.text));
  assert.deepEqual(keptIn(lines[2], t), lines[2].map(w => w.text));
});

test('a tall box next to a small date field does not split the field', () => {
  const box = { text: 'RER', confidence: 30, bbox: { x0: 0, y0: 3227, x1: 900, y1: 3268 } };
  const small = (text, x) => ({ text, confidence: 95, bbox: { x0: x, y0: 3259, x1: x + 90, y1: 3274 } });
  const rows = pageRows([[box, small('Data', 1000)], [small('wydruku:', 1100), small('15-03-2026', 1200), small('08:15', 1300)]]);
  assert.deepEqual(keptOnPage([[box, small('Data', 1000)], [small('wydruku:', 1100), small('15-03-2026', 1200), small('08:15', 1300)]]).flat(), ['Data', 'wydruku:', '15-03-2026', '08:15']);
  assert.equal(rows.length, 2);
});
