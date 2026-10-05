# astra_report_02

**Independent Architecture, Security, and Reliability Audit of Smart Bujet**  
**Audit date:** October 5, 2026 (Asia/Qyzylorda)  
**Reviewed revision:** `28331a87d5f9df8ba47776e37fc52c862f5f849e`  
**Previous assessment:** `astra_report.md`, reviewed revision `d9b7482`  
**Mode:** Read-only investigation; this report is the only repository file created by the audit.

## 1. Assessment and Scope

**The application has improved since the first audit, but material privacy and accounting defects remain.** Several earlier fixes are effective at their individual entry points. They do not yet establish consistent security and financial guarantees across the API, bot, AI processing, family reports, and background jobs.

The most consequential newly identified disclosure is the family advisor's aggregation of other members' personal asset and credit balances. Other confirmed problems include raw-message disclosure through the family feed and mirrored transfers, incorrect balance adjustments when editing transactions, and overpayment rollback that increases debt above its original value. The implementation also continues to depend on non-atomic credit operations and lacks durable incoming-event deduplication.

**SQL injection:** No exploitable path from user input into executable SQL syntax was identified in the reviewed source. ORM predicates use bound values, startup SQL is constant, and the role-provisioning script quotes its password with PostgreSQL `%L`. This does not establish that every deployed dependency or database configuration is secure.

**Prompt injection:** The model is treated as an operation parser with more authority than its output validation justifies. Instructions, user text, account names, and category names share the prompt context; receipt images and audio are also untrusted input. Downstream code accepts financially inconsistent output. No live Gemini adversarial evaluation was performed, so this report does not claim a measured jailbreak success rate.

The review covered authentication, authorization, API routes, bot handlers, services, financial models and schemas, MiniApp rendering, SQL construction, AI inputs and outputs, schedulers, container configuration, migration infrastructure, and tests. Requirements in `AGENTS.md` were treated as authoritative, including personal asset isolation, the initial-balance guard, family transfer conservation, and reservation of host port 443 for MTProto.

### Evidence and limits

- Syntax compilation passed for **81 Python files** under `src`, `scripts`, `tests`, and `migrations`. Compiled output was directed to a temporary directory outside the repository.
- `node --check src/static/app.js` passed.
- `python -B -m unittest discover -s tests -p 'test_*.py' -v` reported **34 test entries: 11 OK, 22 skipped, and 1 module-import error**. The import error was missing SQLAlchemy in `test_photo_batch`; the environment also lacked FastAPI, aiogram, asyncpg, pytest, and other application dependencies. This is not a successful full-suite run.
- Isolated checks executed actual functions/classes extracted from the source using Python's AST, with database access and external services replaced by test doubles. These establish the observed function behavior, not PostgreSQL locking, HTTP serialization, or production exploitability. Financial branches and comparisons were unchanged; framework decorators, annotations/default evaluation dependencies, ORM entities, and sessions were isolated as necessary.
- Application startup, the operational privacy script, production APIs, Telegram delivery, the live database, and Gemini requests were not executed. The operational privacy script reads actual user financial data and may provision a family; it is unsuitable as a read-only audit test against an unknown database.
- No packages were installed. Actual `.env` contents and production secrets were not read. No dependency inventory, image SBOM, live TLS scan, load test, or database execution plan was available.
- HEAD remained at the revision above. SHA-256 checks of **93 reviewed tracked files** matched the audit checkpoint after the interrupted audit resumed. No application or configuration edits were made.

Priorities: **P1** means resolve before broader use because of financial corruption, privacy exposure, authentication compromise, or lost operations. **P2** means significant reliability, hardening, or maintainability work. **Conditional** identifies an additional deployment or input precondition; it does not mean that precondition was observed in production. No confirmed unauthenticated production compromise or remote code execution is claimed.

## 2. What Improved Since the First Audit

| Previous finding | Current assessment | Evidence |
|---|---|---|
| A01: Family-screen stored XSS | The previously identified member, title, author, and category sinks now escape those values. No replacement browser-XSS exploit was confirmed in this review. | `src/static/app.js:241,1369,1417` |
| A02: Generic transaction API bypassed masking | Fixed for ordinary non-owner rows returned through that API. Other disclosure paths remain; see B02 and B03. | `src/api/v1/transactions.py:42`; `transaction_service.py:1153` |
| A03: Manual creation lacked validation | Initial balance, category ownership/type, and positive amount checks were added. Special-operation consistency is still missing; see B09. | `transaction_service.py:1196`; `schemas/transaction.py:7` |
| A04: MiniApp repayment omitted cash expense | The API now creates a repayment expense and commits it with the debt update. Bot credit processing still commits prematurely; overpayment remains incorrect. | `src/api/v1/credits.py:77-122`; B04, B10 |
| A05: Concurrent financial updates | Still open. Locks exist on deletion and the MiniApp repayment path, not consistently across all writers. | B06 |
| A06: Repeated delivery | Still open. A report-log uniqueness constraint is not incoming-update deduplication. | B07 |
| A07: Editing linked amounts | Still open; the three previous arithmetic failures were reproduced against the current functions. | B05 |
| A08: Toggle breaks linked operations | The handler now rejects transactions linked to a mirror, asset, or credit before toggling. | `src/bot/handlers/tx_actions.py:46` |
| A09: Mixed currencies | Still open, including in the new advisor. | B11 |
| A10: Double subtraction of family income | The second subtraction was removed. An unnecessary query for internal income remains. | `src/services/family_service.py:123-137` |
| A11: Lazy-loading failures in manual creation/toggle | The previously cited paths now attach the category explicitly or eager-load it. Full HTTP/ORM behavior remains unverified locally. | `transaction_service.py:1248`; `tx_actions.py:32` |
| A12: Webhook mode and port 8443 | Still open. | B12 |
| Docker build could include `.env` | `.dockerignore` now excludes `.env`, `.env.*`, and `.git`. The original build-context defect is addressed at source level. | `.dockerignore:1-4` |
| Empty webhook secret bypassed verification | The webhook now rejects an empty configured secret and uses constant-time comparison. API authentication still permits an empty bot-token key. | `src/api/v1/webhook.py:14`; B01 |
| Read-only DB role used a fallback password | New-role creation now requires a supplied password and quotes it safely. Existing roles are not rotated; broad grants remain. | `scripts/init_db_roles.sql:3-17` |
| Receipt normalization dropped dining metadata | `establishment_type` and `venue_name` are preserved. | `src/services/ai_service.py:66-69` |

