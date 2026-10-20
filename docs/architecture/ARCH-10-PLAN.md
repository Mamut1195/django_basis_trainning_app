# Goal

Accept the final strict typed hexagonal monolith on the integrated ARCH-09 structure, including actual browser/offline workflows, temporary PostgreSQL regression and committed evidence. Close the architecture epic only after all ten deliveries are integrated and independently verified; preserve functional-ticket acceptance states.

# Context

CURRENT: ARCH-09 was reopened after the user/source audit; main337f12d is structural progress only. The amended correction sections below supersede the initial completion assumptions. config is active, test sources are in tests/regression, remaining workflows now enter typed cases, and fresh acceptance/integration is still required. The first paragraph below records the earlier integration snapshot, not current full acceptance.

ARCH-09 independently verified in main/337f12d8d6b78d52c77c3e7e821ab2af1351cdc8, parent24f9853. Actual PostgreSQL logs224/OK/no skips, stopped container,170 committed paths/61 absent retired paths and normalized source hashes checked. Its EOF-only api.py correction is explicit in the receipt; no new PostgreSQL run was claimed. MAM-830 Done. Only unrelated seed.py168/56 and manage.py mode remain. The final seven applications own28 typed models and initial migrations; no legacy runtime or silent model frontiers remain.

# Constraints

No new product feature or silent functional fix. Preserve public URLs, JSON/export-v1, owner/CSRF, Decimal/missing/zero, version history and existing offline queues. Domain/application remain framework-free; all new/migrated Python is strict from this delivery. Do not modify original DBs, user files, credentials, ACLs or Git history. No provider/paid/SMTP/production calls. Browser uses loopback and a unique fresh temporary database; credentials are generated only in process memory/environment and never emitted. Keep evidence and disposable files recoverable. Git/Docker external execution remains necessary when this assistant process lacks access.

# Affected areas

Existing scripts/browser_smoke.py, a typed disposable-browser acceptance launcher, strict scope/inventory/CI integration, final documentation/Linear and deletion-aware explicit verification/integration scripts. Runtime product code stays unchanged unless a demonstrated migration regression requires an explicitly documented correction.

# Implementation steps

1. Browser executor inspects the existing browser/offline script and current templates/JavaScript, then migrates that tool to strict types and implements a repeatable launcher using an owned temporary SQLite DB and loopback Django server. Own scripts/browser_smoke.py and scripts/acceptance_browser.py plus focused launcher tests if needed. Preserve existing responsive/navigation/download/offline-reload/fractional-result/ordered-outbox/completion checks, extend with replay/conflict/owner separation/logout where feasible through real browser/API boundaries. Never simulate successful browser results. Run headless installed Edge/Chromium; retain sanitized logs, screenshots and machine-readable result. Root adds strict scope entries; no product-code edits without reporting a concrete regression.
2. Independent auditor performs read-only final architecture/persistence/core/public/typing/command/admin and baseline-test coverage review against ADR-001/002. Own only docs/architecture/ARCH-10-AUDIT.md and JSON if useful; no code edits or children. Identify blockers precisely rather than inferring functional acceptance from architecture metadata.
3. Primary orchestrates/reviews, owns public/config/CI/inventory/docs/manifest/PowerShell scripts and executes independent aggregate gates. Reconcile ARCH-09 Done and ARCH-10 In Progress in Linear. Run kernel-only tests and typing, full Django regression, final layout/public/import contracts, Ruff, checks/no migration drift/static, plus meaningful browser results. Distinguish physical-device/remote-CI/live-provider evidence from local acceptance.
4. Freeze source manifest and report real counts. External Complete-Arch10 verifies sources, native exit handling, fresh owned Docker PostgreSQL18.4 migrations/all races/no skips, browser acceptance and cleanup; catches whitespace for new files by checking indexed content before committing, including original user files only as exclusions. Scope commit/fast-forward main; preserve tested evidence for a safe exact-state continuation if Git fails.
5. Independently read back main SHA, original logs, receipt, stopped owned processes/container, all source/HEAD hashes and final package/model structure. Only then mark ARCH-10 and epic Done, remove the epic blocking relation from open functional tickets while preserving their existing functional dependencies/states/history, and reconcile project/docs. No physical-device, remote-CI or live-provider acceptance claim without actual evidence.

# Required skills

task-planning, safe-git-workflow, verify-before-complete, systematic-debugging for reproduced failures. Two executors maximum and primary orchestration, as authorized.

# Validation

