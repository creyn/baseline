"""Generates fictional lab result documents from the descriptions in documents/.

Output (never committed; see .gitignore): out/<id>/text.pdf, scan.pdf, photo-<page>.jpg,
truth.json, and out/index.html. The same descriptions give byte-identical files.

Needs reportlab, Pillow and pypdfium2 (requirements.txt) and the DejaVu Sans font.
Usage: python3 evals/synthetic/generate.py [--out DIR] [--only ID]
"""
import argparse
import hashlib
import html
import io
import json
import os
import random
import sys

from PIL import Image, ImageChops, ImageFilter, ImageOps
import pypdfium2
from reportlab import rl_config
from reportlab.graphics.barcode import code128
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader, simpleSplit
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import describe  # noqa: E402

rl_config.invariant = 1  # fixed dates and ids inside the PDF: byte-identical output
W, H = A4
FONT, BOLD = 'DejaVu', 'DejaVu-Bold'
FONT_DIRS = [os.environ.get('FONT_DIR', ''), '/usr/share/fonts/truetype/dejavu', '/usr/share/fonts/dejavu']


def register_fonts():
    for d in FONT_DIRS:
        regular, bold = os.path.join(d, 'DejaVuSans.ttf'), os.path.join(d, 'DejaVuSans-Bold.ttf')
        if d and os.path.isfile(regular) and os.path.isfile(bold):
            pdfmetrics.registerFont(TTFont(FONT, regular))
            pdfmetrics.registerFont(TTFont(BOLD, bold))
            return
    sys.exit('DejaVu Sans not found. Install fonts-dejavu-core or set FONT_DIR.')


def seed(doc_id, form):
    return int(hashlib.sha256(f'{doc_id}/{form}'.encode()).hexdigest()[:16], 16)


# ------------------------------------------------------------------ drawing helpers
class Pen:
    def __init__(self, c):
        self.c = c

    def text(self, x, y, s, size=9, bold=False, right=False, centre=False):
        self.c.setFont(BOLD if bold else FONT, size)
        if right:
            self.c.drawRightString(x, y, s)
        elif centre:
            self.c.drawCentredString(x, y, s)
        else:
            self.c.drawString(x, y, s)

    def wrap(self, x, y, s, width, size=8, leading=10, bold=False):
        for line in simpleSplit(s, BOLD if bold else FONT, size, width):
            self.text(x, y, line, size, bold)
            y -= leading
        return y

    def rule(self, y, x0=36, x1=W - 36, width=0.6):
        self.c.setLineWidth(width)
        self.c.line(x0, y, x1, y)

    def barcode(self, x, y, value):
        code128.Code128(value, barHeight=22, barWidth=0.75, humanReadable=False).drawOn(self.c, x, y)

    def stamp(self, x, y, lab):
        c = self.c
        c.saveState()
        c.setStrokeColorRGB(0.15, 0.2, 0.55)
        c.setFillColorRGB(0.15, 0.2, 0.55)
        c.setLineWidth(1.2)
        c.circle(x, y, 30)
        c.circle(x, y, 24)
        c.setFont(BOLD, 5.5)
        c.drawCentredString(x, y + 4, lab['name'].split(' ')[0].upper())
        c.setFont(FONT, 5)
        c.drawCentredString(x, y - 4, 'DIAGNOSTA LAB.')
        c.restoreState()

    def signature(self, x, y):
        c = self.c
        c.saveState()
        c.setStrokeColorRGB(0.1, 0.1, 0.35)
        c.setLineWidth(0.9)
        p = c.beginPath()
        p.moveTo(x, y)
        p.curveTo(x + 15, y + 18, x + 22, y - 12, x + 38, y + 6)
        p.curveTo(x + 50, y + 16, x + 58, y - 8, x + 75, y + 3)
        c.drawPath(p)
        c.restoreState()


def range_text(r):
    if r.get('min') is not None and r.get('max') is not None:
        return f'{r["min"]} - {r["max"]}'
    return r.get('range') or ''


