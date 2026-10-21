# Аудит безопасности, персональных данных и надёжности проекта `smart-bujet` (Argon Audit)

---

## Краткое резюме (Executive Summary)

### 1. Что было сделано
Проведён строго **read-only аудит** кода проекта `smart-bujet`, серверной инфраструктуры (`85.198.89.188`) и живой базы данных PostgreSQL (`postgres_dg_improve` на сервере). Никакие файлы, контейнеры или данные в БД не изменялись.

### 2. Какой результат получен
**Вердикт: ❌ Сервис пока НЕ готов к внешним пользователям.**

#### А. Состояние базы данных и персональных данных (Live DB + Code)
В БД `smart_bujet` (10 таблиц, владелец `bujet_user`) **все персональные и финансовые данные лежат в открытом виде (Plaintext)**. Владелец сервера через `psql`, бэкапы или MCP видит всю личную жизнь пользователя:
1. **`users` (2 строки):** открытые Telegram ID, `@username`, `first_name` и текущий баланс (`src/models/models.py:13-28`).
2. **`transactions` (195 строк) и `user_classification_feedback` (2 строки):** открытые названия покупок (`item_name`), суммы и дословные голосовые/текстовые сообщения в `raw_text` / `original_text` (например, кто сколько валюты купил, какие наличные нашёл и т.д.) (`src/bot/handlers/tx_actions.py:116-125`).
3. **`asset_accounts` (5 строк) и `credit_accounts` (2 строки):** открытые названия личных целей/вкладов (*«Роды»*, *«Доула»*, *«Страховка Дочка»*), названия банков (*Halyk*, *Tele2*), остатки долгов и платежи.
4. **`user_item_aliases` (144 строки):** полный словарь привычек и покупок пользователя с частотой (`usage_count`) в открытом тексте.
5. **`family_groups` (1 строка):** автоматически записывает имя создателя (`Семья <first_name>`) (`src/services/family_service.py:34`).
6. **Нюанс `PIIGuardrailService` (`src/services/pii_guardrail_service.py`):** он маскирует карты/телефоны/счета **только перед отправкой в Gemini**, а после ответа вызывает `unmask_payload()` и сохраняет в БД уже открытые данные. Кроме того, в `TransactionService.process_text` (`src/services/transaction_service.py:403-409`) в `classify_text()` не передаётся аргумент `known_names` (имена членов семьи уходят в Gemini без маскирования).

#### Б. Критические уязвимости инфраструктуры и надёжности
1. **Открытые порты БД и Vault наружу (P0):** На сервере выключен файрвол (`ufw inactive`), порт PostgreSQL `0.0.0.0:5432` (без SSL, а внутри локальной сети с `trust` в `pg_hba.conf`) и порт HashiCorp Vault `0.0.0.0:8200` открыты всему интернету.
2. **Бот работает на Long Polling со сбросом сообщений при рестарте:** В `.env` указан `WEBHOOK_DOMAIN=localhost`, а проверка `":" not in settings.domain` в `src/main.py:92-95` блокирует домен с портом `:8443` и при каждом перезапуске вызывает `delete_webhook(drop_pending_updates=True)`, удаляя сообщения пользователей.
3. **Нет Rate Limiting и защиты квот Gemini:** Любой пользователь может заспамить бота голосовыми/фото/PDF, исчерпав бюджет `GOOGLE_API_KEY` и лимит коннектов БД (`max_connections = 25` в Postgres, `src/core/database.py:8` без `pool_pre_ping=True`).
4. **Нет автобэкапов и каскадного удаления:** Единственный незашифрованный дамп БД сделан вручную 6 октября. Внешние ключи не имеют `ON DELETE CASCADE`, поэтому штатно удалить профиль пользователя нельзя.
5. **Баг пересчёта валютного вклада и гонки (Race Conditions):** В `src/services/transaction_service.py:1143-1144` при редактировании транзакции сумма умножается на курс вместо деления (`new_amount * exchange_rate`), а в `src/services/asset_service.py:201-265` нет `.with_for_update()`.

### 3. Какой это даёт эффект и как обезопасить сервис (Рекомендации)
Чтобы внешние пользователи были уверены, что **даже администратор** не может прочитать их данные, и сервис работал стабильно, рекомендуется внедрить архитектуру **Admin Blindness (Слепота администратора)**:

