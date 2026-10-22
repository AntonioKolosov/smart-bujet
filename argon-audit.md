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


---

# Третий аудит (Re-Audit #3: Prod `b406bc8` + Dev `d819165` — Выписки и Персонализация)

Дата проверки: `2026-10-22`
Проверенные коммиты:
- **Prod (`C:\Users\aanto\smart-bujet` и `/home/ag_admin/smart-bujet`):** `b406bc8` (*"chore(prod): isolate Argon security audit fixes, remove experimental personalization, add return to menu button"*)
- **Dev (`C:\Users\aanto\smart-bujet-dev` и `/home/ag_admin/smart-bujet-dev`):** `d819165` (*"feat(dev): user facts personalization, bank statement PDF ingestion, Argon security audit fixes, return to menu button"*)
- **Боевой сервер `85.198.89.188`:** контейнеры `smart_bujet_backend`, `smart_bujet_backend_dev`, `postgres_dg_improve` (базы `smart_bujet` и `smart_bujet_dev`), `hashicorp_vault`.

---

## 1. Статус выполнения Блоков 1, 2, 3 из предыдущего аудита — ❌ 0% ИСПРАВЛЕНИЙ

Разработчик разделил ветки (вынес персонализацию из Prod в Dev и синхронизировал локальный `smart-bujet-dev`), **но НЕ выполнил ни одного пункта из Блоков 1, 2 и 3 `argon-audit.md`**:

1. **Блок 1 (Сервер, Сеть, Postgres, Бэкапы) — НЕ ВЫПОЛНЕНО:**
   - Порты `0.0.0.0:5432` (`postgres_dg_improve`, `ssl = off`) и `0.0.0.0:8200` (`hashicorp_vault`) по-прежнему открыты всему интернету.
   - `ufw status` по-прежнему `inactive`.
   - В `pg_hba.conf` сохраняются правила `local all all trust`, `host all all 127.0.0.1/32 trust` и `host all all 0.0.0.0/0 scram-sha-256`.
   - В `/home/ag_admin/postgres/postgresql.conf` лимит `max_connections = 25` не увеличен, хотя два запущенных контейнера (`smart_bujet_backend` + `smart_bujet_backend_dev`) имеют пул `10 + 20 = 30` соединений каждый (**60 соединений суммарно при лимите 25**).
   - `crontab -l` пуст, ключи `age`/`gpg` не созданы, в `/home/ag_admin/backups/` лежат 3 ручных незашифрованных `.sql.gz` дампа.
2. **Блок 2 (Шифрование `AES-256-GCM` и `HMAC-SHA256` Blind Index) — НЕ ВЫПОЛНЕНО:**
   - Ни в `smart-bujet`, ни в `smart-bujet-dev` нет `EncryptedString` (`AES-256-GCM`) и нет `HMAC-SHA256` для алиасов.
   - В обеих базах (`smart_bujet` и `smart_bujet_dev`) все поля `users` (`username`, `first_name`), `transactions.item_name`, `asset_accounts.name` (*«Роды»*, *«Доула»*, *«Страховка Дочка»*), `credit_accounts`, `user_item_aliases` (144 строки) и `user_agent_memories.fact_text` лежат в **100% открытом тексте (`plaintext`)**.
   - В БД `smart_bujet` (Prod) запись `family_groups.name` по-прежнему называется `Семья Anton`, а таблица `user_agent_memories` осталась в прод-базе после отката кода.
   - В `TransactionService.process_voice` (`src/services/transaction_service.py:748`) по-прежнему стоит `raw_text=last_raw_text` вместо `raw_text=None`.
3. **Блок 3 (Исправление сломанных фич из `f1788dc`) — НЕ ВЫПОЛНЕНО:**
   - **`ON DELETE CASCADE` и удаление аккаунта:** Ни в моделях (`transaction.py:34`, `credit.py:23`, `alias.py:19`, `category.py:27`), ни в внешних ключах БД `smart_bujet` и `smart_bujet_dev` (где `ON DELETE CASCADE` нет даже на `asset_accounts_user_id_fkey`!) каскадное удаление не добавлено. Вызов `DELETE /api/v1/auth/me` (`src/api/v1/auth.py:67-90`) гарантированно падает с `500 ForeignKeyViolationError`. При удалении единственного участника семьи вызывается `await session.delete(family)` без обнуления `current_user.family_group_id = None`. Кнопки удаления аккаунта в MiniApp и команды `/delete_account` в боте нет.
   - **`AIRateLimiter` остаётся мёртвым кодом:** класс объявлен в `src/services/ai_service.py`, но `ai_rate_limiter.check_and_record()` нигде в `src/` не вызывается (0 вызовов). На `POST /api/v1/family/join` также нет rate limiting.
   - **Команда `/facts` в `smart-bujet-dev`:** зарегистрирована в меню бота (`src/main.py:80`), но обработчика `Command("facts")` в `src/bot/handlers/` нет (бот просто игнорирует нажатие).
   - **Экран согласия с Политикой конфиденциальности при `/start`:** отсутствует.