def footer(pen, doc, page_no, pages):
    staff = [s for s in doc['staff'] if not s['in_table']]
    pen.rule(118)
    y = 104
    for s in staff:
        pen.text(40, y, f'{s["role"]}: {s["name"]}', 8)
        y -= 11
    pen.stamp(330, 80, doc['lab'])
    pen.signature(390, 70)
    pen.text(W - 40, 104, f'Data wydruku: {doc["printed"]}', 8, right=True)
    pen.text(W - 40, 40, f'Strona {page_no} z {pages}', 7, right=True)
    pen.text(40, 40, f'{doc["lab"]["name"]}, {doc["lab"]["address"]}', 6.5)


# ------------------------------------------------------------------ layout A
def page_a(pen, doc, page, page_no, pages):
    lab, p = doc['lab'], doc['patient']
    pen.text(40, 800, lab['name'], 11, bold=True)
    pen.text(40, 788, lab['address'], 8)
    pen.text(40, 778, lab['phone'], 8)
    pen.text(380, 800, f'Nr zlecenia: {doc["order_no"]}', 8)
    pen.barcode(380, 768, doc['order_no'])
    y = 735
    for line in (f'Pacjent: {p["name"]}', f'PESEL: {p["pesel"]}    Data urodzenia: {p["birth_date"]}    Płeć: {p["sex"]}',
                 f'Adres: {p["address"]}', f'Zlecający: {doc["orderer"]}'):
        pen.text(40, y, line, 9)
        y -= 13
    for f in doc['dates']:
        if f['where'] == 'header':
            pen.text(380, 735, f'{f["label"]}: {f["value"]}', 8)
    y = 660
    cols = [(40, 'Badanie'), (250, 'Wynik'), (318, 'Jedn.'), (380, 'MIN'), (430, 'MAX'), (490, 'FLAGA')]
    if page['table_header']:
        pen.rule(y + 12)
        for x, t in cols:
            pen.text(x, y, t, 8.5, bold=True)
        pen.rule(y - 5)
        y -= 26
    for sec in page['sections']:
        pen.text(40, y, f'{sec["title"]} (ICD-9: {sec["icd9"]})', 9, bold=True)
        dy = y
        for f in sec.get('dates', []):
            pen.text(380, dy, f'{f["label"]}: {f["value"]}', 7.5)
            dy -= 10
        y = min(y, dy) - 14
        for r in sec['results']:
            if r.get('range_lines'):
                pen.text(46, y, f'Wynik badania: {r["value"]} {r["unit"]}'.rstrip(), 9)
                if r.get('flag'):
                    pen.text(490, y, r['flag'], 9, bold=True)
                y -= 13
                for line in r['range_lines']:
                    pen.text(60, y, line, 7.5)
                    y -= 10
                continue
            pen.text(46, y, r['name'], 9)
            pen.text(250, y, r['value'], 9, bold=bool(r.get('flag')))
            pen.text(318, y, r['unit'], 8.5)
            if r.get('min') is not None:
                pen.text(380, y, r['min'], 8.5)
                pen.text(430, y, r['max'], 8.5)
            else:
                pen.text(380, y, r.get('range') or '', 8.5)
            if r.get('flag'):
                pen.text(490, y, r['flag'], 9, bold=True)
            y -= 13
        if sec.get('method'):
            y = pen.wrap(46, y - 2, sec['method'], 480, 7.5)
        for note in sec.get('notes', []):
            y = pen.wrap(46, y, note, 480, 7)
        for c in sec.get('comment', []):
            y = pen.wrap(46, y, c, 480, 8)
        y -= 12
    for s in doc['staff']:
        if s['in_table']:
            pen.text(46, y, f'{s["role"]}: {s["name"]}', 8)
            y -= 12
    footer(pen, doc, page_no, pages)


