# Source adapters and ingestion

Every adapter exposes `source_name`, `fetch_jobs()`, `normalize_job(raw)` and `health_check()`. Adapters produce validated `JobIn` objects, so source-specific payloads never leak into ranking logic.

## Implemented adapters

- Greenhouse: public Job Board API, `GET /v1/boards/{token}/jobs?content=true`.
- Lever: public Postings API, bounded pagination of 100 items, at most 10,000 postings.
- Ashby: public job-board postings API with compensation request flag.
- Official: operator-approved HTTPS JSON feeds containing a list or `{jobs:[...]}` in CareerOS normalized format. This is a feed contract, not arbitrary HTML scraping.
- Manual and Campus: authenticated entry/parse-and-review paths; no automated network discovery.

Reference documentation: [Greenhouse](https://docs.greenhouse.io/job-board.html), [Lever](https://github.com/lever/postings-api), [Ashby](https://developers.ashbyhq.com/docs/public-job-posting-api).

## Reliability path

1. Acquire the per-user writer lock shared by workers, manual ingestion, job edits and source edits.
2. Fetch with a 20-second timeout, public client User-Agent, no redirects, 10 MiB response limit and at most three attempts. Retry 429/transient 5xx/transport failures with 1- and 2-second backoff; other HTTP errors fail immediately.
3. Normalize each record inside a database savepoint. A malformed job increments parse errors without discarding other records.
4. Upsert canonical job and source occurrence; raw source payload stays with the occurrence.
5. Reconcile missing occurrences when enabled, then persist fetched/added/updated/closed/error counts, runtime and source status. Commit per source.
6. Generate high-match notifications independently. A failed source does not stop other sources.

HEALTHY means the last run completed with no parse errors, not that every job fact is certain. DEGRADED means partial parsing failures. FAILED means fetch/response failure. DISABLED is explicit. NOT_RUN is the additional truthful state for newly configured sources.

## Deduplication

Prefer company plus requisition ID; then normalized application URL with tracking parameters removed; otherwise company/title/country/location/type. An exact occurrence `(source, external_id)` reconnects updates. A conservative fuzzy title fallback requires same company, country, locations and employment type, similarity ≥0.96, and no conflicting requisition or same-source external IDs. Different requisition IDs remain different jobs.

Source occurrence identity and canonical job identity are separate. A merged duplicate still has an occurrence. First discovery is not reset; last-seen changes. The primary source is identified by source ID, not just adapter kind, so another Greenhouse board cannot overwrite the first board’s facts. Human-reviewed corrections and explicit manual archive are preserved on refresh. A manual update may intentionally replace structured facts. Cross-source conflicts can still require review; V1 is conservative rather than pretending fuzzy deduplication is perfect.

## Adding sources responsibly

Use a documented public API or an explicitly permitted feed. Put board tokens in Source configuration; user input cannot choose the Greenhouse/Lever/Ashby hostname. Custom feed hosts are controlled by the deployment operator, use HTTPS/443, reject private DNS addresses and redirects. Only allow domains you control or trust; DNS checks are not a substitute for outbound network controls. No cookies, credentials, CAPTCHA bypass or private LinkedIn scraping are supported.

Keep `country=Unknown` for multi-country boards. Imported skills are prose-based suggestions. Hard requirements remain review-required until confirmed. `refresh-jobs` re-fetches sources. Closure reconciliation defaults off. Set `close_missing_after` to 2–10 consecutive complete, nonempty, error-free snapshots to mark a missing occurrence inactive. Empty, failed and partially parsed snapshots never advance this counter. A canonical job closes only when every occurrence is inactive; a reappearing occurrence can reopen a source-closed job. Explicit manual archive survives refresh until the user selects Restore. Unconfirmed extracted dates do not close jobs.

Source configuration can be edited in the UI. Once a source has imported occurrences, changing adapter kind, board token or feed URL returns 409; create a new source to preserve provenance. Country/company defaults, closure policy and enabled state remain editable.
