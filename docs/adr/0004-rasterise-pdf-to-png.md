# 4. Rasterise incoming PDFs to PNG

Date: 2026-11-17

## Status

Accepted

## Context

A PDF from a lab is untrusted input:
- The format allows JavaScript, embedded files, launch actions and complex fonts, which is a large attack surface for the parser.
- Metadata (author, producer, dates, XMP) may contain personal data.
- Hidden text, e.g. white on white or outside the page, may carry a prompt injection aimed at the LLM (OWASP Top 10 for LLM Applications).
- Masking from [ADR-0003](0003-mask-personal-data-before-ai.md) must be irreversible. In a PDF, a black rectangle is often only an overlay, and the text underneath remains.

Rasterisation, i.e. turning every page into pixels, is a known CDR (Content Disarm & Reconstruction) technique, used for example by Dangerzone. Sources: [OCRmyPDF security](https://ocrmypdf.readthedocs.io/en/v8.0.0/security.html), [Dangerzone](https://starlog.pages.dev/articles/developer-tools/freedomofpress-dangerzone).

### Considered options

1. **Keep the PDF.** No work, but no protection against any of the problems above.
2. **Sanitise the PDF** (qpdf, pdfcpu: strip JavaScript and embedded files). Keeps the text layer, but hidden text survives and masking remains problematic.
3. **Rasterise to JPG.** Small files, but lossy compression. Artefacts may distort digits, and numbers must be 100% correct.
4. **Rasterise to BMP.** Lossless, but very large files and no advantage over PNG.
5. **Rasterise to PNG.** Lossless, compressed, and free of metadata when written by our code.

## Decision

We choose option 5. The sanitiser renders every page to PNG at a fixed resolution: 300 DPI to start with, to be confirmed by OCR evals. All metadata is stripped. From this point on the system works on images only, and the original PDF is not kept ([ADR-0005](0005-no-archive-of-originals.md)).

The sanitiser runs in an isolated container:
- no internet access, only private endpoints to Storage and Key Vault,
- as a non-root user,
- with memory, CPU and time limits, plus limits on file size and page count,
- with file type validation by magic bytes, not by extension.

The rendering library (e.g. poppler `pdftoppm` or PyMuPDF) will be chosen during implementation.

## Consequences

- Active PDF content, metadata and hidden text do not pass further.
- Masking is burned into the pixels and cannot be undone.
- The text layer is lost, so everything depends on OCR. Document Intelligence performs OCR anyway, and the extraction evals measure its quality.
- Files are several times larger than the PDF. With a single user the cost is negligible.
- The rendering library still parses untrusted PDFs. The risk is moved into an isolated container, not removed. The library must be kept up to date.