#### Шаг 1. Отказ от хранения прямых PII (Минимизация данных)
* **Убрать `username` и `first_name` из таблицы `users`:** в MiniApp имя берётся напрямую на клиенте из `Telegram.WebApp.initDataUnsafe.user`, хранить его в БД не нужно. В `family_groups` ставить нейтральное название `"Семейный бюджет"`.
* **Не сохранять `raw_text` и `original_text`:** после извлечения суммы и категории сырой текст/расшифровку голоса сразу отбрасывать (`None`).

#### Шаг 2. Слепое индексирование (Blind Indexing через `HMAC-SHA256`)
* **Обезличить `telegram_id`:** сделать `users.id` случайным `UUID`, а поиск при входе делать по `tg_id_hmac = HMAC-SHA256(SERVER_PEPPER, telegram_id)`. В таблице транзакций будут только анонимные `UUID`.
* **Обезличить словарь привычек (`user_item_aliases`):** хранить вместо открытого слова (`"манты"`) его хеш `HMAC-SHA256(user_key, item_name_normalized)`. Быстрый поиск (10 мс) продолжит работать, но прочитать список покупок в БД станет невозможно.

#### Шаг 3. Шифрование чувствительных полей (2 уровня на выбор)
Суммы (`amount`, `balance`) оставляем числовыми для работы SQL-агрегаций и начисления процентов (в привязке к анонимному `UUID` голые цифры не раскрывают личность), а текстовые названия (`transactions.item_name`, `asset_accounts.name`, `credit_accounts.name`, `bank_name`) шифруем:
1. **Уровень 1 (Серверное конвертное шифрование AES-256-GCM + HashiCorp Vault):**
   У каждого пользователя свой ключ `DEK`, зашифрованный через уже развёрнутый `hashicorp_vault`. В `psql`, логах и дампах вместо *«Роды»* или *«Халыковский кредит»* будет `v1:nonce:ciphertext`.
2. **Уровень 2 (Полный Zero-Knowledge — ключ у пользователя в `Telegram.WebApp.CloudStorage`):**
   При первом входе в MiniApp на телефоне пользователя генерируется ключевая пара `X25519`: приватный ключ сохраняется в облаке Telegram аккаунта пользователя (`CloudStorage`, к которому сервер не имеет доступа), а публичный — в БД. Бот при записи траты шифрует `item_name` публичным ключом пользователя, а расшифровка происходит только внутри MiniApp на телефоне клиента. **Технически ни владелец сервера через root/psql, ни кто-либо при взломе сервера расшифровать названия трат и вкладов не сможет.**

#### Шаг 4. Инфраструктурный и юридический минимум перед релизом
1. **Сеть и БД:** привязать порты `5432` и `8200` к `127.0.0.1`, включить `ufw` (оставив `22, 80, 443, 8443`), убрать `trust` из `pg_hba.conf`, ограничить роль `mcp_readonly` (`scripts/init_db_roles.sql`) только агрегированными `VIEW` без доступа к сырым таблицам.
2. **Надёжность:** починить условие вебхука для порта `:8443` в `src/main.py:92`, добавить дедупликацию `update_id` в `src/api/v1/webhook.py`, включить `pool_pre_ping=True`, добавить Rate Limiting на запросы к Gemini и настроить ежедневный зашифрованный бэкап (`pg_dump | age`).
3. **Согласие и удаление (152-ФЗ / ЗРК о ПДн):** использовать платный тариф Gemini API (где данные не идут на обучение моделей Google), добавить при `/start` принятие Политики конфиденциальности и кнопку **«Удалить аккаунт и все данные»** (`ON DELETE CASCADE`).

---

## Детальный технический разбор (Deep Dive)

### 1. Инфраструктура на сервере (`85.198.89.188`)
На хосте запущены 5 Docker-контейнеров:
- `smart_bujet_backend` (`smart-bujet-backend:latest`, лимит `0.40 CPU / 240 MiB RAM`, фактическое потребление `~85 MiB RAM`). Подключается к БД через `host.docker.internal:5432` под ролью `bujet_user`.
- `smart_bujet_caddy` (`caddy:2-alpine`, лимит `64 MiB RAM`, пробрасывает `0.0.0.0:80->80` и `0.0.0.0:8443->443`).
- `postgres_dg_improve` (`postgres:16-alpine`, лимит `256 MiB RAM`, `max_connections = 25`, `shared_buffers = 32MB`).
- `hashicorp_vault` (`hashicorp/vault:latest`, порт `0.0.0.0:8200`).
- `mtproto-proxy` (`nineseconds/mtg:2`, порт `0.0.0.0:443`).