These are source-level remediation assessments, not a certification of the running deployment. The modular monolith remains appropriate for the application's size; a microservice rewrite would not solve the defects below.

## 3. Priority Findings

### B01. P1, conditional — Missing or known test bot tokens permit API impersonation

**Evidence:** [configuration](C:/Users/aanto/smart-bujet/src/core/config.py:7), [signature validation](C:/Users/aanto/smart-bujet/src/core/security.py:25), [API authentication](C:/Users/aanto/smart-bujet/src/api/deps.py:14), [fallback bot token](C:/Users/aanto/smart-bujet/src/bot/bot.py:12), [startup checks](C:/Users/aanto/smart-bujet/src/main.py:44).

`BOT_TOKEN` defaults to an empty string. The API passes this value directly to the HMAC validator. Bot initialization substitutes a known dummy token for missing/invalid values, while startup merely avoids Telegram setup for certain test tokens; it does not refuse to serve the API.

**Reproduction:** Using the actual validator, a locally constructed `initData` payload signed with the empty key was accepted when `bot_token=""`. The repository's known dummy token also produced accepted signatures when configured as the API key. The payload can choose an arbitrary user ID. With a valid configured database and an exposed API, this permits impersonating an existing user or creating a chosen identity.

The precondition is a missing or publicly known bot-token configuration. It was not checked on the production server. With a correctly configured secret, the local tampered-signature control was rejected.

**Remediation:** Fail startup in production unless required secrets are nonempty and valid, reject known development values, and make development mode explicit. Use one validated bot identity for both bot initialization and API authentication. Do not silently substitute production credentials.

The validator also accepts correctly signed future timestamps and permits replay for 24 hours. A future timestamp does **not** bypass HMAC on its own. Define an acceptable clock-skew window and an explicit session lifetime; consider short-lived application sessions and revocation. Telegram documents HMAC verification and checking `auth_date` in its [Mini Apps validation guidance](https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app).

### B02. P1 — Family advisor discloses personal asset and credit balances

**Evidence:** [family summary callback](C:/Users/aanto/smart-bujet/src/bot/handlers/summary.py:206), [family member selection](C:/Users/aanto/smart-bujet/src/services/report_service.py:336), [asset/debt aggregation](C:/Users/aanto/smart-bujet/src/services/report_service.py:407), [summary rendering](C:/Users/aanto/smart-bujet/src/bot/messages.py:289), [AI payload](C:/Users/aanto/smart-bujet/src/services/ai_service.py:348).

Family analytics builds `target_user_ids` from every current member. It then sums `AssetAccount.balance` and `CreditAccount.remaining_amount` for those IDs. The bot displays both totals and sends them to Gemini for advice. Owner scoping in the standalone assets and credits APIs does not protect this separate path.

**Impact:** In a two-person family, a member can subtract their own known asset balance from the family total to learn the partner's private balance. The same inference applies to debt. This violates the explicit personal-asset isolation requirement even without returning individual account objects or names. Credit APIs themselves also describe credits as personal and isolated from family.

**Evidence level:** The cross-member aggregation and delivery path are confirmed in source. An isolated formatter check confirmed that supplied family asset/debt totals are included in the outgoing message. No real family data was accessed.

**Remediation:** Keep private asset/debt metrics scoped to the requesting owner in every service, including reports and AI context. If shared balance reporting is desired, introduce explicit consent and a separate shareable data model. Test two-user inference, not merely whether account IDs overlap.

### B03. P1 — Raw-message privacy remains bypassable through two independent paths

**Evidence:** [family feed](C:/Users/aanto/smart-bujet/src/services/family_service.py:188), [generic masking](C:/Users/aanto/smart-bujet/src/services/transaction_service.py:1158), [mirror creation](C:/Users/aanto/smart-bujet/src/services/transaction_service.py:155), [raw text persistence](C:/Users/aanto/smart-bujet/src/services/transaction_service.py:445).

1. `FamilyService.get_family_transactions()` still uses its own masking implementation. It suppresses `raw_text` only for a row classified as a deposit operation. A normal purchase row retains the entire original mixed-operation message, including private deposit names mentioned elsewhere in that message.
2. `_handle_intra_family_mirror()` copies the sender's entire message into the recipient's mirror transaction. The recipient owns that row, so even the corrected generic masking function returns its `raw_text`. Hiding all non-owner raw text alone cannot close this second path.

**Reproduction:** A grocery row containing a mixed message with the dummy private name `Secret reserve` returned that raw text through the family-feed function, while the generic non-owner mask returned `None`. A second isolated check created a family mirror and confirmed that the recipient-owner mask returned the sender's full mixed message, including the same private name.

**Remediation:** Apply one viewer-aware presentation policy to all feeds and reports. Preserve original message provenance separately from transaction ownership. Mirror records should contain only the minimum transfer description, never a copied multi-operation source message. Include mixed text/voice messages and recipient-owned mirror records in privacy regressions.

### B04. P1 — Nested credit commits break operation atomicity

**Evidence:** [credit creation/repayment](C:/Users/aanto/smart-bujet/src/services/credit_service.py:92), [text orchestration](C:/Users/aanto/smart-bujet/src/services/transaction_service.py:387), [voice orchestration](C:/Users/aanto/smart-bujet/src/services/transaction_service.py:549).

`CreditService.create_credit()` and `repay_credit()` commit the shared session themselves. Their caller subsequently constructs ledger rows and processes more items before its final commit. A failure after the inner commit can leave a changed debt or newly created loan without its corresponding ledger operation. An inner commit can also persist earlier pending items in the same message.

**Reproduction:** The actual repayment function, run with a recording session double, committed once and created zero ledger entries before returning to its caller. The wider failure path follows directly from the caller's subsequent work. This was not a database rollback integration test.

**Remediation:** Give a single operation coordinator ownership of the transaction boundary. Nested services may mutate and flush, but must not independently commit. Inject a failure after loan mutation and during the second item of a batch; all financial effects must roll back together.

### B05. P1 — Editing linked amounts still corrupts balances

