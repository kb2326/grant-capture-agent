# ADR-0004: Document parsing (revised in M1)

- Status: Accepted (revised 2026-10-09; supersedes the 2026-10-07 "Docling for parsing" decision)
- Date: 2026-10-07, revised 2026-10-09
- Deciders: Karthick Balaje

## Context
Solicitations are long, table-heavy documents. The Analyze module must quote clauses exactly and cite pages, and every quote is checked by code against stored text. Parsing has to keep page boundaries, run on the whole corpus, and fit a $10/month budget.

The original decision (Docling for everything) was made before measuring. M1 measured the corpus first:

| Fact (2026-10-09) | Value |
|---|---|
| Stored documents | 736: 357 PDF, 320 HTML, 58 DOCX, 1 DOC |
| PDF length | median 26 pages, max 166; 10,691 pages total |
| Docling PDF pipeline (CPU, warm) | 2.46 s/page, about 7.3 h for the corpus |
| pypdf text layer | 0.066 s/page; the full corpus parsed in about 9 minutes |
| Document AI Layout Parser | $10 per 1,000 pages, about $107 for the corpus |
| Largest package | about 100k tokens, inside Gemini's context window |
| Parse result | 533 parsed, 4 scanned PDFs (no text layer), 1 legacy .doc unsupported, 0 failures |

## Decision
Split the two jobs parsing used to do:

1. **Understanding** a document is Gemini's job. PDFs are sent natively (Gemini sees layout, tables and page numbers); HTML and DOCX are sent as page/section-tagged text.
2. **Verifying** quotes needs a cheap, deterministic text layer: pypdf per PDF page; BeautifulSoup + markdownify for HTML; python-docx for DOCX. One chunk per page or heading section, stored in `chunks` with its page number.

## Alternatives considered
- Docling for everything: best open-source structure, but 7 hours of CPU for the corpus, and it brings PyTorch into the ingestion image even for HTML/DOCX.
- Document AI Layout Parser: good quality, about $107 for the corpus, over budget.
- Text-only extraction for the model too: cheap, but it loses tables and layout that Gemini reads natively.

## Consequences
- Parsing the whole corpus takes minutes and costs nothing.
- A quote that pypdf extracts differently from the PDF (ligatures, hyphenation, columns) can fail verification. Normalisation (NFKC, whitespace and hyphen removal, adjacent-page spans) handles the common cases; quote fidelity is measured in every eval run.
- Scanned PDFs (no text layer) cannot be verified, so their clauses become NEEDS_REVIEW.
- Docling and Layout Parser are compared in M5 on a sample, as an upgrade path for the text layer.