### 2. Карта таблиц и чувствительных данных в БД `smart_bujet`

| Таблица | Кол-во строк (Prod) | Колонки с PII и чувствительными финансовыми данными | Как хранится сейчас (факт из Live DB) |
|---|---|---|---|
| `users` | `2` | `id` (BigInt Telegram ID), `username`, `first_name`, `currency`, `initial_balance`, `family_group_id` | Открытый текст (`id`, `@username`, имя, баланс). |
| `transactions` | `195` | `user_id`, `amount`, `original_amount`, `discount_amount`, `item_name`, `raw_text`, `asset_amount`, `exchange_rate`, `asset_account_id`, `credit_account_id` | Открытый текст и суммы, включая полные голосовые/текстовые фразы в `raw_text`. |
| `asset_accounts` | `5` | `user_id`, `name`, `type`, `currency`, `balance`, `interest_rate` | Открытый текст с личными/семейными целями и точными суммами (*«Страховка Дочка»*, *«Доула»*, *«Роды»*, *«Наличные»* и др.). |
| `credit_accounts` | `2` | `user_id`, `name`, `bank_name`, `original_amount`, `remaining_amount`, `monthly_payment` | Открытый текст с названиями кредитов, банков, остатками и ежемесячными платежами. |
| `family_groups` | `1` | `name`, `owner_id`, `invite_code` | Автоматически подставляет имя владельца: `Семья <first_name>` (`src/services/family_service.py:34`) и открытый `invite_code`. |
| `user_item_aliases` | `144` | `user_id`, `item_name_normalized`, `category_id`, `usage_count` | Полный словарь привычек и покупок конкретного пользователя в открытом виде с частотой покупок (`usage_count`). |
| `user_classification_feedback` | `2` | `user_id`, `transaction_id`, `original_text` | Дублирует сырой пользовательский ввод (`raw_text` или `item_name`) при нажатии кнопки смены типа операции в боте (`src/bot/handlers/tx_actions.py:116-125`). |
| `categories` | системные + кастомные | `user_id`, `name`, `type` | Пользовательские категории привязаны к `user_id` в открытом виде. |
| `scheduled_report_logs` | лог рассылок | `user_id`, `report_type`, `period_key`, `status`, `error_message` | Хранит `user_id` (Telegram ID) и историю доставки отчетов. |
| `dynamic_few_shots` | `13` | `domain_tag`, `raw_query`, `expected_payload` | Системный каталог примеров для LLM (не содержит пользовательских PII). |

### 3. Чек-лист перед открытием для внешних пользователей (Pre-Launch Checklist)

1. **[P0 — Инфраструктура]**:
   - Изменить биндинг портов в compose-файлах для `postgres_dg_improve` и `hashicorp_vault` с `0.0.0.0` на `127.0.0.1`.
   - Включить `ufw`, разрешив входящие только на `22/tcp` (SSH), `80/tcp`, `443/tcp` (MTProto), `8443/tcp` (Caddy MiniApp/Webhook).
   - Заменить `trust` на `scram-sha-256` в `pg_hba.conf`.
2. **[P0 — Приватность / Admin Blindness]**:
   - Перестать сохранять `username`, `first_name` в `users` и `raw_text` / `original_text` в `transactions` / `user_classification_feedback`.
   - Перевести `user_item_aliases.item_name_normalized` и `telegram_id` на слепой индекс `HMAC-SHA256`.
   - Внедрить шифрование `AES-256-GCM` (`EncryptedString`) для `transactions.item_name`, `asset_accounts.name`, `credit_accounts.name`, `credit_accounts.bank_name` (через Vault Transit или ключи в `Telegram.WebApp.CloudStorage`).
   - Передать `known_names` в `classify_text` в `TransactionService.process_text`.
