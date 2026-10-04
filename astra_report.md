# astra_report

**Independent Audit of Smart Bujet**  
**Audit date:** October 5, 2026  
**Audit mode:** Read-only  
**Final repository revision observed during the audit:** `d9b7482`

The audit did not modify application files. This English version of the report was subsequently saved to the repository with the user's explicit authorization.

**Assessment:** The architectural foundation is suitable for a small application, but the current implementation contains significant risks of exposing family financial data and compromising accounting integrity. Correcting these defects is the priority; performance optimization should follow assurance that financial operations are correct.

## 1. Audit Scope and Evidence

The review covered the API, services, data models and schemas, Telegram handlers, MiniApp, deployment configuration, migration infrastructure, and tests.

The following checks were performed:

- In-memory syntax validation of **76 Python files**: no syntax errors.
- Syntax validation of `app.js`: no syntax errors.
- Six isolated checks of source functions with data access replaced by test doubles.
- Comparison of the implementation against `AGENTS.md` requirements and the architecture documentation.

Production, the live database, actual HTTP behavior, and production load were not tested. The contents of `.env` were not read. The full test suite was not run because the available Python environment lacked the application's main dependencies; no dependencies were installed.

During the audit, an external process changed and committed frontend files: HEAD advanced from `a74625a` to `d9b7482`. References to the affected frontend locations were rechecked. Python file checksums matched between the audit's checkpoint reads.

All findings below describe the code inspected during that audit. A source-level finding is not a claim that the issue was exploited or observed in production. File links and line numbers refer to the reviewed snapshot and may shift after later edits.

| Priority | Meaning |
|---|---|
| **P1** | Resolve before expanding use: data exposure, accounting corruption, or lost operations |
| **P2** | Address in the next improvement stage: reliability, maintainability, or performance |
| **Conditional risk** | Exposure depends on deployment settings; presence in production has not been established |

## 2. Existing Strengths

The separation into API endpoints, services, and models provides a useful foundation for further development. Telegram `initData` is verified using HMAC and `compare_digest`. Asset and credit services scope queries to the owner. Some list endpoints eagerly load related objects and limit page size.

The financial implementation also contains sound elements: database `Numeric` columns, use of `Decimal`, linked family transfer entries, and row locks when deleting transactions. However, these mechanisms are not applied consistently across all mutation paths.

## 3. Main Findings

### A01. P1 — Stored XSS in the Family Interface

