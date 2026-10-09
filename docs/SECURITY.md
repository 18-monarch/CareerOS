# Security model

## Authentication and browser boundary

Passwords are hashed with Argon2id (64 MiB memory, 3 iterations, 2 lanes). Password whitespace is preserved exactly. There is no JWT signing key. Access, refresh and CSRF secrets are generated with a cryptographic RNG; only SHA-256 token digests are persisted. Access lasts 15 minutes, refresh/session 7 days. Refresh rotates all secrets under a row lock; logout deletes the session. An expired/revoked session fails on the server even if a browser still has a cookie.

Cookies are HttpOnly for access/refresh, host-only, SameSite=Lax and Secure in production. CSRF is a random readable cookie that must match both the mutation header and the stored session digest. Origin must match the configured frontend. Login/register also reject an unexpected Origin to prevent login CSRF. The Next.js gateway enforces origin checks on browser mutations and forwards only a fixed set of headers to a configured backend URL. No bearer token is stored in localStorage; only theme preference is stored there.

Failed initial authentication does not trigger endless refresh requests. Concurrent browser requests share a refresh promise. Cache data is cleared on logout/expiration to avoid displaying a previous user's private workspace.

Authenticated password changes require the current password, are rate limited, revoke all prior sessions, and issue one new current session. `careeros.manage` provides hidden-prompt account creation and audited operator password reset; no password is accepted as a command-line argument.

## Authorization and data

Every user-owned query scopes ownership. Job/application/project/source/resume ID mutation routes validate the server-side owner. A guessed UUID returns 404. Joined resources derive ownership through parents. All writes use validated schemas and parameterized SQLAlchemy expressions. Database constraints enforce uniqueness. Application event history has a database trigger preventing update/deletion.

The API bounds the actual request body to 1 MiB, including chunked requests, and rejects invalid Content-Length values.

The frontend renders text, never raw job HTML. HTML descriptions are converted to plain text. Links accept only HTTP(S) without embedded credentials. External links use noreferrer. No user-supplied host is used by the gateway.

## Ingestion and external services

Public ATS hosts are hardcoded; board tokens permit only letters, numbers, underscores and hyphens. Custom official feeds require an operator allowlist, HTTPS/443, global DNS addresses, no redirects, response limits and timeouts. Allowlisting a hostile/rebinding domain would still be unsafe; only trust known official endpoints and add infrastructure egress restrictions for broader multi-user deployment.

Sensitive auth endpoints use database-backed atomic rate buckets keyed by hashed email/IP. The API sees the frontend gateway IP in proxied deployments; the IP budget therefore applies to the small workspace collectively, while the email budget is specific. Do not trust arbitrary forwarded IP headers without a gateway-authentication design. Add a managed edge rate limiter for a public product.

AI endpoints are operator configured, not user chosen. They receive only the pasted description, validate schema output, mark claims unconfirmed and cannot override hard eligibility. Email receives the user's enabled digest content, never passwords/session tokens.

## Headers, logs and secrets

API responses use no-store, request IDs, nosniff, frame denial and strict referrer policy. Production enables HSTS. Next.js adds a restrictive CSP and disables camera/microphone/geolocation. CSP currently permits inline scripts for Next.js bootstrap and inline styles; a nonce-based CSP is a further hardening task, not a claim made by V1.

Logs do not include request bodies, raw tokens, passwords, authorization headers or resume contents. Upstream errors are summarized by class rather than dumping URLs/credentials. `.env` and database files are ignored by Git and excluded from Docker build contexts. Provider keys belong only in deployment secrets. No live key is shipped.

## Production limits

V1 is designed for a private account, with multi-user ownership enforced. It has no email verification, self-service password reset, MFA, public-registration bot protection or complete account-erasure UI. Close registration after onboarding. Credential recovery uses the trusted-operator `careeros.manage reset-password` command; do not make the app a public signup service until recovery/verification and abuse controls are implemented and tested.

Resume PDFs are stored as private per-account database records (650 KB maximum), with integrity hashes; database backups therefore contain personal resume data. The optional local runner sends an approved PDF and truthful profile fields only to the selected supported employer form. It pauses for unsupported questions, consent controls, CAPTCHAs and ambiguous results. Keep the local database and approval settings private. Backups, account access, external monitoring, retention, and platform permissions are operator responsibilities. The repository provides controls and tests, not a third-party security audit.