3. **[P1 — Защита квот, надёжность и комплаенс]**:
   - Добавить Rate Limiting на AI-вызовы (лимит в минуту/сутки на пользователя) и на `POST /api/v1/family/join`.
   - Исправить условие установки вебхука с портом `:8443` в `src/main.py:92`, убрать `drop_pending_updates=True` и добавить дедупликацию `update_id`.
   - Настроить `pool_pre_ping=True` в SQLAlchemy и поднять `max_connections = 100` в Postgres.
   - Исправить формулу валютного пересчета (`/` вместо `*`) в `src/services/transaction_service.py:1144` и добавить `.with_for_update()` в `AssetService`.
   - Добавить `ON DELETE CASCADE`, кнопку полного удаления аккаунта (`/delete_account`) и экран согласия с Политикой конфиденциальности при `/start`.
   - Настроить ежедневный зашифрованный `pg_dump` (через `age`/`gpg`).


---

# Повторный аудит (Re-Audit после коммита `f1788dc`)

Дата проверки: `2026-10-21`
Проверенный коммит: `f1788dc` (*"feat: user personalization facts CRUD and Argon security audit remediations"*)
Проверены: код `C:\Users\aanto\smart-bujet`, `C:\Users\aanto\smart-bujet-dev`, а также живой сервер `85.198.89.188` (контейнеры `smart_bujet_backend`, `smart_bujet_backend_dev`, `postgres_dg_improve`, `hashicorp_vault` и база `smart_bujet`).

---

## 1. Что реально исправлено и работает на проде ✅

1. **Очистка `raw_text` (текстовые, ручные, чековые транзакции) и `original_text` в коде и БД:**
   - В `TransactionService.process_text` (`src/services/transaction_service.py:555`), `_handle_intra_family_mirror` (`:169`), `_build_transactions_from_receipt_payload` (`:844`), `create_manual_transaction` (`:1430`), а также в `AssetService.deposit_to_asset` (`src/services/asset_service.py:243`) и `withdraw_from_asset` (`:302`) установлено `raw_text=None`.
   - В `handle_confirm_cat` (`src/bot/handlers/tx_actions.py:119`) при сохранении `UserClassificationFeedback` установлено `original_text=None`.
   - В живой БД `smart_bujet` старые значения очищены (`SELECT count(raw_text) FROM transactions` = `0` из `195`; `SELECT count(original_text) FROM user_classification_feedback` = `0` из `2`).
2. **Передача `known_names` в `PIIGuardrailService` при классификации текста:**
   - В `TransactionService.process_text` (`src/services/transaction_service.py:401-424`) собираются `first_name` пользователя и членов его семьи и передаются в `self.ai_service.classify_text(..., known_names=known_names)`.
3. **Исправлена формула валютного пересчёта при редактировании транзакции:**
   - В `TransactionService.update_transaction` (`src/services/transaction_service.py:1159-1160`) умножение `new_amount * Decimal(str(tx.exchange_rate))` заменено на деление `new_amount / Decimal(str(tx.exchange_rate))` с проверкой `> 0`.
4. **Добавлены пессимистичные блокировки (`SELECT ... FOR UPDATE`):**
   - В `AssetService._get_asset_with_access` (`src/services/asset_service.py:97-108`) добавлен параметр `with_for_update=True` (используется в `deposit_to_asset:201` и `withdraw_from_asset:260`).
   - В `TransactionService.update_transaction` (`src/services/transaction_service.py:1156-1175`) добавлен `.with_for_update()` при чтении `Transaction` и `CreditAccount`.
5. **Убрано ограничение `":" not in settings.domain`, `drop_pending_updates=False` и добавлена дедупликация `update_id`:**
   - В `src/main.py:93-105` снята блокировка на двоеточие в домене (`:8443`), выставлен `drop_pending_updates=False`.
   - В `src/api/v1/webhook.py:14-49` добавлен in-memory фильтр дублей `is_duplicate_update` с TTL 300 секунд.
6. **Добавлена фича «Память агента» (`user_agent_memories`):**
   - Создана модель `UserAgentMemory` (`src/models/agent_memory.py:15-34`), таблица в БД, CRUD API `/api/v1/facts/` (`src/api/v1/facts.py:1-154`), вкладка «🧠 Память» в MiniApp (`src/static/index.html:99-102`, `src/static/app.js:1682-1766`) и передача фактов в `AIService.generate_financial_advice` (`src/services/ai_service.py:418-438`) при ручном запросе отчёта из бота (`src/bot/handlers/summary.py:203-242`).

