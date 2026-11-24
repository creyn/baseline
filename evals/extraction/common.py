"""Paths and the truth shared by the offline and the live evals."""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..'))
for path in (os.path.join(ROOT, 'services', 'extractor'), os.path.join(ROOT, 'evals', 'synthetic')):
    if path not in sys.path:
        sys.path.insert(0, path)

import describe  # noqa: E402  evals/synthetic/describe.py

_FORMATS = (
    (re.compile(r'^(\d{4})-(\d{2})-(\d{2})(?: (\d{2}):(\d{2})(?::\d{2})?)?$'), (0, 1, 2)),
    (re.compile(r'^(\d{2})[.-](\d{2})[.-](\d{4})(?: (\d{2}):(\d{2})(?::\d{2})?)?$'), (2, 1, 0)),
)
_KINDS = (('pobra', 'collected'), ('rejestr', 'registered'), ('przyję', 'received'), ('wykona', 'performed'),
          ('wydania', 'released'), ('autoryz', 'released'), ('wydruku', 'printed'))


def local(value):
    """A printed date ('02.03.2026 08:50:00', '2026-04-10') as the model should read it."""
    for pattern, (y, m, d) in _FORMATS:
        found = pattern.match(value.strip())
        if found:
            g = found.groups()
            out = f'{g[y]}-{g[m]}-{g[d]}'
            return out + (f'T{g[3]}:{g[4]}' if g[3] else '')
    raise ValueError('unknown date format in a synthetic description')


def kind(label):
    low = label.lower()
    return next((k for key, k in _KINDS if key in low), 'other')


def documents():
    return describe.load_all()
