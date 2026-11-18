// Run with: node --test 'spikes/**/*.test.mjs'
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { isValidPesel, classifyWord, decideLine, findLeaks, findHeaderBottom, prepareKnownIdentifiers } from './rules.js';

const line = s => s.split(' ').map(text => ({ text, confidence: 95 }));
const kept = (s, known = []) => decideLine(line(s), known).filter(d => d.keep).length;
const keptWords = (s, known = []) => line(s).filter((_, i) => decideLine(line(s), known)[i].keep).map(w => w.text);

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
  assert.equal(classifyWord('(30-100)'), 'number');
  assert.equal(classifyWord('17.11.2026'), 'date');
  assert.equal(classifyWord('Kowalski'), 'unknown');
  assert.equal(classifyWord('tys/l'), 'unit'); // tys/µl as read by OCR
  assert.equal(classifyWord('ulU/ml'), 'unit'); // µIU/ml as read by OCR
  assert.equal(classifyWord('pg/ml*'), 'unit'); // footnote marker after a unit
  assert.equal(classifyWord('*'), 'flag');
  assert.notEqual(classifyWord('12/3'), 'unit'); // an address number is not a unit
});

test('a result row stays visible', () => {
  assert.deepEqual(keptWords('Hemoglobina 13,5 g/dl 12,0-16,0'), ['Hemoglobina', '13,5', 'g/dl', '12,0-16,0']);
  assert.deepEqual(keptWords('Witamina D3 25-OH 32,1 ng/ml 30-100'), ['Witamina', 'D3', '25-OH', '32,1', 'ng/ml', '30-100']);
});

test('numbers without a parameter or unit on the line are masked', () => {
  assert.equal(kept('500 600 700'), 0); // e.g. a phone number split by spaces
  assert.equal(kept('Warszawa 00-950 12/3'), 0);
});

test('lines with personal labels are masked in full', () => {
  assert.equal(kept('Pacjent: Jan Testowy'), 0);
  assert.equal(kept('Data urodzenia: 14.05.1944'), 0);
  assert.equal(kept('Lekarz zlecający: dr Anna Przykładowa NPWZ 1234567'), 0);
});

test('dates only next to a date label', () => {
  assert.deepEqual(keptWords('Data pobrania: 17.11.2026 08:15'), ['Data', 'pobrania:', '17.11.2026', '08:15']);
  assert.equal(keptWords('17.11.2026').length, 0);
});

test('denylist wins over the allowlist', () => {
  assert.equal(kept('Glukoza 44051401359 mg/dl'), 2); // PESEL in a result row is masked
  const known = prepareKnownIdentifiers('Jan Testowy');
  assert.equal(kept('Glukoza Testowy 95 mg/dl', known), 3);
  assert.equal(kept('Glukoza Testowv 95 mg/dl', known), 3); // OCR error, still matched
});

test('leak check', () => {
  const known = prepareKnownIdentifiers('Jan Testowy');
  assert.equal(findLeaks([line('Hemoglobina 13,5 g/dl')], known).length, 0);
  assert.equal(findLeaks([line('Hemoglobina 13,5 g/dl Testowy')], known).length, 1);
  assert.equal(findLeaks([line('44051401359')]).length, 1);
  assert.equal(findLeaks([[{ text: 'xq', confidence: 20 }]]).length, 0); // noise is ignored
});

test('ICD-9 PL code and the test name before it are kept', () => {
  const row = 'TSH (ICD-9: L69) 7,640 ulU/ml* 0,270-4,200 H';
  assert.deepEqual(keptWords(row), row.split(' '));
  assert.deepEqual(keptWords('Tyreotropina (ICD-9: L69) 2,15'), ['Tyreotropina', '(ICD-9:', 'L69)', '2,15']); // not in the dictionary
  assert.equal(kept('Pacjent Jan (ICD-9: L69)'), 0); // a personal label still wins
});

test('method lines are kept, except denylist hits', () => {
  const m = 'Badanie wykonano metodą elektrochemiluminescencji na aparacie Cobas 8000.';
  assert.deepEqual(keptWords(m), m.split(' '));
  assert.equal(kept('Badanie wykonano metodą ECLIA przez Testowy', prepareKnownIdentifiers('Jan Testowy')), 5);
});

test('dates of admission, analysis and release', () => {
  assert.equal(keptWords('Data/godz. wydania: 2026-05-28 11:38:55').length, 4);
  assert.equal(keptWords('Data/godz wykonania: 2026-05-28 11:38:53').length, 4);
});

const at = (s, y) => s.split(' ').map((text, i) => ({ text, confidence: 95, bbox: { x0: i * 100, y0: y, x1: i * 100 + 90, y1: y + 40 } }));

test('laboratory header above the first patient label', () => {
  const page = [at('LABORATORIUM PRZYKŁADOWE', 200), at('ul. Testowa 12/3, 00-950 Warszawa', 300), at('Pacjent: Jan Testowy', 500), at('Adres: ul. Przykładowa 5', 600)];
  const headerBottom = findHeaderBottom(page, 3508);
  assert.equal(headerBottom, 500);
  assert.equal(decideLine(page[1], [], { headerBottom }).filter(d => d.keep).length, 5); // lab address kept
  assert.equal(decideLine(page[3], [], { headerBottom }).filter(d => d.keep).length, 0); // patient address masked
  assert.equal(decideLine(at('Testowy 44051401359', 250), prepareKnownIdentifiers('Testowy'), { headerBottom }).filter(d => d.keep).length, 0);
  assert.equal(findLeaks([page[1]], [], { headerBottom }).length, 0);
});

test('no header zone without a patient label near the top', () => {
  assert.equal(findHeaderBottom([at('LABORATORIUM', 200), at('Glukoza 95 mg/dl', 1200)], 3508), 0);
  assert.equal(findHeaderBottom([at('LABORATORIUM', 200), at('Pacjent: Jan', 1500)], 3508), 0); // below 25% of the page
});