---

## 2. Что агент сделал с критическими ошибками или оставил «мёртвым кодом» ⚠️

### 2.1. [CRITICAL BUG] Удаление аккаунта `DELETE /api/v1/auth/me` гарантированно падает с `500 IntegrityError`
* **Что сделал агент:** В `src/api/v1/auth.py:67-90` добавил эндпоинт `delete_my_account`, написал в комментарии *"Permanently erases user account and all personal/financial data via ON DELETE CASCADE"* и вызвал `await db.delete(user)`.
* **Почему это не работает:**
  1. Ни в моделях SQLAlchemy (`src/models/transaction.py:34`, `src/models/credit.py:23`, `src/models/alias.py:19`, `src/models/category.py:27`), ни в самой базе PostgreSQL на внешних ключах `transactions_user_id_fkey`, `credit_accounts_user_id_fkey`, `user_item_aliases_user_id_fkey`, `categories_user_id_fkey` **НЕТ `ON DELETE CASCADE`**.
  2. Любая попытка удалить реального пользователя, у которого есть хотя бы одна транзакция, кредит, алиас или своя категория, приводит к `ForeignKeyViolationError` (`500 Internal Server Error`).
  3. Кроме того, если удаляемый пользователь является владельцем семьи (`family_groups.owner_id`), удаление упадёт или сломает семью партнёра.
  4. Ни в MiniApp (`src/static/index.html`, `src/static/app.js`), ни в Telegram-боте **нет кнопки или команды `/delete_account`**, через которую пользователь вообще мог бы вызвать этот эндпоинт.

### 2.2. [DEAD CODE / БУТАФОРИЯ] `AIRateLimiter` написан, но НИГДЕ не вызывается
* **Что сделал агент:** В конец `src/services/ai_service.py:622-647` добавил класс `AIRateLimiter` и синглтон `ai_rate_limiter = AIRateLimiter()`, а также написал unit-тест `test_personalization_and_argon_security.py:49-65`, который тестирует сам класс изолированно.
* **Почему это не работает:** Метод `ai_rate_limiter.check_and_record()` **не вызывается ни в одном методе `AIService` (`classify_text`, `parse_voice`, `parse_receipt_media`, `generate_financial_advice`, `classify_user_fact`), ни в хэндлерах бота, ни в API роутерах** (0 вызовов во всём `src/`). В продакшене защита квот Gemini и Whisper полностью отсутствует.

### 2.3. [DEAD BOT COMMAND] Команда `/facts` висит в меню бота, но не имеет обработчика
* **Что сделал агент:** В `src/main.py:80` добавил `BotCommand(command="facts", description="🧠 Персонализация и память агента")`.
* **Почему это не работает:** В `src/bot/handlers/` **нет хэндлера `Command("facts")`**. Когда пользователь нажимает `/facts` в меню Telegram-бота, сообщение перехватывается общим текстовым хэндлером трат (`text_tx.py`) и отправляется в парсер покупок как текст траты!

### 2.4. [NEW INFRA BUG] Конфликт пула соединений SQLAlchemy (`max 60`) с лимитом PostgreSQL (`max_connections = 25`)
* **Что сделал агент:** В `src/core/database.py:8-16` выставил `pool_size=10, max_overflow=20` (до **30 соединений** на один процесс бэкенда).
* **Почему это опасно:** На сервере одновременно запущены два контейнера (`smart_bujet_backend` и `smart_bujet_backend_dev`), что в пике даёт до **60 соединений**, плюс другие сервисы на том же контейнере `postgres_dg_improve`. При этом в `/home/ag_admin/postgres/postgresql.conf` на сервере лимит **`max_connections` остался равен `25`**! Под нагрузкой база начнёт отбрасывать коннекты с `TooManyConnectionsError`.