**Code:** [src/static/app.js:1369](src/static/app.js#L1369), [src/static/app.js:1415](src/static/app.js#L1415).

The following values are interpolated into `innerHTML` without escaping:

- Member name.
- Transaction title.
- Category name.
- Transaction author name.

These values originate from user-controlled data. A family member can persist HTML content that another member's browser interprets when the family screen opens.

**Impact:** JavaScript execution in the MiniApp's context, access to `Telegram.WebApp.initData`, reading private data, and making API requests with the affected user's permissions.

**Recommendation:** Render user-controlled strings through `textContent` and review every dynamic HTML insertion. Add a Content Security Policy as an additional layer of protection. This rendering approach follows [OWASP's XSS prevention guidance](https://cheatsheetseries.owasp.org/cheatsheets/Cross_Site_Scripting_Prevention_Cheat_Sheet.html).

**Evidence level:** The path from user-controlled data to an unsafe HTML sink is confirmed in the source. Browser execution was not tested.

### A02. P1 — Deposit Name Masking Can Be Bypassed Through Another API

**Code:** [src/api/v1/transactions.py:24](src/api/v1/transactions.py#L24), [src/schemas/transaction.py:28](src/schemas/transaction.py#L28), [src/services/family_service.py:188](src/services/family_service.py#L188).

The dedicated family feed masks deposit-related transactions. However, `/api/v1/transactions/?include_family=true` returns family records directly, including `item_name`, `category_name`, and `raw_text`.

A second disclosure path exists for messages containing multiple operations. The entire original text is stored on each resulting transaction. If a message describes both a private deposit top-up and an ordinary purchase, masking the deposit entry does not remove the deposit name from the purchase entry's `raw_text`.

**Impact:** Violation of the explicitly stated requirement to keep personal asset names confidential in shared family feeds.

**Recommendation:** Apply one server-side policy for presenting other users' transactions across every API. Do not automatically expose the original message text in family responses.

### A03. P1 — Manual Transaction Creation Bypasses Core Validation

**Code:** [src/api/v1/transactions.py:43](src/api/v1/transactions.py#L43), [src/schemas/transaction.py:6](src/schemas/transaction.py#L6).

The manual endpoint constructs an ORM entity directly. It does not enforce:

- The `initial_balance` guard.
- Ownership of the selected category.
- Consistency between category type and transaction type.
- A strictly positive amount.
- Reconciliation of transfers with assets and family mirror entries.

An isolated check confirmed that `TransactionCreate` accepts `amount=-100`.

A user can also associate their own transaction with an existing ID belonging to another user's category. A subsequent list response using `joinedload` exposes that category's name.

**Impact:** Incorrect balances, bypassed onboarding accounting rules, and broken category isolation.

**Recommendation:** Route API and bot creation paths through the same financial operation service. Enforce strict input schemas and corresponding database constraints.

### A04. P1 — Credit State and Its Transaction Are Not Saved Atomically

**Code:** [src/services/transaction_service.py:390](src/services/transaction_service.py#L390), [src/services/credit_service.py:92](src/services/credit_service.py#L92), [src/services/credit_service.py:119](src/services/credit_service.py#L119).

`TransactionService` calls credit creation or repayment while processing a message. Those methods commit the shared session independently, before the complete operation has finished.

If a subsequent ledger entry or another item in the message fails, the debt change has already been persisted. The nested `commit` can also persist earlier pending changes in that session.

There is a separate inconsistency in the credit repayment API: it calls a method that reduces outstanding debt **without creating an expense transaction**. A repayment through the MiniApp and one recorded through a text message therefore have different effects on the liquid balance.

**Recommendation:** Use one database transaction boundary per business operation. Nested services should mutate state and flush when needed; the operation coordinator should own the final commit. A repayment must update the debt and cash ledger consistently.

### A05. P1 — Concurrent Requests Can Lose Balance Updates

**Code:** [src/services/asset_service.py:195](src/services/asset_service.py#L195), [src/services/credit_service.py:107](src/services/credit_service.py#L107), [src/services/transaction_service.py:821](src/services/transaction_service.py#L821).

Deposits, withdrawals, repayments, and edits use a read–calculate–write sequence without protection against concurrent changes in those paths.

For example, two deposits can both read a balance of 100. One saves 110 and the other saves 120. Both ledger entries may exist, while the final balance is 120 instead of 130.

Interest accrual has a similar problem: a preliminary `SELECT` checks for an existing accrual, but there is no unique constraint for the account and accounting period. Two workers can pass the check simultaneously. See [src/services/asset_service.py:334](src/services/asset_service.py#L334).

**Recommendation:** Apply a consistent locking or atomic-update strategy, enforce a unique accrual key per period, and acquire related rows in a consistent order. Verify the behavior with concurrent tests against PostgreSQL.

### A06. P1 — Repeated Message Delivery Can Record an Operation Twice

**Code:** [src/api/v1/webhook.py:19](src/api/v1/webhook.py#L19), [src/models/transaction.py:30](src/models/transaction.py#L30).

No application-level persistence of processed `update_id` values or another unique incoming event identifier was found. Processing an event creates new transactions each time.

Telegram permits repeated webhook delivery, and `update_id` is intended, among other uses, to help discard duplicate updates. See the [Telegram Bot API documentation](https://core.telegram.org/bots/api#update).

**Impact:** Duplicate expenses, income, repayments, and family transfers following redelivery or retries after an uncertain outcome.

**Recommendation:** Persist incoming events with unique keys, associate their results with those keys, and ensure the financial effect is applied once. Provide idempotency keys for manual operations as well.

### A07. P1 — Editing an Amount Corrupts Related Balances

**Code:** [src/services/transaction_service.py:879](src/services/transaction_service.py#L879).

The following results were confirmed by executing the source function in memory with a substituted session:

| Scenario | Expected result | Actual function result |
|---|---|---|
| A 50,000 KZT → 100 USD transfer is changed to 55,000 KZT with a conversion factor of 0.002 | Asset balance: 110 USD | Asset balance becomes **5,100**, while `asset_amount` becomes 110 |
| Accrued interest changes from 10 to 20, starting from a deposit balance of 1,010 | Deposit balance: 1,020 | Deposit balance remains **1,010** |
| A loan receipt changes from 1,000 to 2,000 with no repayments | Consistent credit adjustment, or rejection of the edit | Transaction amount: 2,000; original and outstanding debt: **1,000** |

The causes differ: the foreign-currency asset adjustment uses the difference in the base currency; capitalized income does not adjust the deposit balance; and the credit adjustment branch only handles expense transactions.

**Recommendation:** Define editing rules for each operation type. A safe general model is to reverse the previous financial effect and apply the new effect within one database transaction.

### A08. P1 — The Income/Expense Toggle Breaks Family Transfer Pairs

**Code:** [src/bot/handlers/tx_actions.py:70](src/bot/handlers/tx_actions.py#L70).

Changing the type updates only the selected transaction. If a mirror exists, the reciprocal links are removed, but the mirror entry itself remains.

For an expense of 1,000 paired with income of 1,000, changing the expense to income leaves two income entries of 1,000. The `ΔB_family = 0` invariant no longer holds.

The handler also does not reconcile a type change with the credit balance.

**Recommendation:** Disable simple toggling for linked operations or implement a complete transformation of the whole financial operation. Finding A11 describes a separate ORM loading error that may prevent this handler from reaching the mutation; fixing that loading error will not fix the accounting logic.

### A09. P1 — Amounts in Different Currencies Are Mixed

**Code:** [src/models/transaction.py:37](src/models/transaction.py#L37), [src/bot/handlers/start.py:155](src/bot/handlers/start.py#L155), [src/services/family_service.py:77](src/services/family_service.py#L77), [src/services/credit_service.py:53](src/services/credit_service.py#L53).

An ordinary transaction has no persisted currency. Changing the profile currency changes the interpretation of the entire history without conversion.

The family summary adds member balances expressed in different currencies. The credit summary similarly adds debts denominated in different currencies. A manual deposit into a foreign-currency asset records the same numerical amount in the asset and cash transaction without applying an exchange rate.

The portfolio uses fixed approximate exchange rates without an effective date. See [src/services/asset_service.py:265](src/services/asset_service.py#L265).

**Recommendation:** Store each operation's currency and original amount, exchange rate, and converted amount. Separate display currency from accounting currency. Aggregate amounts only after conversion to a common denomination.

### A10. P2 — Internal Transfers Are Subtracted from Family Income Twice

**Code:** [src/services/transaction_service.py:782](src/services/transaction_service.py#L782), [src/services/family_service.py:123](src/services/family_service.py#L123).

`get_user_balance()` already excludes mirror receipts from monthly income. The family summary adds these filtered values and subtracts internal receipts again.

**Confirmed example:** A family has external income of 100,000 and an internal transfer of 20,000. The function returns family income of **80,000**.

**Recommendation:** Eliminate internal transfers exactly once in a shared aggregation model. Do not conceal an incorrect result with `max(0, ...)`.

### A11. P2 — Implicit ORM Loading Can Fail After Data Has Been Saved

**Code:** [src/models/transaction.py:59](src/models/transaction.py#L59), [src/api/v1/transactions.py:62](src/api/v1/transactions.py#L62), [src/bot/handlers/tx_actions.py:31](src/bot/handlers/tx_actions.py#L31).

The `category_name` property accesses the lazily loaded `category` relationship. Manual transaction creation does not load that relationship before response serialization.

The toggle handler likewise calls `session.get(Transaction, ...)` and then synchronously accesses `tx.category`.

When that access requires a database query, it is incompatible with ordinary `AsyncSession` usage and can raise `MissingGreenlet`. This limitation is documented in [SQLAlchemy's asyncio guidance](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html#preventing-implicit-io-when-using-asyncsession).

**Impact:** The entry may already be committed, while the client receives an error and retries the request.

**Recommendation:** Explicitly load required relationships or construct response DTOs from explicitly selected fields. Integration tests should verify the HTTP response after persistence.

### A12. P1 — Webhook/Polling Selection Is Inconsistent with Port 8443

**Code:** [src/main.py:86](src/main.py#L86), [src/core/config.py:47](src/core/config.py#L47), [docker-compose.yml:6](docker-compose.yml#L6).

The current conditions produce the following behavior:

- A `WEBHOOK_DOMAIN` without a port enables webhook mode, but generates a URL with the implicit port 443.
- A value containing `:8443` selects polling because it contains a colon.
- Entering polling mode calls `drop_pending_updates=True`, discarding queued updates.

**Impact:** Incorrect delivery mode and loss of unprocessed messages when startup takes this path.

**Recommendation:** Configure the delivery mode explicitly and validate a separate public URL. Discarding pending updates should not be a routine startup action.

The `8443:443` mapping itself is correct: port 443 is used inside the container and does not occupy the host's reserved port 443.

## 4. Additional Security and Operational Risks

| Priority | Observation | Recommendation |
|---|---|---|
| **P1, conditional** | [Dockerfile:12](Dockerfile#L12) copies the entire build context. A local `.env` exists; neither `.dockerignore` nor `Dockerfile.dockerignore` exists. Building with this context includes that file in the image | Exclude secrets from the context and copy only necessary files. Exposure of an actual production image has not been established |
| **P1, conditional** | [src/core/config.py:7](src/core/config.py#L7) permits an empty bot token, which the `initData` validator then uses as its key. [src/api/v1/webhook.py:13](src/api/v1/webhook.py#L13) skips secret verification if the configured secret is explicitly empty | Fail production startup when secrets are empty or contain test values |
| **P1, conditional** | [scripts/init_db_roles.sql:5](scripts/init_db_roles.sql#L5) contains a known fallback password for a role permitted to read all tables | Require an explicitly supplied secret and limit the role to necessary views. Whether this script was applied on the server was not checked |
| **P2** | [Caddyfile:10](Caddyfile#L10) proxies HTTP requests to the backend | Redirect to the correct HTTPS address on port 8443 and verify actual HTTP exposure of the API |
| **P2** | [src/services/family_service.py:225](src/services/family_service.py#L225): hiding an invitation after a family becomes active does not revoke its code. Expiration and revocation mechanisms are absent | Define rules for rejoining, invitation revocation, and admission of new members |
| **P2** | [src/main.py:25](src/main.py#L25): the application executes DDL on startup, and the repository contains no Alembic revision files | Version migrations, execute them as a separate deployment step, and restrict the application's database permissions |
| **P2** | [src/core/accrual_scheduler.py:39](src/core/accrual_scheduler.py#L39): a missed final day of the month is not recovered. The manual endpoint allows accrual without checking whether the period is closed | Persist accounting periods, recover missed periods, and define rules for early accrual |
| **P2** | [src/services/ai_service.py:51](src/services/ai_service.py#L51): normalization drops `establishment_type` and `venue_name`, which restaurant receipt handling expects | Align the AI response schema with its consumer. Loss of both fields was confirmed by an in-memory check |

AI response validation also needs strengthening. JSON output alone does not guarantee valid amounts, operation types, string lengths, or consistency between fields. Recognition results can currently change financial state immediately. When selecting a deposit or credit account is ambiguous, request clarification instead of automatically selecting the first candidate.

## 5. Performance: Highest-Value Improvements

No production performance measurements were taken. The observations below follow from query structure and resource lifetimes; numerical speedup claims would require measurements.

| Priority | Bottleneck | Proposed improvement |
|---|---|---|
| **High** | [get_user_balance:738](src/services/transaction_service.py#L738) performs seven sequential aggregate queries | Use one query with conditional aggregates |
| **High** | The family summary performs that calculation for every member: `7 × member count`, followed by two more aggregate queries | Aggregate by member in one query and eliminate internal transfers once |
| **High** | The [transaction model](src/models/transaction.py#L30) declares no indexes for its principal filters and ordering | Inspect actual database indexes and execution plans. Candidate indexes include `(user_id, transaction_date, id)` and `(family_group_id, transaction_date, id)` |
| **High** | [process_text:292](src/services/transaction_service.py#L292) reads from the database before calling AI and finishes its transaction afterward | Fetch context in a short session, release the connection during the AI call, then open a short write transaction and revalidate relevant conditions |
| **High** | Voice and photo data are downloaded into memory before the initial-balance check; application-level size, rate, and concurrent-processing limits are absent | Validate the user and metadata before downloading; bound concurrency, duration, size, and AI consumption |
| **Medium** | [BatchCategoryResolver:58](src/services/transaction_service.py#L58) saves queries for repeated names, but unique items still generate individual database calls | Fetch aliases and categories in batches and batch alias updates |
| **Medium** | [AIService:69](src/services/ai_service.py#L69) creates a client for each service instance, including balance-calculation paths | Use lazy initialization or a shared managed client with explicit cleanup |
| **Medium** | [src/services/discount_service.py:86](src/services/discount_service.py#L86) calls `list.index()` inside a loop | Precompute the position lookup and eliminate the quadratic component |
| **Medium** | The MiniApp requests category analytics separately, while monthly analytics computes the category breakdown again internally | Return combined analytics or eliminate the duplicate calculation |

In PostgreSQL, a foreign key does not automatically create an index on the referencing column. Declaring `ForeignKey` therefore does not solve filtering performance on a large transaction table. See the [PostgreSQL constraint documentation](https://www.postgresql.org/docs/16/ddl-constraints.html).

**Measure:** API and AI p50/p95 latency, SQL queries per action, connection wait time, database transaction duration, memory use during media processing, recognition cost, and the proportion of duplicate events.

## 6. Tests and Architectural Resilience

The existing tests do not provide sufficient assurance of financial correctness:

- The [accrual test](tests/test_accrual_scheduler.py#L5) checks a separate copy of the calendar function rather than the production accrual mechanism.
- The [performance tests](tests/test_performance_receipt.py#L22) use substituted calls and repeated product names. They check caching behavior rather than PostgreSQL and AI performance under load.
- A substantial portion of the tests is skipped when dependencies are unavailable.
- No integration coverage was found for the principal scenarios involving concurrent writes, edits to related balances, repeated delivery, or masking bypass through alternative endpoints.

Minimum acceptance criteria for remediation:

1. Repeating an incoming event does not apply its balance change again.
2. Failure in any part of an operation rolls back its entire financial effect.
3. Creating, editing, toggling, and deleting a family transfer preserves pair consistency.
4. Asset and credit balances reconcile with the ledger after each operation.
5. Other users' private fields are absent from every family API response.
6. Family members' strings are rendered as text.
7. Concurrent operations produce the same final result as their valid sequential execution.
8. Changing the display currency does not reinterpret historical amounts.

The architectural recommendation is to retain the modular monolith and establish a **single mechanism for applying financial operations**, a shared authorization and masking policy, and durable tracking of incoming events. These responsibilities are currently spread across API endpoints, bot handlers, and services without consistent boundaries.

## 7. Remediation Order

| Stage | Work | Completion criterion |
|---|---|---|
| **1. Data protection** | XSS, family masking, category authorization, safe secret configuration and image builds | Cross-user checks pass through every access path |
| **2. Accounting integrity** | Shared transaction boundary, balance adjustments, repayments, mirror operations, and currencies | Financial invariants are verified by integration tests |
| **3. Reliable delivery** | Idempotency, correct webhook configuration on 8443, preservation of pending messages, and recovery of missed accruals | Retries and restarts neither lose nor duplicate operations |
| **4. Performance** | Aggregation, indexes, short sessions, batch queries, and AI limits | Improvements are demonstrated using representative measurements |
| **5. Operations** | Migrations, dependency locking, monitoring, and backup restoration checks | Deployments are reproducible; failures can be detected and recovered |

**Auditor's recommendation:** Defer expansion of the user base and workload until P1 findings are resolved. The most consequential defects are in server-side access rules and the consistency of financial operations.