Use VERIFIED/FAILED/NOT RUN, actual commands/native exit codes, captured stdout/stderr and source hashes. Browser must create real persisted results, preserve reload/outbox semantics and show no uncaught JS errors. Core import tests run -I -S without Django/settings/DB/network. PostgreSQL must run every test without skips on empty final migrations. Verify all positive/deleted manifest paths and original user exclusions. Existing legacy test namespace is unregistered; standalone unchanged tools and protected seed/manage remain explicitly inventoried, never hidden runtime exclusions.

# Risks

Browser binaries/subprocess/network-loopback access may be unavailable; record actual failure and provide a concrete external runner rather than fake proof. Service-worker update/controller timing, IndexedDB state, repeated mutation replay and account switches need real observations. Screenshot storage may contain only generated demo data. Staged/untracked whitespace checks must cover new files; do not repeat the ARCH-09 oversight. Epic closure and unblocking functional work are operational metadata, not acceptance of all35 functional tickets.


## User acceptance correction: final architecture is not yet complete

The user explicitly challenges completion. Independent source inspection confirms that ARCH-09 moved training web code without fully extracting manual session/block/set/interval writes and touch_parent revision/transaction policy. Passing types/import checks and relocated packages does not satisfy the architecture. Reopen MAM-830; its integrated337f12d commit is structural progress, not full architectural completion. Keep ARCH-10 open as the audit/acceptance activity; do not close either on folder names or test counts alone.

Remediation must migrate every remaining training write/guard through typed application commands, concrete ports, pure policy and explicit Django UoW; views only bind/validate framework input, call cases and translate results/errors. Audit all other module entry points for equivalent bypasses. Preserve valid behavior and error/owner/revision/lock precedence. Three implementers maximum: training execution/write remediation; planning/cross-module boundary remediation plus broad audit; browser validation. Primary orchestrates and owns shared/public/config/evidence only. No product feature is added. Existing functional browser defects are reported honestly rather than silently fixed to manufacture acceptance.


## Final configuration package correction

The user explicitly requires config/ and removal of the old named packages. Move Django settings/URLs/ASGI/WSGI from basis_trainning_app to config, update manage.py, deployment, CI, strict settings and active tools. manage.py content now belongs to this delivery and is strictly typed; its pre-existing working-tree mode change remains outside the commit, preserving the original index mode100755 when staging. seed.py remains protected. Old package source files are deletions; compiled caches are not runtime source and require safe explicit cleanup. Final tree: config/ for framework configuration, basis/bootstrap for composition, basis/modules/<area>/{domain,application,adapters}+public.py, basis/shared for pure shared values. Do not leave a compatibility settings package under the old name.


## Documented pre-existing logout defect and resolution

Real Edge run9937f66b1e834eadb57b03febdf840bd completed eight browser checks (including actual offline/reload/two operations/replay/conflict/CSRF), then failed logout: no POST/accounts/logout reached Django and the subsequent authenticated API still returned200. Browser and server both closed. The offline.js bytes exactly match integrated337f12d, so this is a pre-existing functional defect, not a migration regression. Record under MAM-632 before correction. It blocks validating the intended valid logout/account-separation flow.

Approved minimal resolution: reuse the existing BroadcastChannel sender object for logout notification instead of creating a second local sender whose message reaches this tab's listener and redirects before the native CSRF logout POST. Other tabs must still redirect; keep pending export/confirmation, local purge and server logout intact. Browser proof must observe the real logout POST, server unauthenticated redirect, local scope removal and another tab's notification. No assertion is removed and no new feature is added.


## Logout correction refined by real browser evidence

A second real run49583ee5 confirmed that reusing the channel allows POST/logout302 and subsequent API302, but another tab can still navigate before the POST completes and restore the old local scope from authenticated HTML. The first hypothesis was therefore insufficient; keep the failing assertion. Approved correction: await the original same-origin CSRF logout POST through fetch using FormData; after server acknowledgement, purge this account's local state, broadcast through the existing sender and navigate to the response URL. On request failure, retain pending/local data and report failure rather than claiming logout. Other tabs must receive the message only after session invalidation. Verify real network POST, unauthenticated API, local purge, second tab and next-account isolation.

## Final test namespace and strict scope

Relocate remaining training/tests to tests/regression and type the entire moved suite, including its shared factories. No new untyped legacy path or global exclusion is allowed; remove old paths from pending inventory. If tests expose untyped verification-tool imports, migrate scripts/verify_environment.py to strict typing too. This removes the last old training source namespace while preserving every regression scenario. Only compiled caches may remain until explicit safe operator cleanup. Keep baseline inventory immutable.