### 2.5. Пропуски в очистке `raw_text`, именах семей и «Памяти агента»
1. **Голосовые сообщения всё ещё сохраняют `raw_text` в БД:** В `TransactionService.process_voice` (`src/services/transaction_service.py:748`) агент забыл заменить `raw_text=last_raw_text` на `raw_text=None`.
2. **В боевой БД осталось старое название семьи с именем:** В коде `src/services/family_service.py:34` дефолт для новых семей изменён на `"Семейный бюджет"`, но в боевой таблице `family_groups` существующая строка по-прежнему хранит `Семья Anton`.
3. **Автоматические отчёты по расписанию игнорируют память агента:** В `src/core/report_scheduler.py:116` вызов `await ai_service.generate_financial_advice(summary)` выполняется **без передачи `facts=...`**.
4. **Факты из памяти агента (`fact_text`) уходят в Gemini без `PIIGuardrailService`:** Ни в `AIService.classify_user_fact` (`src/services/ai_service.py:559-605`), ни в `AIService.generate_financial_advice` (`src/services/ai_service.py:421-437`) текст фактов не маскируется через `PIIGuardrailService.mask_text`.

---

## 3. Что агент упустил полностью (0% выполнения из `argon-audit.md`) ❌

1. **[P0] Сетевая безопасность сервера (`85.198.89.188`) не тронута вообще:**
   - Межсетевой экран `ufw` по-прежнему **выключен** (`Status: inactive`, `iptables INPUT ACCEPT`).
   - Порт PostgreSQL (`postgres_dg_improve`) **`0.0.0.0:5432`** открыт всему интернету без SSL (`ssl = off`).
   - В `/home/ag_admin/postgres/pg_hba.conf` по-прежнему стоят опасные правила `local all all trust` и `host all all 127.0.0.1/32 trust` (любой локальный процесс заходит суперпользователем без пароля).
   - Порт HashiCorp Vault (`hashicorp_vault`) **`0.0.0.0:8200`** открыт всему интернету без TLS.
2. **[P0] «Слепота администратора» (Admin Blindness — шифрование и обезличивание БД) не реализована вообще:**
   - Ни одного поля с шифрованием (`AES-256-GCM`) и ни одного слепого индекса (`HMAC-SHA256`) не добавлено.
   - В таблице `users` в открытом виде лежат Telegram ID, `username` (`heretic_ded`, `akadyrova`) и `first_name` (`Anton`, `Aiganym`).
   - В открытом виде (`plaintext`) лежат: `transactions.item_name`, `asset_accounts.name` (*«Страховка Айкоша и Тоша»*, *«Страховка Дочка»*, *«Доула»*, *«Роды»*, *«Наличные»*), `credit_accounts.name`, `credit_accounts.bank_name`.
   - Новая таблица `user_agent_memories.fact_text` также создана **в открытом виде (`Text`)** — теперь там в plaintext лежат ещё и личные факты о зарплате, здоровье и семье!
   - Таблица `user_item_aliases.item_name_normalized` (144 строки) по-прежнему хранит открытые названия покупок вместо `HMAC-SHA256`.
3. **[P1] Автоматические зашифрованные бэкапы не настроены:**
   - В `crontab` и `systemd` на сервере нет задач резервного копирования. В `/home/ag_admin/backups/` лежат только 2 ручных незашифрованных `.sql.gz` файла.
4. **[P1] Юридическое согласие (152-ФЗ / ЗРК о ПДн) и защита `/api/v1/family/join`:**
   - При `/start` нет экрана принятия Политики конфиденциальности (согласия на обработку данных и передачу в Gemini).
   - На `POST /api/v1/family/join` нет защиты от перебора `invite_code` (Rate Limit).
5. **[P2] Бот на проде всё ещё работает в режиме Polling, а локальный `smart-bujet-dev` не синхронизирован:**
   - В `/home/ag_admin/smart-bujet/.env` на сервере оставлен `WEBHOOK_DOMAIN=localhost`.
   - Локальная папка `C:\Users\aanto\smart-bujet-dev` осталась на старом коммите `1cdfad8` (тогда как на сервере `/home/ag_admin/smart-bujet-dev` на `f1788dc`).

---

## 4. Чёткое ТЗ для агента: что ОБЯЗАТЕЛЬНО нужно сделать (Definition of Done)

Ниже приведён исчерпывающий список задач. **Запрещается создавать классы-заглушки, которые не вызываются в боевом коде, или писать комментарии про `CASCADE` без реальной миграции БД.**

