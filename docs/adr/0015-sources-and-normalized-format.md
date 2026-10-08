# ADR-0015: Sources and normalized format

- Status: Accepted
- Date: 2026-10-07
- Deciders: Karthick Balaje

## Context
We tested the sources on 2026-10-07. The SBIR.gov search API returns 403 and DSIP blocks access. The SAM.gov API allows only about 10 requests per day, but SAM publishes a free daily CSV extract with full descriptions. Simpler Grants serves the CommonGrants format natively.

## Decision
Index Grants.gov (API) and SAM.gov (the daily CSV). Use the SAM API only for on-demand attachments. Use USAspending, NIH RePORTER, NSF (live) and the SBIR award CSV as context. Validate our export against the CommonGrants SDK.

## Alternatives considered
- SAM API for bulk loading: the quota of about 10 requests per day makes it impractical.
- Scraping SBIR.gov or DSIP: fragile and against their terms.
- A source-specific schema: every new source would force changes downstream, instead of mapping once into a shared format.

## Consequences
Bulk loading uses one 210 MB daily download and needs no quota, with a hard request budget guarding any API use. SAM attachments arrive later than Grants.gov ones, because they are fetched on demand. Normalizing to CommonGrants gives a stable contract for retrieval and makes the data portable. We will watch for changes in extract format.
