# ADR-0004: Docling for parsing

- Status: Accepted
- Date: 2026-10-07
- Deciders: Karthick Balaje

## Context
Solicitations are long, table-heavy PDFs, typically 30 to 150 pages. The Analyze agent must quote clauses exactly and cite page numbers, and headings and tables carry meaning (a clause's category often comes from its heading). Parsing therefore has to preserve structure and page boundaries, and it has to be cheap enough to run on every attachment within a $10/month budget.

## Decision
Parse documents with Docling, keeping structure: headings, tables and page numbers. Text is page-tagged so quotes keep their page.

## Alternatives considered
- Document AI Layout Parser: good quality, but it has a per-page cost that adds up across thousands of pages.
- Plain text extraction: free and simple, but it loses headings, tables and layout, which breaks clause context and citations.

## Consequences
Parsing runs locally in the ingestion job at no per-page fee, and we get structure-aware text that supports page-accurate citations. We must handle Docling's failure modes (scanned or malformed PDFs) and its processing time. Gemini multimodal parsing is a possible fallback for hard documents; it is evaluated in M5 and recorded in ADR-0011.