### Блок 1. Сервер, Сеть и СУБД (`85.198.89.188`) — Сделать в первую очередь!
1. **Закрыть порты Postgres и Vault на `127.0.0.1`:**
   - В compose-конфигурации контейнеров `postgres_dg_improve` и `hashicorp_vault` на сервере изменить проброс портов с `0.0.0.0:5432:5432` на `127.0.0.1:5432:5432` и с `0.0.0.0:8200:8200` на `127.0.0.1:8200:8200`. Перезапустить эти контейнеры и проверить через `ss -tulpn`, что на `0.0.0.0:5432` и `0.0.0.0:8200` больше никто не слушает. *(Контейнер `mtproto-proxy` на порту `443` НЕ ТРОГАТЬ!).*
2. **Включить межсетевой экран `ufw`:**
   - Разрешить входящие соединения **только** на `22/tcp` (SSH), `80/tcp` (HTTP Caddy), `443/tcp` (MTProto Proxy), `8443/tcp` (HTTPS Caddy MiniApp/Webhook). Включить `ufw enable` и проверить `ufw status verbose`.
3. **Исправить `pg_hba.conf` и `postgresql.conf` в `/home/ag_admin/postgres/`:**
   - В `pg_hba.conf` заменить `trust` на `scram-sha-256` для `local` и `127.0.0.1/32` (и запретить подключения с `0.0.0.0/0`, оставив только внутреннюю подсеть Docker `172.16.0.0/12` с `scram-sha-256`).
   - В `postgresql.conf` увеличить `max_connections = 100` (сейчас `25`, что конфликтует с пулом SQLAlchemy). Перезагрузить конфигурацию Postgres (`SELECT pg_reload_conf();` или рестарт контейнера для `max_connections`).
4. **Настроить ежедневный зашифрованный бэкап БД:**
   - Сгенерировать пару ключей `age` (`age-keygen`) или `gpg` (приватный ключ отдать владельцу / не хранить рядом с бэкапами, на сервере оставить только публичный ключ получателя).
   - Добавить скрипт `/home/ag_admin/scripts/backup_smart_bujet.sh` и задачу в `crontab` (`0 3 * * *`), которая делает `docker exec postgres_dg_improve pg_dump -U bujet_user -Fc smart_bujet | age -r <PUBLIC_KEY> > /home/ag_admin/backups/smart_bujet_$(date +\%F).dump.age` и удаляет архивы старше 14 дней. Удалить старые незашифрованные `.sql.gz` дампы из `/home/ag_admin/backups/`.

### Блок 2. «Слепота администратора» (Шифрование БД и обезличивание PII)
1. **Внедрить прозрачное шифрование чувствительных текстовых колонок (`AES-256-GCM`):**
   - Реализовать SQLAlchemy `TypeDecorator` `EncryptedString` (на базе `cryptography.hazmat.primitives.ciphers.aead.AESGCM` с префиксом версии `enc:v1:<base64(nonce + ciphertext)>`, чтобы отличать зашифрованные строки от старых при миграции).
   - Ключ шифрования (`DATA_ENCRYPTION_KEY`) должен загружаться из `.env` / HashiCorp Vault (не хардкодить дефолтный ключ в коде!).
   - Применить `EncryptedString` к следующим колонкам моделей:
     - `Transaction.item_name` (`src/models/transaction.py`)
     - `AssetAccount.name` (`src/models/asset.py`)
     - `CreditAccount.name`, `CreditAccount.bank_name` (`src/models/credit.py`)
     - `UserAgentMemory.fact_text` (`src/models/agent_memory.py`)
   - **Написать и выполнить скрипт миграции существующих данных в боевой БД**, который прочитает все текущие открытые строки в `transactions`, `asset_accounts`, `credit_accounts`, `user_agent_memories` и перезапишет их в зашифрованном виде (`enc:v1:...`). Проверить через `psql`, что в таблицах больше нет открытого текста (*«Роды»*, *«Доула»*, *«Halyk»* и т.д.).
2. **Перевести `user_item_aliases` на слепой индекс (`HMAC-SHA256`):**
   - В `UserItemAlias` (`src/models/alias.py`) при сохранении и поиске алиаса вычислять `HMAC-SHA256(key=BLIND_INDEX_SECRET, msg=item_name_normalized.encode('utf-8')).hexdigest()` и хранить в `item_name_normalized` только 64-символьный hex-хеш.
   - Сконвертировать все 144 существующих алиаса в боевой БД в HMAC-хеши.