---

## 2. Аудит загрузки банковских выписок в `smart-bujet-dev` (коммит `d819165`)

### 2.1. Пять фатальных ошибок исполнения (Runtime Crashes & Regressions)
Разработчик проверил `BankStatementService` только unit-тестом `tests/test_bank_statement_import.py:47-134`, в котором полностью замокал `session`, `CategoryService`, `TransactionService` и `parse_single_pdf` через `AsyncMock`. **В реальном рантайме фича не работает вообще (падает со 100% вероятностью в 4 разных местах) и ломает распознавание PDF-чеков для всех пользователей:**

1. **[FATAL CRASH #1] `AttributeError: 'CategoryService' object has no attribute 'get_all_categories'`:**
   - В `BankStatementService.import_statements` (`src/services/bank_statement_service.py:117-118`) вызывается:
     ```python
     cat_service = CategoryService(self.session)
     categories = await cat_service.get_all_categories()
     ```
   - В классе `CategoryService` (`src/services/category_service.py:34-91`) **метода `get_all_categories()` НЕ СУЩЕСТВУЕТ** (реальный метод называется `get_categories(user_id=..., cat_type=...)`). При нажатии кнопки `✅ Готово, обработать` (`statement:process` в `src/bot/handlers/start.py:283`) бот немедленно падает с `AttributeError`!
2. **[FATAL CRASH #2] `NameError: name 'asyncio' is not defined` при вызове Gemini:**
   - В `BankStatementService.parse_single_pdf` (`src/services/bank_statement_service.py:88`) вызывается `await asyncio.to_thread(self.client.models.generate_content, ...)`.
   - Однако в начале файла `src/services/bank_statement_service.py:1-28` **пропущен `import asyncio`**! Любой реальный вызов `parse_single_pdf` падает с `NameError: name 'asyncio' is not defined` (перехватывается в `except Exception` на строке 98 и всегда возвращает пустой список транзакций `[]`).
3. **[FATAL CRASH #3] `NotNullViolationError` на колонке `transactions.source` при `session.commit()`:**
   - В `BankStatementService.import_statements` (`src/services/bank_statement_service.py:229-239`) создаётся `Transaction(...)` **без передачи поля `source`**.
   - В модели `Transaction.source` (`src/models/transaction.py:48`) и в таблице `transactions` в PostgreSQL колонка `source` имеет ограничение **`NOT NULL` без дефолта** (а в `TransactionSource` enum даже не добавлено значение `statement`). На строке 259 (`await self.session.commit()`) база данных выбрасывает `IntegrityError: null value in column "source" violates not-null constraint`.
4. **[FATAL CRASH #4] `DataError` в `asyncpg` из-за `tzinfo=timezone.utc` в `created_at` (`TIMESTAMP WITHOUT TIME ZONE`):**
   - В `BankStatementService.import_statements` (`src/services/bank_statement_service.py:185-191`) дата парсится с `tzinfo=timezone.utc` (offset-aware) и на строке 236 передаётся в `created_at=item["date"]`.
   - В БД (`\d+ transactions`) и `TimestampMixin` (`src/models/base.py:14`) колонка `created_at` имеет тип `timestamp without time zone` (offset-naive). При попытке вставки `asyncpg` выбрасывает `DataError: can't subtract offset-naive and offset-aware datetimes`.
5. **[FATAL REGRESSION #5] Хэндлер `@router.message(F.document)` в `start.py` сломал загрузку PDF-чеков для всех активных пользователей:**
   - В `src/bot/bot.py:31-36` роутер `start.router` зарегистрирован **первым** (строка 31), а `photo_tx.router` — **шестым** (строка 36).
   - В `src/bot/handlers/start.py:208-240` декоратор `@router.message(F.document)` объявлен без фильтров состояния и перехватывает **любой** документ от любого пользователя.
   - Когда активный пользователь (у которого `initial_balance` уже задан) отправляет боту PDF-чек покупки, `handle_statement_pdf_upload` доходит до конца функции и возвращает `None`. В `aiogram 3.x` возврат `None` из сработавшего хэндлера **останавливает распространение апдейта**, поэтому `process_document_receipt` в `src/bot/handlers/photo_tx.py:141` **больше никогда не вызывается**!
   - При этом созданный разработчиком файл `src/bot/states.py:1-8` (`OnboardingStates`) **вообще нигде не импортируется и не используется** (очередной мёртвый код).

---

### 2.2. Уязвимости безопасности и ПДн в загрузке банковских выписок

1. **[CRITICAL PRIVACY LEAK] Отправка сырых PDF банковских выписок со всеми ПДн напрямую в Google Gemini в обход `PIIGuardrailService`:**
   - В `BankStatementService.parse_single_pdf` (`src/services/bank_statement_service.py:87-92`) байты PDF (`types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf")`) отправляются **напрямую в облако Google Gemini** без локального извлечения текста и без маскирования через `PIIGuardrailService`.
   - Банковская выписка (Kaspi Gold, Halyk, Forte, Сбер, Тинькофф) содержит: полное ФИО владельца счёта, ИИН/ИНН, полный номер счёта IBAN (`KZ...`), номер карты, адрес/телефон, точные остатки по счетам и **полные ФИО/имена всех получателей и отправителей P2P-переводов**.
   - Более того, промпт (`src/services/bank_statement_service.py:63`) требует записывать имя контрагента/получателя перевода в `item_name`. В результате ФИО всех людей, которым пользователь переводил деньги (*«Айгерим К.»*, *«Серик М.»*), сохраняются в таблице `transactions.item_name` **в открытом виде (`plaintext`)**!
   - При ошибке парсинга JSON функция `clean_gemini_json` (`src/services/bank_statement_service.py:37`) также пишет первые 200 символов ответа выписки в `logger.warning` (в stdout контейнера).
2. **[HIGH] Уязвимость к DoS / OOM (Out-Of-Memory) и исчерпанию квот Gemini:**
   - **Отсутствует проверка размера файла и лимит количества файлов:** В `handle_statement_pdf_upload` (`src/bot/handlers/start.py:209-239`) и `on_statement_process` (`:243-280`) нет проверки `doc.file_size` (в отличие от `photo_tx.py:151`) и нет лимита на длину списка `STATEMENT_BUFFER[user_id]`.
   - **Одновременная загрузка всех PDF в RAM:** На строках `src/bot/handlers/start.py:270-273` все файлы из буфера скачиваются в оперативную память одновременно (`downloaded.append((file_name, buf.getvalue()))`). При лимите контейнера в **240 MiB RAM** отправка 10–15 PDF по 15–20 МБ убьёт бэкенд через **Linux OOM Killer**.
   - **Утечка памяти в глобальном словаре `STATEMENT_BUFFER`:** Словарь `STATEMENT_BUFFER: dict[int, list[tuple[str, str]]] = defaultdict(list)` (`src/bot/handlers/start.py:37`) хранится в RAM бесконечно: если пользователь загрузил PDF и не нажал кнопку обработки, записи никогда не удаляются (нет TTL).
   - **Отсутствие `AIRateLimiter` и таймаутов:** В `import_statements` (`src/services/bank_statement_service.py:130-131`) цикл `for filename, pdf_bytes in files:` вызывает Gemini без `AIRateLimiter` и без ограничения числа страниц.
3. **[HIGH] Race Condition при двойном клике и полное отсутствие дедупликации (идемпотентности):**
   - **Гонка при двойном нажатии кнопки `✅ Готово, обработать`:** В `on_statement_process` (`src/bot/handlers/start.py:245-294`) очистка буфера `STATEMENT_BUFFER.pop(user_id, None)` происходит только на **строке 294** — *после* скачивания всех файлов и завершения всех запросов к Gemini (что занимает 10–30 секунд). Если пользователь нажмёт кнопку дважды, оба запроса параллельно обработают один и тот же буфер и **запишут все транзакции в БД дважды**!
   - **Забыта дедупликация транзакций:** Хотя в архитектурном документе (`C:\Users\aanto\code-vault\smart_bujet_prod_security_dev_statements_architecture.md:244`) разработчик описал дедупликацию по ключу `(date[:10], amount, item_name_normalized)`, в реальном коде `BankStatementService.import_statements` (`src/services/bank_statement_service.py:171-245`) **никакой дедупликации нет вообще** — ни внутри пачки выписок, ни против уже существующих в БД транзакций!
4. **[MEDIUM] Ошибки финансовой логики, `/reset`, категорий, семейного бюджета и HTML-инъекции:**
   - **Опасная команда `/reset` без подтверждения:** В `src/bot/handlers/start.py:83-98` команда `/reset` доступна любому пользователю и без подтверждения удаляет все его `Transaction`, но оставляет нетронутыми `AssetAccount` и `CreditAccount`, разрушая консистентность балансов.
   - **Рассинхрон категорий промпта с БД:** В промпте (`src/services/bank_statement_service.py:64`) указаны категории `'Кафе и рестораны'`, `'Коммунальные услуги'`, `'Связь'`, которых **нет** в системном справочнике `DEFAULT_CATEGORIES` (`src/services/category_service.py:6-31`, где используются `'Еда вне дома'` и `'Обязательные расходы'`). Из-за этого все рестораны, связь и коммуналка из выписки не находятся в `cat_map` и попадают в `'Прочее'`.
   - **Коллизия `cat_map` по имени категории без учёта `CategoryType`:** В `src/services/bank_statement_service.py:119` словарь строится как `{c.name.lower(): c for c in categories}`. Категория `"Денежный перевод"` существует в 4 типах (`expense`, `income`, `transfer_out`, `transfer_in`), поэтому в `cat_map` перезаписывается только один тип, и расходная транзакция привязывается к категории чужого типа.
   - **Искажение аналитики внутренними переводами на депозит:** Промпт (`src/services/bank_statement_service.py:62`) заставляет классифицировать любую операцию только как `expense` или `income`. В итоге переводы между своей картой (Kaspi Gold) и своим депозитом (Kaspi Депозит) записываются как доходы и расходы, раздувая аналитику.
   - **Неверный расчёт `initial_balance` при нескольких выписках или отсутствии `closing_balance`:** На строках `src/services/bank_statement_service.py:161-168, 251-258` берётся `latest_closing_balance` только от одного банка, но из него вычитается `net_cashflow` **всех** загруженных банков; а если `closing_balance` равен `None`, `initial_balance` принудительно ставится в `0.0`, уводя баланс в минус.
   - **Потеря `family_group_id` и `user_item_aliases`:** Транзакции из выписки создаются без `family_group_id=user.family_group_id` (`src/services/bank_statement_service.py:229-238`) и не видны в семейном бюджете, а таблица привычек `user_item_aliases` не пополняется.
   - **Неэкранированный HTML и риск Prompt Injection:** В `src/bot/handlers/start.py:234` (`file_name`) и `:300` (`banks_str`) строки вставляются в HTML-сообщение без `html.escape()`. В `parse_single_pdf` (`src/services/bank_statement_service.py:88-92`) не задан `GenerateContentConfig(response_mime_type="application/json")` и нет защиты от Prompt Injection через текст назначения платежа.

---

## 3. Аудит персонализации (`user_agent_memories`) в `smart-bujet-dev`

1. **Что сделано правильно (✅):**
   - В `src/api/v1/facts.py:48-132` все операции чтения, обновления (`PATCH /{fact_id}`) и удаления (`DELETE /{fact_id}`) проверяют `fact.user_id != current_user.id` (IDOR отсутствует).
   - В `src/static/app.js:2111-2116` для рендеринга карточек используется `textContent` (DOM XSS отсутствует).
2. **Что упущено или уязвимо (⚠️):**
   - `UserAgentMemory.fact_text` (`src/models/agent_memory.py:31`) хранится в БД в открытом виде (`plaintext`) без `EncryptedString`.
   - При классификации факта (`AIService.classify_user_fact` в `src/services/ai_service.py:559-596`) и генерации совета (`AIService.generate_financial_advice` в `:421-485`) `fact_text` отправляется в Gemini **в обход `PIIGuardrailService.mask_text`**.
   - **Prompt Injection и спам:** На `POST /api/v1/facts/` (`src/api/v1/facts.py:57-88`) не вызывается `ai_rate_limiter` и нет лимита на максимальное количество фактов у пользователя (например, не более 50 фактов). В `src/bot/handlers/summary.py:202-235` выборка фактов не ограничена `.limit()`, а в `ai_service.py:428-437, 580` пользовательский `fact_text` конкатенируется в промпт без XML-тега/экранирования.
   - В авто-отчётах по расписанию (`src/core/report_scheduler.py:116`) факты не передаются в `generate_financial_advice`, а команда `/facts` в боте (`src/main.py:80`) не имеет хэндлера.

---

## 4. Блок 4 (Дополнение к ТЗ): что агент ОБЯЗАН исправить в `smart-bujet-dev` по выпискам и персонализации

В дополнение к **Блокам 1, 2 и 3** (которые должны быть выполнены на 100% как в Prod, так и в Dev), в `smart-bujet-dev` необходимо выполнить:

1. **Устранить все 5 фатальных крашей и регрессий импорта выписок:**
   - В `src/services/bank_statement_service.py`:
     - Добавить `import asyncio` в начало файла.
     - Заменить несуществующий вызов `await cat_service.get_all_categories()` на `await cat_service.get_categories(user_id=user.id)`.
     - Строить индекс категорий с учётом типа: `cat_map = {(c.name.lower(), c.type.value): c for c in categories}`, а список названий категорий в промпте формировать динамически из реальных категорий БД (чтобы не было несуществующих `'Кафе и рестораны'` вместо `'Еда вне дома'`).
     - Добавить значение `statement = "statement"` в `TransactionSource` (`src/models/transaction.py:23-27`) и передавать `source=TransactionSource.statement.value` и `family_group_id=user.family_group_id` при создании `Transaction` в `import_statements`.
     - Приводить `item["date"]` к naive UTC (`dt.replace(tzinfo=None)`) перед записью в `created_at` (`TIMESTAMP WITHOUT TIME ZONE`).
   - В `src/bot/handlers/start.py`:
     - Повесить на `handle_statement_pdf_upload` строгий фильтр состояния FSM (`OnboardingStates.waiting_for_statement`) либо проверять фильтр на уровне декоратора роутера, чтобы обычные PDF-чеки активных пользователей беспрепятственно проходили в `src/bot/handlers/photo_tx.py:141`!
2. **Обеспечить защиту ПДн (`PIIGuardrailService` + локальный парсинг PDF) при загрузке выписок:**
   - **Не отправлять сырой PDF-файл в Gemini целиком!** Извлекать текст из PDF локально в памяти на сервере (через `pypdf` / `pymupdf` / `pdfplumber`), прогонять извлечённый текст через `PIIGuardrailService.mask_text(..., known_names=known_names)` (плюс регулярное выражение для маскирования ФИО вида `Фамилия И.` / `Имя О.` в строках переводов) и отправлять в Gemini **только обезличенный текст**.
   - Для P2P-переводов не сохранять ФИО контрагентов в БД: записывать обобщённое `item_name = "Перевод клиенту банка"` / `"Пополнение переводом"`, которое затем шифруется через `EncryptedString` (`AES-256-GCM`).
   - Убрать логирование сырого ответа Gemini из `clean_gemini_json` (`src/services/bank_statement_service.py:37`).
3. **Защитить загрузку выписок от DoS / OOM, Race Condition и дублирования:**
   - Ограничить размер одного PDF-файла до `5 МБ` (`doc.file_size <= 5 * 1024 * 1024`), количество файлов за одну загрузку — до `3 файлов`, количество страниц — до `20 страниц`.
   - Скачивать файлы по одному непосредственно перед парсингом (после чего освобождать буфер байтов), не держа все PDF в RAM одновременно.
   - В `on_statement_process` (`src/bot/handlers/start.py:245`) атомарно забирать буфер `file_entries = STATEMENT_BUFFER.pop(user_id, None)` **в самом начале функции** (до `await`), чтобы двойное нажатие кнопки не запускало параллельный повторный импорт.
   - Подключить `ai_rate_limiter.check_and_record(user_id)` перед каждым вызовом Gemini.
   - Реализовать реальную дедупликацию транзакций при импорте: как внутри загружаемого батча, так и против уже существующих транзакций пользователя в БД за этот период (по дате, сумме и типу/нормализованному названию).
   - Исключать внутренние переводы между собственными счетами/депозитами (напр., `"Перевод на Kaspi Депозит"`, `"С Kaspi Депозита"`) из `expense`/`income`, чтобы не искажать статистику доходов и расходов.
   - Защитить команду `/reset` в `start.py:83-98`: либо ограничить её только dev-режимом с двухшаговым подтверждением (и полным сбросом всех связанных счетов), либо объединить с полноценным `/delete_account`.
   - Экранировать `html.escape(file_name)` и `html.escape(banks_str)` в `src/bot/handlers/start.py:234, 300` и использовать `GenerateContentConfig(response_mime_type="application/json")` в `parse_single_pdf`.
4. **Написать честный интеграционный тест импорта выписки:**
   - В `tests/test_bank_statement_import.py` добавить интеграционный тест с реальной тестовой БД (`AsyncSession`) и реальным `CategoryService` (замокав только сетевой вызов `self.client.models.generate_content`), который проверяет сохранение `Transaction` в БД и ловлю всех constraint/type ошибок.


---

# Четвёртый аудит (Re-Audit #4: Prod `17424f1` + Dev `0e9bd43`)

Дата проверки: `2026-10-22`
Проверенные коммиты:
- **Prod (`C:\Users\aanto\smart-bujet` и `/home/ag_admin/smart-bujet`):** `17424f1`
- **Dev (`C:\Users\aanto\smart-bujet-dev` и `/home/ag_admin/smart-bujet-dev`):** `0e9bd43`
- **Боевой сервер `85.198.89.188`:** контейнеры `smart_bujet_backend`, `smart_bujet_backend_dev`, `postgres_dg_improve` (базы `smart_bujet` и `smart_bujet_dev`), `hashicorp_vault`.

---

## 1. Что реально исправлено и работает на проде и в деве (~75% объёма) ✅

1. **БД `smart_bujet` (Prod) зашифрована и обезличена (`AES-256-GCM` + `HMAC-SHA256`):**
   - В `src/core/security.py:68-130` реализованы `EncryptedString`, `EncryptedText` (`AES-256-GCM` со случайным 12-байтным `nonce` и префиксом `enc:v1:`) и `blind_index()` (`HMAC-SHA256`).
   - В боевой БД `smart_bujet` все 196 строк `transactions.item_name`, 5 строк `asset_accounts.name`, 2 строки `credit_accounts.name`/`bank_name` и `users.first_name` зашифрованы (`0` открытых записей).
   - Все 144 строки `user_item_aliases.item_name_normalized` переведены в 64-символьные хеши `HMAC-SHA256`.
   - Поле `users.username` очищено (`NULL`), название семьи в `family_groups` изменено с `'Семья Anton'` на `'Семейный бюджет'`, а в `TransactionService.process_voice` (`src/services/transaction_service.py:748`) отключено сохранение `raw_text` (`raw_text=None`).
2. **Настройки СУБД, `ufw` и ночные зашифрованные бэкапы (`age`):**
   - Межсетевой экран `ufw` включён (`Status: active`, `Default: deny (incoming)`).
   - В `pg_hba.conf` внутри `postgres_dg_improve` удалены все правила `trust`; для локальных и Docker-сетей выставлен `scram-sha-256`, а для `0.0.0.0/0` и `::/0` — `reject`.
   - Лимит `max_connections` в PostgreSQL увеличен до `100` (`SHOW max_connections;` = `100`), а пул в `src/core/database.py:14-21` выставлен в `pool_size=5, max_overflow=10`.
   - В `crontab` пользователя `ag_admin` добавлено задание `0 3 * * * /home/ag_admin/scripts/backup_smart_bujet.sh`, создающее зашифрованные `.dump.age` архивы в `/home/ag_admin/backups/`, старые незашифрованные `.sql.gz` удалены.
3. **Каскадное удаление (`ON DELETE CASCADE`), `AIRateLimiter` и команда `/facts`:**
   - Во всех 7 зависимых таблицах (`asset_accounts`, `categories`, `credit_accounts`, `scheduled_report_logs`, `transactions`, `user_agent_memories`, `user_item_aliases`) и в моделях, и в обеих живых БД (`smart_bujet`, `smart_bujet_dev`) прописан `ON DELETE CASCADE`.
   - Вызов `ai_rate_limiter.check_and_record(user_id)` встроен во все основные методы `AIService` (`classify_text`, `parse_voice`, `parse_receipt_media`, `generate_financial_advice`), добавлен перехват `AIRateLimitExceededError` в хэндлерах бота и rate limit `_check_join_rate_limit` на `POST /api/v1/family/join` (`src/api/v1/family.py:17-63`).
   - В `smart-bujet-dev` создан и подключён рабочий хэндлер `/facts` (`src/bot/handlers/facts.py:23-56`).
4. **Исправления в `BankStatementService` (`smart-bujet-dev`):**
   - Добавлен `import asyncio` (`src/services/bank_statement_service.py:3`), исправлен вызов `cat_service.get_categories(user_id=user.id)` (`:169`), добавлен `family_group_id=user.family_group_id` (`:327`), приведение `created_at` к naive UTC (`:323, 333`), атомарный `STATEMENT_BUFFER.pop(user_id, None)` в начале `on_statement_process` (`src/bot/handlers/start.py:243`), экранирование `html.escape()` (`:230, 292`), внутрипакетная дедупликация (`seen_batch`) и лимит `5 МБ` на файл.

---

## 2. Что осталось сломанным или недоделанным (Обязательный чек-лист доработок) ❌

### 2.1. [FATAL CRASH В DEV] В PostgreSQL в типе `ENUM transactionsource` отсутствует значение `'statement'`
* **Где проблема:** В Python-модели (`src/models/transaction.py:29`) добавлено `statement = "statement"`, и в `bank_statement_service.py:334` выставляется `source=TransactionSource.statement`. Но в самой СУБД PostgreSQL (`smart_bujet_dev` и `smart_bujet`) команда `SELECT enum_range(NULL::transactionsource);` возвращает только **`{text,voice,photo,manual}`**!
* **Последствие:** Любой импорт банковской выписки падает на `await self.session.commit()` (`src/services/bank_statement_service.py:356`) с фатальной ошибкой `asyncpg.exceptions.InvalidTextRepresentationError: invalid input value for enum transactionsource: "statement"`.
* **Что сделать:** Выполнить в обеих базах (`smart_bujet_dev` и `smart_bujet`) SQL-команду:
  ```sql
  ALTER TYPE transactionsource ADD VALUE IF NOT EXISTS 'statement';
  ```
  и добавить эту проверку в стартовую миграцию `src/main.py`.

### 2.2. [CRITICAL PRIVACY BUG В DEV] Пакет `pypdf` не добавлен в `requirements.txt` и не установлен в контейнере — PDF выписок на 100% уходят в Gemini сырыми!
* **Где проблема:**
  1. В `src/services/bank_statement_service.py:28-31` написано `try: import pypdf except ImportError: pypdf = None`.
  2. При этом в `requirements.txt` (и `pyproject.toml`) библиотека `pypdf` **отсутствует**, а внутри контейнера `smart_bujet_backend_dev` вызов `import pypdf` падает с `ModuleNotFoundError: No module named 'pypdf'`.
  3. Из-за этого `extract_and_redact_pdf_text` (`src/services/bank_statement_service.py:53-54`) **всегда** возвращает `("", True)` и на строке `:131` **в 100% случаев отправляет сырой PDF со всеми ПДн (ФИО, ИИН, IBAN, ФИО контрагентов) напрямую в Google Gemini**!
  4. Более того, сама функция `extract_and_redact_pdf_text` (`:63-68`) маскирует только IBAN, карты и 12 цифр, но **не вызывает `PIIGuardrailService.mask_text()`** и **не маскирует ФИО владельца и ФИО контрагентов по P2P-переводам**.
* **Что сделать:**
  1. Добавить `pypdf>=4.0.0` в `requirements.txt` и `pyproject.toml`, пересобрать Docker-образ `smart_bujet_backend_dev` и убедиться, что `docker exec smart_bujet_backend_dev python -c "import pypdf"` выполняется без ошибок.
  2. В `extract_and_redact_pdf_text` прогонять извлечённый текст через `PIIGuardrailService.mask_text(text, known_names=known_names)` и дополнительно маскировать регулярным выражением ФИО в строках переводов (вида `Фамилия И.` / `Имя О.` -> `[PERSON]`), а также подключить `ai_rate_limiter.check_and_record(user_id)` в `parse_single_statement` и фильтрацию внутренних переводов между своими счетами/депозитами в `STATEMENT_SYSTEM_PROMPT`.

### 2.3. [CRITICAL BUG В DEV] Обычный `return` в `@router.message(F.document)` (`start.py:209-214`) всё ещё блокирует загрузку PDF-чеков!
* **Где проблема:** В `src/bot/handlers/start.py:209-214` написано:
  ```python
  @router.message(F.document)
  async def handle_statement_document(message: Message, session: AsyncSession) -> None:
      user_id = message.from_user.id
      if user_id not in STATEMENT_BUFFER:
          return
  ```
* **Почему это не работает:** В `aiogram 3.x` декоратор `@router.message(F.document)` срабатывает на **любой** документ, а возврат `return` (`None`) из хэндлера сигнализирует диспетчеру, что событие обработано, и **останавливает дальнейший обход роутеров**. До `process_document_receipt` в `src/bot/handlers/photo_tx.py:143` обычные PDF-чеки никогда не доходят!
* **Что сделать:** Вынести проверку `user_id in STATEMENT_BUFFER` непосредственно в фильтр декоратора:
  ```python
  @router.message(F.document, F.from_user.id.func(lambda uid: uid in STATEMENT_BUFFER))
  ```
  либо выбрасывать `raise SkipHandler()` (`from aiogram.dispatcher.event.bases import SkipHandler`).

### 2.4. [FATAL CRASH В DEV] Падение `TypeError` при нажатии «Личная / Семейная сводка» в боте
* **Где проблема:** В `src/services/ai_service.py:432-436` параметр метода `generate_financial_advice` переименовали из `facts` в `user_facts: list[str] | None = None` (под `report_scheduler.py`), но в `src/bot/handlers/summary.py:214` и `:242` оставили старый вызов:
  ```python
  advice = await ai_service.generate_financial_advice(summary, facts=user_facts)
  ```
* **Последствие:** При запросе сводки в Dev-боте происходит 100% падение `TypeError: AIService.generate_financial_advice() got an unexpected keyword argument 'facts'`.
* **Что сделать:** В `src/bot/handlers/summary.py:214, 242` заменить `facts=user_facts` на `user_facts=user_facts` (а в `generate_financial_advice` и `classify_user_fact` также добавить вызов `PIIGuardrailService.mask_text` для `user_facts` и `ai_rate_limiter.check_and_record`).

### 2.5. [CRITICAL — КЛЮЧИ ШИФРОВАНИЯ] В `.env` на сервере не заданы `DATA_ENCRYPTION_KEY` и `BLIND_INDEX_SECRET`
* **Где проблема:** В `/home/ag_admin/smart-bujet/.env` и `/home/ag_admin/smart-bujet-dev/.env` переменные `DATA_ENCRYPTION_KEY` и `BLIND_INDEX_SECRET` отсутствуют. Из-за этого `src/core/security.py:48-53, 126-130` использует фоллбэк `hashlib.sha256(settings.bot_token.encode()).digest()`.
* **Последствие:** Все данные в боевой БД `smart_bujet` сейчас зашифрованы производным от `BOT_TOKEN` ключом. Если когда-либо перевыпустить `BOT_TOKEN` в `@BotFather`, **вся база данных и все 144 алиаса станут нечитаемыми навсегда!**
* **Что сделать:**
  1. Вычислить текущий hex/base64 ключ `sha256(BOT_TOKEN)` и явно записать его в `DATA_ENCRYPTION_KEY` и `BLIND_INDEX_SECRET` в `/home/ag_admin/smart-bujet/.env` и `/home/ag_admin/smart-bujet-dev/.env`, чтобы отвязать шифрование БД от токена Telegram-бота без потери уже зашифрованных данных.
  2. Убрать из `src/core/security.py:51` хардкод-фоллбэк `"smart_bujet_default_secure_vault_seed_2026"`.

### 2.6. [HIGH — СЕРВЕР] Обход `ufw` через Docker (`0.0.0.0:5432` и `0.0.0.0:8200`) и приватный ключ бэкапов на сервере
* **Где проблема:**
  1. Контейнеры `postgres_dg_improve` (`0.0.0.0:5432`) и `hashicorp_vault` (`0.0.0.0:8200`) пробрасывают порты через цепочку `iptables DOCKER` **до** правил `ufw`. Из-за этого порт `8200` (`hashicorp_vault`) по-прежнему полностью открыт в интернет!
  2. В `/home/ag_admin/.age/key.txt` на самом сервере лежит **приватный ключ** `AGE-SECRET-KEY-...` от бэкапов (в случае компрометации сервера атакующий расшифрует все бэкапы этим ключом).
  3. Скрипт `/home/ag_admin/scripts/backup_smart_bujet.sh` с паролем от БД имеет права `0775` (доступен на чтение всем пользователям).
* **Что сделать:**
  1. Пересоздать контейнеры `postgres_dg_improve` и `hashicorp_vault` с биндингом портов строго на `127.0.0.1:5432:5432` и `127.0.0.1:8200:8200`.
  2. В скрипте бэкапа использовать только публичный ключ (`age -r age1...`), а приватный ключ из `/home/ag_admin/.age/key.txt` сохранить локально у владельца и удалить с сервера.
  3. Выполнить `chmod 700 /home/ag_admin/scripts/backup_smart_bujet.sh`.

### 2.7. [MEDIUM — РЕГРЕССИИ В МОДЕЛЯХ, UI И ТЕСТАХ]
1. **Пропал `@property def asset_currency` из `Transaction` (`src/models/transaction.py:60`):**
   - При редактировании модели случайно удалили свойство `asset_currency`, из-за чего в MiniApp (`src/static/app.js:1744`) все переводы на вклады отображаются в `$ USD` вместо валюты счёта. Вернуть `@property def asset_currency(self) -> str | None: return self.asset_account.currency if self.asset_account else None` в Prod и Dev.
2. **Дублирование хэндлеров в Prod `start.py`, пропуск в Dev `start.py` и отсутствие кнопки удаления в MiniApp:**
   - В Prod (`src/bot/handlers/start.py:175-347`) функции `on_privacy_accept`, `cmd_delete_account`, `on_delete_cancel`, `on_delete_confirm` продублированы в файле дважды подряд — удалить дубликаты.
   - В Dev (`src/bot/handlers/start.py`) перенести `on_privacy_accept` и `/delete_account`.
   - Добавить кнопку **«🗑 Удалить аккаунт и все данные»** в интерфейс MiniApp (`src/static/index.html`, `src/static/app.js` -> `DELETE /api/v1/auth/me`).
3. **Убрать оставшуюся запись `username` и починить сломанный тест:**
   - В `src/bot/handlers/text_tx.py:40` (Prod и Dev) и `src/bot/handlers/start.py:112, 117` (Dev) заменить `username=message.from_user.username` на `username=None` и очистить `UPDATE users SET username = NULL;` в БД `smart_bujet_dev`.
   - Обновить ассерт количества рядов кнопок в `tests/test_tx_toggle_and_learning.py:59` (`3` вместо `2` после добавления кнопки «📋 Вернуться в меню»).