# ------------------------------------------------------------------ layout B
def page_b(pen, doc, page, page_no, pages):
    lab, p = doc['lab'], doc['patient']
    pen.text(W / 2, 805, lab['name'], 12, bold=True, centre=True)
    pen.text(W / 2, 792, f'{lab["address"]}, {lab["phone"]}', 8, centre=True)
    y = 760
    for line in (f'Pacjent: {p["name"]}', f'PESEL: {p["pesel"]}    Data urodzenia: {p["birth_date"]}',
                 f'Adres: {p["address"]}', f'Zleceniodawca: {doc["orderer"]}    Nr zlecenia: {doc["order_no"]}'):
        pen.text(150, y, line, 9)
        y -= 13
    y -= 8
    for f in doc['dates']:
        if f['where'] == 'middle':
            pen.text(150, y, f'{f["label"]}: {f["value"]}', 9)
            y -= 13
    pen.barcode(430, 700, doc['order_no'])
    y = 600
    if page['table_header']:
        pen.rule(y + 14)
        for x, t in ((40, 'ICD9'), (78, 'Nazwa'), (262, 'Wynik'), (312, 'j.m.'), (362, 'Wartość referencyjna/'), (495, 'Procedura/')):
            pen.text(x, y, t, 8, bold=True)
        pen.text(362, y - 9, 'decyzyjna', 8, bold=True)
        pen.text(495, y - 9, 'Instrukcja nr', 8, bold=True)
        pen.rule(y - 14)
        y -= 30
    for sec in page['sections']:
        pen.text(78, y, sec['title'], 9, bold=True)
        y -= 16
        for r in sec['results']:
            pen.text(40, y, r.get('icd9') or '', 8.5)
            ny = y
            for line in simpleSplit(r['name'], FONT, 8.5, 175):
                pen.text(78, ny, line, 8.5)
                ny -= 10
            pen.text(262, y, r['value'], 8.5, bold=bool(r.get('flag')))
            pen.text(312, y, r['unit'], 8)
            ry = y
            first = range_text(r)
            if first and not r.get('range_lines'):
                pen.text(362, ry, first + (f'  {r["flag"]}' if r.get('flag') else ''), 8)
                ry -= 10
            for line in r.get('range_lines', []):
                ry = pen.wrap(362, ry, line, 128, 7, 8.5)
            if r.get('method'):
                ry = pen.wrap(362, ry, r['method'], 128, 7, 8.5)
            if r.get('procedure'):
                pen.text(495, y, r['procedure'], 8)
            y = min(ny, ry) - 8
        for c in sec.get('comment', []):
            y = pen.wrap(78, y, c, 400, 8)
        y -= 6
    for s in doc['staff']:
        if s['in_table']:
            pen.text(78, y, f'{s["role"]}: {s["name"]}', 8)
            y -= 12
    footer(pen, doc, page_no, pages)


# ------------------------------------------------------------------ layout C
def page_c(pen, doc, page, page_no, pages):
    lab, p = doc['lab'], doc['patient']
    pen.text(W / 2, 805, lab['name'], 12, bold=True, centre=True)
    pen.text(W / 2, 793, f'{lab["address"]}, {lab["phone"]}', 8, centre=True)
    pen.text(W - 40, 770, f'Nr zlecenia: {doc["order_no"]}', 8, right=True)
    pen.barcode(W - 160, 740, doc['order_no'])
    y = 760
    for line in (f'Pacjent: {p["name"]}', f'PESEL: {p["pesel"]}', f'Data urodzenia: {p["birth_date"]}',
                 f'Adres: {p["address"]}', f'Lekarz kierujący: {doc["orderer"]}'):
        pen.text(40, y, line, 9)
        y -= 13
    for f in doc['dates']:
        if f['where'] == 'patient':
            pen.text(40, y, f'{f["label"]}: {f["value"]}', 9)
            y -= 13
    y = 610
    if page['table_header']:
        pen.rule(y + 12)
        for x, t in ((40, 'Badanie'), (238, 'Wynik'), (296, 'Jedn.'), (358, 'Zakres referencyjny'), (510, 'LIW')):
            pen.text(x, y, t, 8.5, bold=True)
        pen.rule(y - 5)
        y -= 26
    for sec in page['sections']:
        for r in sec['results']:
            pen.text(40, y, f'{r["name"]} (ICD-9: {r["icd9"]})', 9)
            pen.text(238, y, r['value'], 9, bold=bool(r.get('flag')))
            pen.text(296, y, r['unit'] + ('*' if r['unit'] else ''), 8.5)
            if r.get('min') is not None:
                pen.text(358, y, r['min'], 8.5)
                pen.text(420, y, r['max'], 8.5)
            else:
                pen.text(358, y, r.get('range') or '', 8.5)
            if r.get('flag'):
                pen.text(510, y, r['flag'], 9, bold=True)
            y -= 13
            if r.get('method'):
                y = pen.wrap(56, y, r['method'], 470, 7.5)
            y -= 8
        for c in sec.get('comment', []):
            y = pen.wrap(40, y, c, 480, 8)
    for s in doc['staff']:
        if s['in_table']:
            pen.text(40, y, f'{s["role"]}: {s["name"]}', 8)
            y -= 12
    if page.get('samples'):
        y -= 8
        pen.text(40, y, 'Informacje dodatkowe', 9, bold=True)
        y -= 14
        for smp in page['samples']:
            first = True
            for f in smp['dates']:
                pen.text(40, y, smp['material'] if first else '', 8)
                pen.text(110, y, f'{f["label"]}: {f["value"]}', 8)
                first = False
                y -= 11
            y -= 4
    footer(pen, doc, page_no, pages)