**Evidence:** [transaction update logic](C:/Users/aanto/smart-bujet/src/services/transaction_service.py:992).

The following results were reproduced by executing the current update function against isolated entities:

| Operation | Expected | Observed |
|---|---|---|
| Change a 50,000 KZT / 100 USD asset transfer to 55,000 KZT, exchange factor 0.002, asset balance initially 100 USD | Asset balance and linked amount become 110 USD | Asset balance becomes **5,100**; `asset_amount` becomes 110 |
| Change capitalized interest from 10 to 20, deposit balance initially 1,010 | Deposit balance becomes 1,020 | Balance stays **1,010**, while the transaction becomes 20 |
| Change a loan receipt from 1,000 to 2,000 before any repayments | Reject or consistently change the loan principal and outstanding balance | Ledger becomes 2,000; debt remains **1,000** |

The asset branch applies the difference in the cash amount directly to the asset balance before separately converting `asset_amount`. It has no capitalized-income balance branch. Credit reconciliation handles expenses only.

**Remediation:** Define edit semantics by operation kind and reconcile the complete operation atomically. Use the difference between old and new asset-denominated effects for FX edits. Reject unsupported principal or accrued-interest edits until the correct reversal/reapplication logic exists. Verify edit-then-delete conservation as well as the immediate response.

### B06. P1 — Concurrent writes and interest accrual are not consistently protected

**Evidence:** [asset deposits/withdrawals](C:/Users/aanto/smart-bujet/src/services/asset_service.py:195), [AI asset mutation](C:/Users/aanto/smart-bujet/src/services/transaction_service.py:280), [bot repayment](C:/Users/aanto/smart-bujet/src/services/credit_service.py:107), [updates](C:/Users/aanto/smart-bujet/src/services/transaction_service.py:940), [accrual check](C:/Users/aanto/smart-bujet/src/services/asset_service.py:333), [transaction model](C:/Users/aanto/smart-bujet/src/models/transaction.py:30).

These paths read balances or amounts, calculate new values, and write them without a consistent row-lock or optimistic-version protocol. The lock in the MiniApp repayment endpoint does not protect concurrent writers that already read the same credit without that protocol.

**Failure scenario:** Two deposits read 100; one adds 10 and the other adds 20. Both ledger rows can persist while the stored balance ends at 110 or 120 instead of 130. Concurrent mirror edits can similarly diverge or overwrite each other.

Interest accrual checks for an existing transaction and then inserts one. There is no unique account/period accrual key, so concurrent workers or manual triggers can both pass the check. The description “strict idempotency” is unsupported by the database model.

Deletion does use locks, but acquires a primary transaction and then its mirror. Concurrent deletion of opposite sides can acquire the pair in opposite orders and deadlock.

