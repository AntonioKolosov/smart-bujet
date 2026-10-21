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