LAYOUT = {'A': page_a, 'B': page_b, 'C': page_c}


# ------------------------------------------------------------------ forms
def text_pdf(doc):
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setTitle('Wynik badania laboratoryjnego')
    c.setAuthor(doc['lab']['name'])
    pages = doc['pages']
    for i, page in enumerate(pages, 1):
        LAYOUT[doc['layout']](Pen(c), doc, page, i, len(pages))
        c.showPage()
    c.save()
    return buf.getvalue()


def rasterise(pdf, dpi):
    pdf_doc = pypdfium2.PdfDocument(pdf)
    try:
        return [pdf_doc[i].render(scale=dpi / 72).to_pil() for i in range(len(pdf_doc))]
    finally:
        pdf_doc.close()


def jpeg(img, quality):
    buf = io.BytesIO()
    img.save(buf, 'JPEG', quality=quality, optimize=False, progressive=False, subsampling=2)
    return buf.getvalue()


def noise(rnd, size, strength):
    raw = Image.frombytes('L', size, rnd.randbytes(size[0] * size[1]))
    return raw.point(lambda v: 128 + (v - 128) * strength // 128)


def scan_pdf(doc, pdf):
    rnd = random.Random(seed(doc['id'], 'scan'))
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    for img in rasterise(pdf, 200):
        img = img.convert('L').point(lambda v: 18 + v * 222 // 255)      # grey paper, ink not fully black
        img = img.rotate(rnd.uniform(-1.0, 1.0), resample=Image.BICUBIC, fillcolor=236)
        img = ImageChops.add(img, noise(rnd, img.size, 22), scale=1, offset=-128)
        img = img.filter(ImageFilter.GaussianBlur(0.5))
        c.drawImage(ImageReader(io.BytesIO(jpeg(img, 82))), 0, 0, W, H)
        c.showPage()
    c.save()
    return buf.getvalue()


def solve(a, b):
    """Gaussian elimination for the 8x8 system of a perspective transform."""
    n = len(b)
    m = [row[:] + [b[i]] for i, row in enumerate(a)]
    for col in range(n):
        piv = max(range(col, n), key=lambda r: abs(m[r][col]))
        m[col], m[piv] = m[piv], m[col]
        for r in range(n):
            if r != col:
                f = m[r][col] / m[col][col]
                m[r] = [x - f * y for x, y in zip(m[r], m[col])]
    return [m[i][n] / m[i][i] for i in range(n)]


def perspective(src, dst):
    """Coefficients for Image.transform: maps each output point in dst to the input point in src."""
    a, b = [], []
    for (x, y), (X, Y) in zip(dst, src):
        a.append([x, y, 1, 0, 0, 0, -X * x, -X * y]); b.append(X)
        a.append([0, 0, 0, x, y, 1, -Y * x, -Y * y]); b.append(Y)
    return solve(a, b)


def photos(doc, pdf):
    rnd = random.Random(seed(doc['id'], 'photo'))
    out = []
    for img in rasterise(pdf, 150):
        paper = img.convert('RGB')
        pw, ph = paper.size
        dw, dh = int(pw * 1.22), int(ph * 1.16)
        desk = Image.new('RGB', (dw, dh), (112, 92, 74))
        desk = ImageChops.add(desk, noise(rnd, (dw, dh), 30).convert('RGB'), scale=1, offset=-128)
        ox, oy = (dw - pw) // 2, (dh - ph) // 2
        desk.paste(paper, (ox, oy))
        j = lambda v: v * rnd.uniform(0.0, 0.045)
        src = [(ox, oy), (ox + pw, oy), (ox + pw, oy + ph), (ox, oy + ph)]
        dst = [(ox + j(pw), oy + j(ph)), (ox + pw - j(pw), oy + j(ph)), (ox + pw - j(pw), oy + ph - j(ph)), (ox + j(pw), oy + ph - j(ph))]
        img = desk.transform((dw, dh), Image.PERSPECTIVE, perspective(src, dst), resample=Image.BICUBIC, fillcolor=(112, 92, 74))
        shade = Image.linear_gradient('L').rotate(rnd.choice([90, -90, 0, 180])).resize((dw, dh)).point(lambda v: v * 70 // 255)
        img = Image.composite(Image.new('RGB', (dw, dh), (0, 0, 0)), img, shade)
        img = ImageOps.autocontrast(img.filter(ImageFilter.GaussianBlur(0.8)), cutoff=0)
        out.append(jpeg(img, 85))
    return out


# ------------------------------------------------------------------ output
def truth(doc):
    return {'id': doc['id'], 'layout': doc['layout'], 'pages': len(doc['pages']),
            'results': describe.expected_extraction(doc), 'must_remove': describe.must_remove(doc),
            'must_keep': describe.must_keep(doc), 'known_gaps': doc.get('known_gaps', []), 'traps': doc['traps']}


def build(doc, folder):
    os.makedirs(folder, exist_ok=True)
    written = {}

    def put(name, data):
        with open(os.path.join(folder, name), 'wb') as f:
            f.write(data)
        written[name] = hashlib.sha256(data).hexdigest()

    pdf = text_pdf(doc)
    if 'text' in doc['forms']:
        put('text.pdf', pdf)
    if 'scan' in doc['forms']:
        put('scan.pdf', scan_pdf(doc, pdf))
    if 'photo' in doc['forms']:
        for i, data in enumerate(photos(doc, pdf), 1):
            put(f'photo-{i}.jpg', data)
    put('truth.json', (json.dumps(truth(doc), ensure_ascii=False, indent=2) + '\n').encode())
    return written


def index(docs, built):
    rows = []
    for d in docs:
        links = ' · '.join(f'<a href="{html.escape(d["id"])}/{n}">{n}</a>' for n in sorted(built[d['id']]))
        rows.append(f'<tr><td>{html.escape(d["id"])}</td><td>{d["layout"]}</td><td>{len(d["pages"])}</td>'
                    f'<td>{links}</td><td>{html.escape(", ".join(d["traps"]))}</td></tr>')
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1"><title>Synthetic lab results</title>'
            '<style>body{font-family:system-ui;max-width:1000px;margin:2rem auto;padding:0 16px}'
            'table{border-collapse:collapse;width:100%}td,th{border-bottom:1px solid #ddd;padding:6px;text-align:left;font-size:14px}'
            '</style></head><body><h1>Synthetic lab results</h1>'
            '<p>Fictional documents for testing masking and extraction. Every person, laboratory and number is invented. '
            'truth.json holds the expected results and what masking must remove.</p>'
            '<table><tr><th>Document</th><th>Layout</th><th>Pages</th><th>Files</th><th>Traps</th></tr>'
            + ''.join(rows) + '</table></body></html>\n')


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--out', default=os.path.join(describe.HERE, 'out'))
    ap.add_argument('--only')
    args = ap.parse_args(argv)
    register_fonts()
    docs = [d for d in describe.load_all() if not args.only or d['id'] == args.only]
    built = {d['id']: build(d, os.path.join(args.out, d['id'])) for d in docs}
    with open(os.path.join(args.out, 'index.html'), 'w', encoding='utf-8') as f:
        f.write(index(docs, built))
    with open(os.path.join(args.out, 'sha256.json'), 'w', encoding='utf-8') as f:
        json.dump(built, f, indent=2, sort_keys=True)
    print(f'{sum(len(v) for v in built.values())} files for {len(docs)} documents in {args.out}')


if __name__ == '__main__':
    main()