3. **Убрать хранение открытых `username`, `first_name` и старого имени семьи:**
   - В `User` (`src/models/user.py`) зашифровать `first_name` через `EncryptedString`, а `username` перестать сохранять (`username = None`) и очистить в боевой БД (`UPDATE users SET username = NULL;`).
   - В боевой БД обновить название существующей семьи: `UPDATE family_groups SET name = 'Семейный бюджет';`.
   - В `TransactionService.process_voice` (`src/services/transaction_service.py:748`) заменить `raw_text=last_raw_text` на `raw_text=None`.

### Блок 3. Исправление сломанных фич из коммита `f1788dc`
1. **Починить удаление аккаунта (`DELETE /api/v1/auth/me` и `ON DELETE CASCADE`):**
   - В моделях `Transaction`, `AssetAccount`, `CreditAccount`, `UserItemAlias`, `Category`, `UserClassificationFeedback`, `ScheduledReportLog`, `UserAgentMemory` прописать `ForeignKey("users.id", ondelete="CASCADE")`.
   - Выполнить в боевой БД `ALTER TABLE ... DROP CONSTRAINT ..._user_id_fkey, ADD CONSTRAINT ..._user_id_fkey FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;` для всех таблиц, ссылающихся на `users(id)`.
   - В `delete_my_account` (`src/api/v1/auth.py:67-90`) перед `await db.delete(user)` обработать случай, когда пользователь состоит в `family_groups` (если он `owner_id` и в семье есть другие участники — передать `owner_id` второму участнику; если он единственный участник — отвязать `user.family_group_id = None` и удалить `FamilyGroup`).
   - Добавить кнопку **«🗑 Удалить аккаунт и все данные»** с подтверждением в MiniApp (`src/static/index.html`, `src/static/app.js`) и команду `/delete_account` в Telegram-боте.
   - Написать интеграционный тест, который создаёт пользователя с транзакцией, активом, кредитом, алиасом и семьёй, вызывает `DELETE /api/v1/auth/me` и проверяет, что возвращается `200 OK`, а все записи каскадно удалены.
2. **Реально подключить `AIRateLimiter` и защиту `/api/v1/family/join`:**
   - Встроить вызов `ai_rate_limiter.check_and_record(user_id)` внутрь методов `AIService` (`classify_text`, `parse_voice`, `parse_receipt_media`, `generate_financial_advice`, `classify_user_fact`) или на уровне хэндлеров/сервисов с передачей `user_id` и возвратом понятного сообщения пользователю при превышении лимита (например, `HTTPException(429)` в API и вежливое предупреждение в боте).
   - Добавить Rate Limiter на `POST /api/v1/family/join` (не более 5 неудачных попыток ввода `invite_code` за 10 минут на одного `user_id`).
3. **Реализовать обработчик команды `/facts` в Telegram-боте:**
   - Добавить в `src/bot/handlers/` хэндлер `Command("facts")`, который выводит пользователю список сохранённых фактов из `UserAgentMemory` с inline-кнопками удаления каждого факта и кнопкой перехода во вкладку «🧠 Память» в MiniApp (чтобы `/facts` не улетал в парсер трат!).
4. **Довести до ума интеграцию `UserAgentMemory` (Память агента):**
   - В `src/core/report_scheduler.py:116` загружать факты пользователя из `UserAgentMemory` и передавать `facts=user_facts` в `ai_service.generate_financial_advice(summary, facts=user_facts)`.
   - В `AIService.classify_user_fact` (`src/services/ai_service.py:559`) и `AIService.generate_financial_advice` (`:421`) пропускать `fact_text` через `PIIGuardrailService.mask_text(..., known_names=known_names)` перед отправкой в Gemini.
5. **Добавить экран согласия с Политикой конфиденциальности при `/start`:**
   - Для новых пользователей при `/start` (до создания активного профиля / выбора валюты) показывать краткое уведомление о правилах хранения данных (зашифрованное хранение, использование облачного ИИ для распознавания чеков/голоса, право на полное удаление через `/delete_account`) с кнопкой `✅ Принимаю условия`.
6. **Синхронизировать `C:\Users\aanto\smart-bujet-dev`:**
   - Сделать `git pull` в `C:\Users\aanto\smart-bujet-dev`, чтобы локальная dev-папка не отставала от прод-репозитория.
