# MAM816 — local Polar integration and separate LIVE gate

## Goal

Server-selected USD5/month plus exclusive tax, native seven-day trial with payment
method, checkout/customer portal and authoritative reconciliation. This delivery
is local code and executable contract evidence, **not Sandbox LIVE or Done**.

## Context

Based on `88e5dd013ff398b55b9d1ea65fde7ffa068ca879`. Reuses the pinned
HTTPX0.28.1 and StandardWebhooks1.1.0 dependencies; no new SDK or service broker.
[Current API docs](https://polar.sh/docs/api-reference/current/introduction.md)
explicitly reference2026-10. REST requests pin `Polar-Version: 2026-10` and reject
missing/incompatible response versions. The MCP's2027-01 model does not select
the application's contract.

## Constraints

No provider transactions, organizations, credentials, SMTP, production deployment
or public tunnel are activated by this change. MCP OAuth is not the app OAT.
No browser-supplied owner, price, product or return URL selects a purchase. Free
personal setup still requires an active verified owner; training/RM/planning/IA
remain commercial. Expiry preserves owned history and export.

## Affected areas

- Billing domain chooses only current, matching active/trialing subscriptions,
  comparing aware UTC instants, with deterministic ID tie-break. Future/expired
  rows cannot mask an eligible subscription. The earlier `ends_at` also bounds
  active and trial periods before selection; malformed cutoffs fail closed.
  Trial history is monotonic, including
  expired trials. Invalid relevant dates fail closed as controlled provider errors.
- Application writes and reconciliation share the existing account-row lock.
  Mutating authorization retains it in the caller's UoW; presentation preflight
  does not open an independent lock. Global order remains fund→account→billing→quota;
  training retains its account→lineage→prescription→execution order.
- Checkout uses a committed opaque UUID intent, owner/config/product/price/trial/
  period fingerprint and creation/expiry times. Reuse rechecks the product. The
  existing local maximum cache window is30minutes, additionally limited by the
  provider's required expires_at. Old caches without context cannot be reused.
  Context-changing reconciliation invalidates cached links; unchanged polls keep
  them. An ambiguous POST is never automatically repeated. Its intent survives
  rollback/error and requires fresh authoritative reconciliation; unresolved
  inactive intents also retain the finite30minute window before release. This is
  not a guarantee that a payment or a trial occurred, or provider exactly-once.
- refund.updated resolves its documented customer_id through the persisted unique
  customer binding. Organization and returned external ID/customer ID must agree.
  No email fallback. Existing customers cannot silently rebind to another Polar ID.
- Portal requires verified identity and is never cached. Redirects allow explicit
  HTTPS Polar origins for the configured environment, no userinfo/arbitrary ports;
  application return URLs use validated server PUBLIC_URL.

## Implementation steps

### Durable webhook and recovery

`POST /webhooks/polar/` verifies RAW bytes before storage. It commits a unique
receipt, then a traceable reconciliation-pending marker under the common account
lock. It acknowledges queued/unlinked events202 with the same generic response;
unknown kinds complete200. No provider GET happens in the delivery request, so
provider latency does not consume Polar's10second delivery timeout. Invalid
signatures/version/shape return400 without creating a receipt. Bad routes retain404.

The recovery worker invokes the same authoritative cases, not event snapshots:

```sh
python manage.py reconcile_billing --all --watch
```

Compose includes one billing-worker process using that command. Each60second cycle
handles at most25due receipts and25account refreshes, rotating account IDs so a
failed account cannot starve later ones. It polls bound/pending accounts stale by
five minutes to recover missed events. HTTPX connect/pool/read-write timeouts are
2/1/4seconds, without redirects or automatic POST retry. These are per-phase
timeouts, not a claim of a hard wall-clock deadline for an arbitrary HTTP stream.
Receipt retries use exponential delay, at most10automatic attempts per receipt;
unprocessed records are retained and visible, never discarded. Operational use:

```sh
python manage.py reconcile_billing --all
python manage.py reconcile_billing --all --retry-events
python manage.py reconcile_billing --owner-id ACCOUNT_DATABASE_ID
```

`--retry-events` explicitly revisits a bounded batch of exhausted/unlinked records.
Inspect unprocessed/error_code/attempts/retry_at through authorized operations;
recovery output contains counts only, not event payloads, emails or provider URLs.
HTTPX/httpcore request URL logging is disabled at INFO. Pending access is denied
until successful reconciliation. Provider/schema failure keeps its receipt and
pending marker. Concurrent duplicate deliveries can repeat bounded GETs, never
create billing mutations; only one receipt identity is stored. Do not run multiple
watchers as a substitute for a measured provider rate budget.

Supported notifications include customer.state_changed, subscription lifecycle
(including active/past_due/cycled/paused/resumed), order updates/paid/refunded and
refund created/updated. **Only a fresh Customer State GET grants access.** Old paid
events, zero/null invoice fields and browser success queries cannot grant it.
Refunding a subscription order fully or partially does not itself cancel it:
follow current subscription state. This preserves the existing policy rather than
inventing refund-based revocation.

### Explicit configuration, still deferred

Set privately on the server, without copying MCP OAuth credentials:

- POLAR_ACCESS_TOKEN: Sandbox org-specific OAT. Least scopes: products:read,
  customers:read, checkouts:write, customer_sessions:write.
- POLAR_ORGANIZATION_ID: the **new, user-approved** organization; no default existing org.
- POLAR_PRODUCT_ID: its approved monthly product, count1, fixed500cUSD, exclusive
  tax, native trial intervalday/count7. Disallow checkout discount codes.
- POLAR_SANDBOX=1 (already the default).
- POLAR_WEBHOOK_SECRET: Standard secret from the configured endpoint.
- POLAR_WEBHOOK_SECRET_FORMAT=standard. For an explicitly identified pre2026-09-08
  legacy secret only, select legacy: encode the entire whsec string before passing
  it to StandardWebhooks. No silent fallback or weakened second key. Timestamp
  tolerance and signature rotation use the library's verification behavior.
- POLAR_WEBHOOK_API_VERSION=2026-10. Separately configure the **remote endpoint's**
  api_version2026-10/raw format; both webhook-api-version header and payload
  api_version must match. This setting does not migrate an endpoint remotely.
- PUBLIC_URL: approved public HTTPS origin with matching allowed hosts/CSRF/proxy
  settings. HTTP is permitted only for local loopback development. Confirm the
  hostname/tunnel explicitly before enabling actual inbound delivery.

The new organization, OAT, product, webhook endpoint and hostname are unknown and
on hold. Native trial/card collection/conversion must be verified with Polar; a
local product-shaped response does not prove those behaviors.

## Required skills

Planning, safe Git isolation, systematic debugging and verify-before-complete.
No MCP global configuration, tracker updates, calculation skills or delegation.

## Validation

Candidate-specific logs and binding are under `.cache/MAM816_IMPLEMENTATION_REPORT.*`.
New `tests/regression/test_billing_polar.py` exercises real cases with synthetic
data, HTTPX MockTransport, independent HMAC, signatures with full wrong headers,
replay/current-state transitions, scoped refunds, price/trial/cache boundaries,
verified portal, migration preservation and real PostgreSQL serialization in both
directions. The checked-in contract JSON is an explicit projection of the public
2026-10 OpenAPI request properties used here, not a full-schema or LIVE assertion.

Full PostgreSQL tests, pure tests, strict typing, eight import contracts, migration
drift, fresh/upgrade/backup restore and real local browser results must be recorded
as VERIFIED/FAILED/NOT RUN in the report, with exact hashes of the uncommitted files.
Historical CI counts are not reused as this candidate's evidence.

### Independent local review

The original 25-file overlay and all sealed log hashes matched the implementation
report before review. Its 445 PostgreSQL /191 pure tests remain prior-run evidence,
not an independently repeated full suite. Focused PostgreSQL review exercised
refund/customer binding and current-state replay, UTC ordering, stale checkout
contexts and missing expiry, full-header invalid signatures, parent account locks
and both real protected-write/revocation orders, migration preservation, sign-in,
CSRF and production event privacy. A reviewer-authored regression additionally
reproduced and corrected the omitted `ends_at` cutoff. The reviewer does not claim
independent authorship separation for that corrective delta. Hosted CI must run
the resulting exact commit; the added regression increases that suite by one.

## Risks

Sandbox LIVE, tax/card/trial conversion, failed renewal, cancellation and full vs
partial refund delivery remain a separate acceptance gate. Repository delivery and
remote CI receipts are tracked separately and cannot close the LIVE gate. The worker budget is conservative for the
documented100requests/minute Sandbox limit but is not a proof of1000-user capacity.
DB lock waits can outlast a delivery deadline during a long concurrent transaction;
Polar can retry and receipt/pending commits remain durable. A definitive revoked
subscription linearizes under the common lock; time-based access is checked at the
guard, not by inventing a database commit-time clock guarantee.

Existing unfinished receipts from the old schema may lack customer identity;
upgrade preserves them and recovery leaves unresolvable ones pending for explicit
operator reconciliation. Backup/restore and upgrade tests must preserve IDs,
periods, trial history, ownership and existing processed receipts.