**Remediation:** Use one concurrency protocol across every writer, lock related rows in a deterministic order, enforce durable operation/accrual uniqueness, and retry only retryable failures with preserved idempotency. PostgreSQL recommends a consistent lock acquisition order to avoid deadlocks in its [locking documentation](https://www.postgresql.org/docs/16/explicit-locking.html). Verify interleavings on PostgreSQL; mock or SQLite tests do not establish these guarantees. The scenarios above are source-derived, not measured production races.

### B07. P1 — Incoming events and manual mutations lack durable idempotency

**Evidence:** [webhook dispatch](C:/Users/aanto/smart-bujet/src/api/v1/webhook.py:20), [transaction model](C:/Users/aanto/smart-bujet/src/models/transaction.py:30), [creation commit](C:/Users/aanto/smart-bujet/src/services/transaction_service.py:459), [reply after persistence](C:/Users/aanto/smart-bujet/src/bot/handlers/text_tx.py:63).

No persisted unique incoming `update_id`, message-operation key, or API idempotency key was found. A commit followed by a network failure or failed confirmation leaves the sender uncertain. Reprocessing the same content creates new financial effects. Telegram explicitly documents retries after unsuccessful webhook responses in the [Bot API](https://core.telegram.org/bots/api#setwebhook).

The application dispatches webhook work directly; it has no durable inbox separating accepted delivery from financial processing. In-memory album grouping does not survive process termination and is not a substitute for deduplication.

**Remediation:** Persist accepted events with unique keys and processing states; commit the financial result against that key. Return the original result for repeated requests. Add idempotency keys to manual mutations. Separate financial completion from delivery of its confirmation so failed replies do not require repeating the operation.

### B08. P1 — AI output can directly apply inconsistent financial operations

**Evidence:** [prompt construction](C:/Users/aanto/smart-bujet/src/services/ai_service.py:128), [normalization](C:/Users/aanto/smart-bujet/src/services/ai_service.py:18), [credit/asset dispatch](C:/Users/aanto/smart-bujet/src/services/transaction_service.py:387), [asset delta](C:/Users/aanto/smart-bujet/src/services/transaction_service.py:280), [receipt transaction building](C:/Users/aanto/smart-bujet/src/services/transaction_service.py:674), [asset resolution fallback](C:/Users/aanto/smart-bujet/src/services/asset_service.py:108).

The Gemini configuration requests JSON MIME output but supplies no response schema. Normalization accepts arbitrary item dictionaries and largely preserves their fields. Only the literal Boolean `false` rejects nonfinancial content; a string `"false"` becomes an accepted financial payload. There is no comprehensive finite-number, maximum-value, item-count, operation-type/category, credit-action/type, or FX-consistency validation before mutation.

**Confirmed examples:**

- An item with positive cash amount and `asset_amount=-50` survives normalization. The actual transfer-out helper reduced a dummy asset balance from 100 to **50**, even though transfer-out represents funding that asset.
- JSON containing `NaN` survives Python JSON normalization; downstream arithmetic is not designed to handle it safely.
- Receipt transaction building accepts an item-supplied operation type rather than enforcing receipt-only expense semantics, and does not create asset effects for a receipt classified as a transfer.
- Ambiguous deposit matching can select the first active deposit; an unmatched name with one active credit can select that credit. UUID/name matches do not consistently establish compatibility with the requested currency/type.

The attacker-controlled surfaces include receipt content, spoken/text instructions, and stored account/category names interpolated into prompts. Family category names also enter advisor prompts. A malicious user changing their own ledger is not, by itself, privilege escalation; the security concern is untrusted content changing the interpretation of another intended operation or a shared report, and model output crossing into privileged financial code without invariant checks.

**Remediation:** Parse into a strict, bounded operation schema, then enforce business rules independently of the model. Treat target IDs as suggestions that require owner and currency/type checks. Reject inconsistent combinations and ambiguous targets. Use separated instruction/data channels, structured output where supported, and a review step for uncertain transfers or credit changes. Prompt wording alone cannot provide authorization. These controls follow [OWASP's prompt-injection guidance](https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html); Gemini documents [structured output](https://ai.google.dev/gemini-api/docs/structured-output), which still needs application-specific validation.

**Limits:** No live model jailbreak was attempted. The model has no exposed arbitrary SQL, shell, or network tools in this code. Asset and credit resolution starts from owner-scoped lists, which limits the direct cross-user blast radius. No route from a prompt to arbitrary server-secret extraction was established.

### B09. P1 — Financial invariants still depend on the entry point

**Evidence:** [manual creation](C:/Users/aanto/smart-bujet/src/services/transaction_service.py:1196), [asset endpoints](C:/Users/aanto/smart-bujet/src/api/v1/assets.py:91), [repayment endpoint](C:/Users/aanto/smart-bujet/src/api/v1/credits.py:63).

Manual creation validates category ownership and type but accepts `transfer_out`/`transfer_in` without an asset target or a corresponding asset balance change. It also permits special credit categories without credit effects and family-transfer categories without invoking mirror creation.

Separately, asset funding/withdrawal and credit repayment do not enforce `User.initial_balance`. The bot's message guards and the manual transaction guard therefore do not implement the repository's universal onboarding requirement.

**Reproduction:** The manual creation function committed a `transfer_out` row with no `asset_account_id`. The actual API repayment function accepted a user with `initial_balance=None` and committed an expense and debt update in the isolated check.

**Remediation:** Route financial entry points through one operation service. Until specialized requests are implemented, reject unsupported special operation types/categories in generic creation. Apply the initial-balance requirement in the shared spending/transfer operation layer, not only handlers. Distinguish importing an opening asset/debt balance from recording a new cash movement.

### B10. P1 — Credit overpayment is silently clamped and cannot be reversed correctly

**Evidence:** [MiniApp repayment](C:/Users/aanto/smart-bujet/src/api/v1/credits.py:90), [bot repayment](C:/Users/aanto/smart-bujet/src/services/credit_service.py:111), [deletion reversal](C:/Users/aanto/smart-bujet/src/services/transaction_service.py:1107).

Both repayment implementations clamp remaining debt at zero. The ledger nevertheless records the entire payment. Deletion later restores the entire ledger amount to debt, rather than the amount actually applied to principal.

**Reproduction:** Starting debt 100, payment 150: debt becomes 0 and the expense is 150. Deleting that expense through the actual deletion function restores debt to **150**, not 100. The API also does not reject repayment of an already closed credit.

**Remediation:** Reject principal overpayment or model principal, interest, fees, and excess credit explicitly. Store the exact liability effect separately if it differs from the cash payment. Every accepted repayment must have a well-defined inverse. The lock and atomic API commit are useful but do not correct this business rule.

### B11. P1 — Currency identity is missing from ledger operations and aggregates

**Evidence:** [transaction model](C:/Users/aanto/smart-bujet/src/models/transaction.py:37), [currency change](C:/Users/aanto/smart-bujet/src/bot/handlers/start.py:163), [manual asset funding](C:/Users/aanto/smart-bujet/src/services/asset_service.py:199), [portfolio rates](C:/Users/aanto/smart-bujet/src/services/asset_service.py:265), [family totals](C:/Users/aanto/smart-bujet/src/services/family_service.py:77), [advisor totals](C:/Users/aanto/smart-bujet/src/services/report_service.py:407).

Transactions do not persist their cash currency. Changing the profile currency reinterprets history without conversion. Manual funding of a foreign-currency asset applies the same numerical amount to cash and the asset. Family balances, credit summaries, and advisor asset/debt metrics sum amounts across currencies without conversion. Advisor asset aggregation also labels all active asset types as deposits/savings.

The portfolio's separate fixed conversion table has no effective date; unknown currencies fall back to a factor of 1. The advisor ignores even that approximate conversion.

**Impact:** Net worth, cash balance, savings, and debt burden can be materially false while displaying a plausible currency label. AI advice inherits the incorrect aggregates.

**Remediation:** Persist original currency/amount and the cash/asset effects with their rate and valuation date. Separate display currency from accounting denomination. Aggregate per currency or convert explicitly to an identified reporting currency. Reject unsupported currencies rather than guessing a rate. Treat existing historical records as a migration and reconciliation problem, not simply a new column default.

### B12. P1 — Delivery-mode selection remains incompatible with the prescribed public port

**Evidence:** [webhook URL](C:/Users/aanto/smart-bujet/src/core/config.py:47), [startup delivery selection](C:/Users/aanto/smart-bujet/src/main.py:88), [proxy configuration](C:/Users/aanto/smart-bujet/Caddyfile:1), [host mappings](C:/Users/aanto/smart-bujet/docker-compose.yml:6).

The startup condition chooses webhook mode only when `WEBHOOK_DOMAIN` has no colon. Without a port, `webhook_url` targets implicit HTTPS port 443, which the project reserves for MTProto. Supplying `:8443` instead selects polling and calls `delete_webhook(drop_pending_updates=True)`, discarding queued updates.

MiniApp URL construction has separate rules that append 8443 for some hosts, so a working MiniApp URL does not demonstrate correct webhook delivery.

**Remediation:** Configure polling/webhook mode explicitly, validate a complete public URL, and use the same canonical origin for MiniApp and webhook routing. Preserve pending updates during routine startup. Test restart with queued updates and assert the actual Telegram webhook URL.

The `8443:443` container mapping is correct and does not occupy host port 443. Keep that reservation intact. The `:80` catch-all can serve the backend for unmatched hosts; Caddy may insert automatic redirects for the configured hostname, and those redirects also need verification against the external 8443 topology. Do not assume every HTTP request behaves identically. See [Caddy's automatic HTTPS routing rules](https://caddyserver.com/docs/automatic-https). Live routing/TLS was not tested.

## 4. Additional Security and Reliability Findings

### C01. P2 — Unescaped Telegram HTML enables content injection and failed confirmations

**Evidence:** [HTML parse mode](C:/Users/aanto/smart-bujet/src/bot/bot.py:23), [transaction messages](C:/Users/aanto/smart-bujet/src/bot/messages.py:69), [receipt titles](C:/Users/aanto/smart-bujet/src/bot/messages.py:127), [advisor rendering](C:/Users/aanto/smart-bujet/src/bot/messages.py:279), [family notifications](C:/Users/aanto/smart-bujet/src/api/v1/family.py:53).

Names, categories, transaction descriptions, receipt titles, and AI advice are inserted directly into HTML-formatted Telegram messages. A formatter check retained a dummy `<a href="https://example.invalid/audit">` link verbatim. A malicious shared category or family member name can change the apparent message content or introduce a link. Unsupported tags or unmatched markup can cause Telegram to reject a message after its financial operation has committed, encouraging a duplicate retry.

This is Telegram content/link injection, **not browser JavaScript execution**. Telegram documents its restricted formatting and link behavior in [formatting options](https://core.telegram.org/bots/api#formatting-options).

Escape every data value with an HTML-aware encoder or use explicit message entities. Bound and split outgoing content to supported lengths; validate advisor field types and lengths. Keep error messages distinguishable between “operation failed” and “saved, confirmation failed.”

### C02. P2 — Report-log uniqueness does not guarantee exactly-once delivery

**Evidence:** [broadcast loop](C:/Users/aanto/smart-bujet/src/core/report_scheduler.py:89), [send before log](C:/Users/aanto/smart-bujet/src/core/report_scheduler.py:123), [unique constraint](C:/Users/aanto/smart-bujet/src/models/report_log.py:26), [manual report script](C:/Users/aanto/smart-bujet/scripts/run_reports.py:13).

Two workers can both see no log, both send, and only then compete to insert the unique log. A crash after sending and before commit also permits another send. The database constraint protects log rows, not Telegram side effects. Every API process starts its own scheduler.

All existing log statuses are treated as already sent, including `failed`; those failures are never retried within the period. Reports are only selected during the 19:00 hour, with no durable catch-up after downtime. `scripts/run_reports.py` bypasses the report log entirely. The configured time zone is obtained through an attribute not defined on `Settings`, so there is no ordinary declared environment setting for it.

Introduce durable job claiming, explicit status/retry transitions, and a controlled scheduler topology. State delivery semantics honestly: an external send and a database commit cannot become exactly-once merely through a local unique constraint. Handle uncertain delivery outcomes deliberately.

### C03. P2 — Receipt albums can be stranded or only partly recorded without a failure summary

**Evidence:** [album buffer](C:/Users/aanto/smart-bujet/src/bot/handlers/photo_tx.py:30), [batch result](C:/Users/aanto/smart-bujet/src/services/transaction_service.py:787), [batch reply](C:/Users/aanto/smart-bujet/src/bot/handlers/photo_tx.py:122).

The debounce leader has no cancellation cleanup. In an isolated execution, cancelling the leader left its group in memory; the next invocation appended a message and returned `None`, leaving no task to process that retained group. Multiple processes or late-arriving messages can also split an album because coordination exists only in one process and ends at the debounce cutoff.

Batch parsing intentionally skips failed/off-topic receipts and commits successful ones. It returns `failed_count`, but the bot ignores that field. The database commit is atomic for the selected successful rows; the album is **not** all-or-nothing recognition of every submitted image.

Add cancellation cleanup and bounded buffer lifetime, durable correlation/deduplication if multiple workers are supported, and explicit per-receipt results. A user retry must target only failed receipts. The single commit does not justify the documentation's claim of zero split responses or zero races.

### C04. P2 — No application-level budgets protect expensive processing

**Evidence:** [voice download](C:/Users/aanto/smart-bujet/src/bot/handlers/voice_tx.py:19), [parallel photo downloads](C:/Users/aanto/smart-bujet/src/bot/handlers/photo_tx.py:82), [parallel AI calls](C:/Users/aanto/smart-bujet/src/services/transaction_service.py:775), [advisor callback](C:/Users/aanto/smart-bujet/src/bot/handlers/summary.py:173), [container limits](C:/Users/aanto/smart-bujet/docker-compose.yml:44).

No explicit per-user request/AI quota, global AI semaphore, receipt-item bound, application media-size/duration cap, or job deadline was found. Telegram/provider limits are not a budget for this application's 240 MB backend. Multiple albums and repeated advisor callbacks can multiply in-memory bytes, concurrent requests, database occupancy, and paid AI usage. Voice downloads precede the initial-balance guard; photo downloads now follow it.

Check identity/onboarding and media metadata early. Bound download size, duration, total batch bytes, concurrency, model output, and user spend. Use timeouts/cancellation and short-lived queues; return clear overload responses. Resource limits alone turn overload into process termination.

### C05. P2 — Numeric and text schemas do not match persistence constraints

**Evidence:** [asset request schemas](C:/Users/aanto/smart-bujet/src/api/v1/assets.py:15), [transaction schemas](C:/Users/aanto/smart-bujet/src/schemas/transaction.py:7), [category schema](C:/Users/aanto/smart-bujet/src/schemas/category.py:3), [alias width](C:/Users/aanto/smart-bujet/src/models/alias.py:20), [financial columns](C:/Users/aanto/smart-bujet/src/models/transaction.py:37).

The actual asset-action schema accepted the JSON-compatible string `"NaN"` as floating-point NaN, which bypasses `amount <= 0`. Asset creation accepted a negative opening balance and negative interest rate. Transaction creation accepted `0.001`, despite two-decimal storage; database rounding can turn a positive accepted amount into zero. Bounds do not consistently match `Numeric` precision, account/category name widths, or the 128-character alias field. Category type is a free string converted to an enum inside the endpoint rather than a validated request enum.

Use finite `Decimal` values with explicit precision, scale, and range. Decide whether sub-minor-unit amounts are rejected or rounded before validation. Enforce operation-specific nonnegative constraints, supported currencies, and maximum text lengths. Add database checks as a final layer. A malformed value should produce a validation response, not fail during commit or poison a balance. NaN persistence/serialization behavior was not tested against PostgreSQL.

### C06. P2 — Family membership and invitation lifecycle are underspecified

**Evidence:** [invitation display](C:/Users/aanto/smart-bujet/src/services/family_service.py:144), [join](C:/Users/aanto/smart-bujet/src/services/family_service.py:227), [leave](C:/Users/aanto/smart-bujet/src/services/family_service.py:267), [feed selection](C:/Users/aanto/smart-bujet/src/services/family_service.py:170).

Hiding an invitation when a family becomes active does not revoke its code. Anyone holding it can still join; there is no expiry, owner approval, member cap, or revocation API. The code is cryptographically random, so this is a token-lifecycle issue, not a demonstrated guessing weakness.

Feed selection combines transactions tagged with the family and every transaction owned by current members. This imports pre-membership history, including transactions tagged with another family, while old tagged records can remain visible to the former family. Other APIs use different predicates. Leaving does not reassign ownership or rotate the invitation when the owner departs. Concurrent family auto-provisioning is not serialized.

Define whether sharing is historical or prospective, what departure revokes, who can invite, and whether more than two members are supported. Enforce that policy consistently and test join/leave/rejoin transitions. For multi-member families, selecting the first other member as the transfer recipient is insufficient.

### C07. P2, conditional — Bot financial replies are not restricted to private chats

**Evidence:** [message routes](C:/Users/aanto/smart-bujet/src/bot/handlers/text_tx.py:34), [summary callbacks](C:/Users/aanto/smart-bujet/src/bot/handlers/summary.py:116), [router registration](C:/Users/aanto/smart-bujet/src/bot/bot.py:28).

No global private-chat filter or destination authorization was found. Handlers identify the account by `from_user.id` but send or edit messages in the originating chat, including balances and summaries. If the bot is admitted to groups and receives these commands/callbacks, financial information can be displayed to the group. Existing buttons can cause the clicker's own information to be written into a shared message.

This depends on Telegram bot/group configuration, which was not inspected. Enforce private-chat handling for sensitive workflows or explicitly validate a supported destination. Do not rely on Telegram privacy mode as an authorization policy.

### C08. P2 — Accrual and report period semantics are inconsistent

**Evidence:** [accrual timing](C:/Users/aanto/smart-bujet/src/core/accrual_scheduler.py:39), [manual trigger](C:/Users/aanto/smart-bujet/src/api/v1/assets.py:145), [period bounds](C:/Users/aanto/smart-bujet/src/services/report_service.py:297), [category period](C:/Users/aanto/smart-bujet/src/services/report_service.py:150), [legacy summary](C:/Users/aanto/smart-bujet/src/services/report_service.py:86).

Accrual runs on the last UTC day, has no missed-period recovery, and can be invoked manually before month end. The calculation uses the current balance for a full monthly rate without a documented balance-history/proration rule. This can be an intentional estimate, but should not be presented as an authoritative bank accrual.

Reports mix rolling 7/30/365-day windows with calendar periods. `get_category_breakdown(period="year")` still selects only the current month. Scheduled weekly bounds inherit the supplied local timezone, while month/year starts are constructed in UTC. The advisor scales year-to-date totals by 12 even before year end, and month-to-date figures are used as monthly expenditure without accounting for elapsed days.

Define accounting timezone, closed-period cutoffs, catch-up behavior, and whether advice uses completed periods or prorated estimates. Share the same period and membership policies across screens and bot reports.

### C09. P2 — Deployment and dependency controls are incomplete or unverified

**Evidence:** [dependency declarations](C:/Users/aanto/smart-bujet/pyproject.toml:6), [image build](C:/Users/aanto/smart-bujet/Dockerfile:1), [startup DDL](C:/Users/aanto/smart-bujet/src/main.py:25), [DB role grants](C:/Users/aanto/smart-bujet/scripts/init_db_roles.sql:9).

- Dependencies and base images are not pinned to a resolved version set/digests; no lockfile or deployed inventory was found. A new build can change transitive dependencies without a code change. **No specific CVE is asserted:** installed production versions were unavailable, and scanning a newly resolved set would not establish the deployed state. Produce an SBOM and run an advisory check against the actual locked/deployed environment, using a tool such as [PyPA pip-audit](https://github.com/pypa/pip-audit).
- The application performs table creation and ad hoc alterations at startup. No Alembic revision files were present. Existing schemas are not automatically reconciled to all model constraints by `create_all`. Separate versioned migrations from runtime access and use a non-DDL application role.
- The backend image has no non-root `USER`; Compose mounts source read-write. No explicit read-only root filesystem, capability drop, or `no-new-privileges` setting is present. These are containment gaps, not evidence of a container escape.
- The read-only role receives all current and future table contents, including raw messages, aliases, feedback, financial balances, and invite codes. Restrict analytics access to necessary views/columns. The script only sets a password when creating the role: running the fixed script does not rotate a previously created role's old password or revoke existing grants.
- No repository evidence established backup restoration testing, readiness/liveness checks, encrypted database transport, dependency scanning in CI, or alerting. The architecture references `.github/workflows/deploy.yml`, but that file/directory is absent from this snapshot. These controls may exist outside the repository and require operator verification.
- The reviewed web configuration has no explicit CSP or security-header policy. Add a Telegram-compatible policy after testing supported embedding contexts; do not blindly block the MiniApp's required parent frames or SDK. Verify the actual external HTTPS origin and redirect behavior on port 8443.

### C10. P2 — The tests and documentation overstate current guarantees

**Evidence:** [scheduler tests](C:/Users/aanto/smart-bujet/tests/test_report_scheduler.py:8), [accrual test](C:/Users/aanto/smart-bujet/tests/test_accrual_scheduler.py:5), [guardrail tests](C:/Users/aanto/smart-bujet/tests/test_guardrails.py:23), [privacy script](C:/Users/aanto/smart-bujet/scripts/verify_privacy_and_isolation.py:7), [architecture claims](C:/Users/aanto/smart-bujet/ARCHITECTURE.md:546).

Calendar/report tests copy production logic into the test file rather than importing the actual functions. The rule-based advice test silently passes on `ImportError`. Other tests skip missing dependencies, and the photo tests fail to import in this environment. Mock guardrail tests verify that supplied `is_financial=False` is handled; they do not test adversarial model behavior or inconsistent financial output.

The privacy script checks specific real user IDs and account-list separation, not all response paths. It can expose data in logs and invoke family provisioning. The documented script name also differs from the actual filename.

Claims of universal masking, strict exactly-once broadcasts, comprehensive pessimistic locking, and zero album races are contradicted by the reviewed paths. `get_agent_analytics()` uses several aggregate queries, not a single overall database pass.

Replace guarantees in documentation with verified invariants and explicit delivery semantics. Require dependencies in CI and fail instead of silently skipping security/financial coverage. Add isolated PostgreSQL integration fixtures and API/bot contract tests. Source-level comments and successful mocked tests are not sufficient evidence of architectural correctness.

## 5. Injection and Access-Control Coverage

| Surface | Assessment and remaining boundary |
|---|---|
| SQL injection | No unsafe user-controlled SQL construction found. ORM comparisons and `ilike` values are bound. `%`/`_` in category names can alter wildcard matching, which is a matching bug rather than SQL execution. Prefer exact normalized equality where an exact category is intended. Parameter binding is the appropriate primary defense described by [OWASP](https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html). |
| Direct/indirect prompt injection | Boundary weakness confirmed; live model attack success unmeasured. Treat audio, OCR content, stored names, category names, and model output as untrusted. `sanitize_poisoned_aliases()` deletes certain historical misclassifications; it is not a general prompt-injection defense. No public mutation path for the global few-shot catalog was found. |
| Browser XSS | Previously reported family sinks now escape data. Other HTML/SVG interpolations reviewed include numeric values, UUIDs, and server-selected chart metadata. No concrete new executable payload path was established. Prefer text nodes and explicit attribute validation to preserve that property as the API evolves. Browser execution was not tested. |
| Telegram HTML injection | Confirmed unescaped data-to-markup path; C01. This has a different execution model from browser XSS. |
| Object authorization | Asset/credit lookups generally check ownership; transaction edits/deletes reject a non-owner; manual category isolation improved. Cross-member privacy failures remain in reports and raw-message provenance. Some lookups disclose existence through differing 403/404 responses; UUIDs reduce enumeration practicality, but uniform owner-scoped queries are preferable. |
| Authentication/webhook forgery | HMAC and constant-time comparison are present. Webhook secret validation is now fail-closed. Empty/known API signing keys remain a conditional impersonation risk. A generated per-process webhook secret without stable configuration can also cause inconsistencies across workers/restarts. |
| CSRF/CORS | Protected API routes use an explicit `X-Telegram-Init-Data` header, not ambient cookie authentication; no permissive CORS middleware was found. No concrete conventional cross-origin CSRF bypass was identified. Token theft/XSS would still authorize same-origin requests. |
| SSRF, command injection, unsafe deserialization | No user-controlled URL fetch, shell command, `eval`, unsafe pickle, or YAML object-construction path was found in the reviewed application inputs. Media downloads use Telegram file IDs and AI calls use the SDK. This is scoped source-review evidence, not dependency-level assurance. |
| Secrets and data retention | `.dockerignore` addresses the previous `.env` build leak. Actual secrets and history were not exhaustively scanned. Raw text/transcriptions and feedback are persisted; “in-memory media processing” does not mean no personal-data retention. Define deletion/retention and external AI disclosure policies. |
| Error/log exposure | Client-facing bot errors are generally generic. Exception logging can nevertheless include provider responses or SQLAlchemy statement parameters; no parameter-hiding/redaction policy was found. Use synthetic failures to verify that financial text, tokens, and invite codes do not enter logs. No actual secret leak was observed. |

## 6. Performance and Optimization

These are source-derived optimization opportunities. No production latency, throughput, memory, or SQL-plan measurements were taken; no numerical speedup is claimed.

| Priority | Current behavior | Recommended change and measurement |
|---|---|---|
| High | `get_user_balance()` issues seven sequential aggregate queries, plus user access. Family summaries call it for every member and execute two additional internal-transfer queries, one now unused. | Consolidate balance components with conditional aggregates and aggregate per member. Record SQL statements/action and p95 latency before/after. Preserve the different rules for liquid income and external income. |
| High | `Transaction` declares no secondary indexes for its main user/family/date filters and sort order. | Inspect actual PostgreSQL indexes and representative `EXPLAIN (ANALYZE, BUFFERS)` plans on a safe fixture. Evaluate `(user_id, transaction_date, id)` and `(family_group_id, transaction_date, id)`, plus selective linked-account lookups. Choose indexes from workload evidence. |
| High | Bot processing loads user/category/account context before awaiting downloads or AI, retaining a database transaction/connection during slow external work. Report generation similarly awaits AI inside session scopes after SQL. | Read context in a short transaction, release the connection, call AI, then open a short write transaction and revalidate ownership/state. Measure pool waits, transaction age, and AI duration separately. |
| High | Photo albums parallelize downloads and model calls without application-wide limits. | Bound global and per-user concurrency and batch bytes; monitor peak RSS, queue delay, model cost, and rejected/expired jobs. |
| Medium | `BatchCategoryResolver` memoizes repeated names but still queries aliases individually for distinct products and performs per-item alias upserts. | Fetch aliases/categories in batches and use conflict-safe batched writes. Benchmark diverse receipt items, not only repeated names. |
| Medium | Every `TransactionService` constructs an `AIService`, including balance/read-only paths. SDK clients have no explicit lifecycle cleanup. | Inject a shared managed or lazily initialized client, close it on shutdown, and keep ledger reads independent of AI initialization. Measure connection/resource counts. |
| Medium | The UI requests category analytics while monthly analytics computes the same category breakdown internally. | Return a shared snapshot or avoid duplicate aggregates. Define one reporting period and family scope first. |
| Medium | Discount allocation calls `expense_indices.index(idx)` inside a loop. | Precompute index positions to remove the quadratic component. Keep the existing minor-unit conservation behavior covered. |
| Medium | Feeds use offset pagination and only a date sort; equal timestamps have no deterministic tiebreaker. | Use stable `(transaction_date, id)` ordering and cursor pagination if history size warrants it. Verify no skipped/duplicated rows while new operations arrive. |
| Medium | Reports load all active users, then await each user's AI result and send serially. Accrual loads every eligible account. | Page work, claim jobs durably, and use bounded worker concurrency with per-job observability. Do not create concurrent tasks sharing one `AsyncSession`. |

PostgreSQL does not automatically index the referencing side of a foreign key; see its [constraint documentation](https://www.postgresql.org/docs/16/ddl-constraints.html). Async ORM access also needs explicit loading and session boundaries; see [SQLAlchemy's asyncio guidance](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html#preventing-implicit-io-when-using-asyncsession).

Measure API/AI p50/p95/p99, SQL count and duration, pool occupancy/waits, long transactions, lock waits/deadlocks, duplicate-event suppression, financial reconciliation failures, media memory peaks, per-user AI consumption, and job/reply failure rates. Do not optimize away correctness or privacy checks.

## 7. Validation Record and Reproduction Targets

The audit harness ran in memory with synthetic identities, balances, and names; it did not create an application test file or contact external services. Missing application dependencies were isolated with doubles, while Pydantic request classes used the available local Pydantic runtime. Its version is not evidence of the deployed runtime version.

| Check against current source | Observed result | Interpretation |
|---|---|---|
| Empty-token and known-dummy-token HMAC payloads | Accepted by `validate_init_data` | Conditional API impersonation; B01 |
| Tampered signature / timestamp older than 24 hours | Rejected | Positive authentication controls work for these cases |
| Correctly signed future timestamp | Accepted | Missing future-skew bound; not an independent HMAC bypass |
| Family grocery row with a mixed private message | Family feed retained raw text; generic non-owner mask removed it | B03 |
| Recipient-owned family mirror from a mixed message | Generic mask retained sender's original private text | B03 |
| FX amount edit, 50,000 to 55,000 at 0.002 | Asset 5,100; linked asset amount 110 | B05 |
| Capitalized interest edit, 10 to 20 | Deposit stayed 1,010 | B05 |
| Loan receipt edit, 1,000 to 2,000 | Debt stayed 1,000 | B05 |
| Transfer-out with positive cash and negative asset amount | Asset decreased from 100 to 50 | B08 |
| Normalizer receives string `"false"` or numeric NaN | Accepted as financial / retained nonfinite amount | B08 |
| Generic manual transfer creation | Committed a transfer with no linked asset | B09 |
| Repayment with unset initial balance | Function committed debt/expense changes | B09 |
| Debt 100, repayment 150, then delete repayment | Debt 0 after payment, then 150 after deletion | B10 |
| Nested credit repayment service | Committed once before any ledger entry existed | B04 |
| Summary formatter with family totals and a dummy HTML link | Totals and raw link appeared in message text | B02/C01; aggregation scope independently traced in source |
| Actual asset request schemas | Accepted `"NaN"`, negative opening balance/rate; NaN bypassed nonpositive check | C05 |
| Actual transaction schema with `0.001` | Accepted | Scale mismatch; database result not executed |
| Cancelled album leader, then another message for same group | Group retained; later invocation returned `None` | C03 |

The report does not equate these function-level checks with HTTP end-to-end, browser exploit, PostgreSQL concurrency, or live AI tests. Required next-stage regressions are listed below so those gaps can be closed on an isolated staging fixture.

## 8. Recommended Architecture and Remediation Order

Keep the modular monolith, but establish enforceable boundaries:

1. **One financial operation coordinator.** Model operation kinds explicitly: expense, income, asset movement, loan opening, principal repayment, accrued interest, and family transfer. The coordinator validates user state, ownership, denomination, amount, and target compatibility; acquires locks consistently; persists all effects; and commits once.
2. **One authorization and presentation policy.** Define who can view a field independently from who owns a derived ledger row. Use it across API responses, Telegram messages, reports, and AI context. Raw-source provenance and personal assets require explicit handling.
3. **Durable input and job tracking.** Separate accepted input, applied financial operation, and delivered notification. Give incoming events and scheduled work stable unique keys and explicit retry states. Use an outbox/worker pattern where helpful, while acknowledging external delivery ambiguity.
4. **AI as a constrained parser/advisor.** Keep authorization, arithmetic, account resolution, and financial invariants in deterministic code. Validate the parsed operation before execution; preserve uncertainty rather than selecting an arbitrary account. Give the model only the data required for the current authorized task.
5. **Versioned persistence and reproducible deployment.** Add migration revisions, data reconciliation, limited runtime roles, locked dependencies, and operational evidence. Migrations should include existing-data review before adding constraints.

| Stage | Work | Acceptance criteria |
|---|---|---|
| 1. Contain privacy/authentication exposure | B01-B03, C01, private-chat policy | Missing/test secrets stop production startup. Family reports cannot infer private balances. Mixed messages and recipient-owned mirrors cannot disclose private source text. All user/model strings render safely. |
| 2. Restore financial conservation | B04-B06, B09-B11, C05 | Create/edit/delete conserves cash, assets, credit principal, and family transfer pairs across every entry point. Invalid/ambiguous amounts and targets fail before mutation. PostgreSQL concurrency/failure-injection tests pass. |
| 3. Make ingestion and jobs recoverable | B07, B12, C02-C03, C08 | Duplicate events do not duplicate ledger effects; restart does not discard pending input; partial receipt results are explicit; jobs have documented retry/catch-up and delivery semantics; port 443 remains reserved. |
| 4. Harden the AI/resource boundary | B08, C04, C06-C07 | Adversarial fixture outputs cannot violate invariants; indirect receipt/category prompts are tested separately from direct user prompts; quotas and size/concurrency limits are observable; membership and destination rules are enforced. |
| 5. Optimize and operationalize | Section 6, C09-C10 | Performance is demonstrated on representative data; dependency/image inventory is auditable; migration and backup recovery are exercised; CI runs real production functions with required dependencies. |

Minimum PostgreSQL/API regression scenarios should cover concurrent deposit/repayment/edit/delete, deletion of opposite family-transfer sides, duplicate webhook delivery and uncertain API retries, failure immediately after a credit mutation, repeated monthly accrual, overpayment and its inverse, FX edits and deletion, cross-family join/leave history, two-user balance inference, and all raw-message disclosure paths.

**Release recommendation:** Resolve the P1 privacy and financial-integrity findings before expanding the user base or increasing concurrency. The current source contains useful safeguards, but the documented guarantees are broader than the implementation and the available validation evidence support.
