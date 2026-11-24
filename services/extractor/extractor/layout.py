"""Words with positions, as the extractor keeps them, and the page text the LLM reads.

The Document Intelligence adapter turns its answer into plain words: text, a box as
fractions of the page from the top left, and a confidence. Ids (p{page}w{n}) are given
here, in reading order, so the LLM can name the words it read a value from.
"""
from statistics import median


def box_from_polygon(polygon, width, height):
    """A polygon [x1, y1, x2, y2, ...] in page units -> a box of fractions, clamped to the page."""
    xs, ys = polygon[0::2], polygon[1::2]
    x0, x1 = max(0.0, min(xs) / width), min(1.0, max(xs) / width)
    y0, y1 = max(0.0, min(ys) / height), min(1.0, max(ys) / height)
    return {'x': round(x0, 5), 'y': round(y0, 5), 'w': round(max(0.0, x1 - x0), 5), 'h': round(max(0.0, y1 - y0), 5)}


def union(boxes):
    x0 = min(b['x'] for b in boxes)
    y0 = min(b['y'] for b in boxes)
    x1 = max(b['x'] + b['w'] for b in boxes)
    y1 = max(b['y'] + b['h'] for b in boxes)
    return {'x': round(x0, 5), 'y': round(y0, 5), 'w': round(x1 - x0, 5), 'h': round(y1 - y0, 5)}


def lines(words):
    """Groups words into lines by their vertical centre, each line from left to right."""
    if not words:
        return []
    tolerance = 0.5 * median(w['box']['h'] for w in words) or 0.005
    out = []
    for w in sorted(words, key=lambda w: (w['box']['y'] + w['box']['h'] / 2, w['box']['x'])):
        centre = w['box']['y'] + w['box']['h'] / 2
        if out and abs(centre - out[-1]['centre']) <= tolerance:
            out[-1]['words'].append(w)
        else:
            out.append({'centre': centre, 'words': [w]})
    return [sorted(line['words'], key=lambda w: w['box']['x']) for line in out]


def number(pages_words):
    """[[word, ...] per page] -> pages with ids in reading order (lines top to bottom)."""
    out = []
    for index, words in enumerate(pages_words, 1):
        ordered = [w for line in lines(words) for w in line]
        out.append([{'id': f'p{index}w{n}', 'text': w['text'], 'box': w['box'], 'confidence': w['confidence']}
                    for n, w in enumerate(ordered, 1)])
    return out


def page_text(index, words):
    """The text of one page for the prompt: one line per printed line, every word with its id."""
    rows = [' '.join(f'[{w["id"]}]{w["text"]}' for w in line) for line in lines(words)]
    return f'## Page {index}\n' + '\n'.join(rows)
