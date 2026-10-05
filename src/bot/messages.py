import html
from typing import Any, List, Union
from src.models.transaction import Transaction
from src.models.category import CategoryType

CURRENCY_SYMBOLS: dict[str, str] = {
    "KZT": "₸",
    "RUB": "₽",
    "USD": "$",
    "EUR": "€",
}


def esc(value: Any) -> str:
    """Escapes user/AI text safely for Telegram HTML parse mode."""
    if value is None:
        return ""
    return html.escape(str(value), quote=False)


def get_currency_symbol(currency_code: str | None) -> str:
    if not currency_code:
        return "₽"
    return CURRENCY_SYMBOLS.get(currency_code.upper(), currency_code)


def format_amount(amount: float, currency_code: str | None) -> str:
    symbol = get_currency_symbol(currency_code)
    formatted = f"{amount:,.2f}".replace(",", " ")
    return f"{formatted} {symbol}"


class BotMessages:
    @staticmethod
    def tx_success(
        transactions: Union[List[Transaction], Transaction],
        currency: str = "RUB",
        current_balance: float | None = None
    ) -> str:
        if not transactions:
            return "✅ <b>Записано!</b>"

        tx_list: List[Transaction] = [transactions] if isinstance(transactions, Transaction) else transactions
        if not tx_list:
            return "✅ <b>Записано!</b>"

        balance_suffix = ""
        if current_balance is not None:
            balance_suffix = f"\n\n💳 <b>Остаток на счёте: {format_amount(current_balance, currency)}</b>"

        # Case 1: Single item formatting
        if len(tx_list) == 1:
            tx = tx_list[0]
            if tx.type == CategoryType.transfer_out:
                icon = "🏦"
                type_label = "Перевод в депозит/актив"
            elif tx.type == CategoryType.transfer_in:
                icon = "🏦"
                type_label = "Вывод из актива"
            elif tx.type == CategoryType.income:
                icon = "💰"
                type_label = "Доход"
            else:
                icon = "💸"
                type_label = "Расход"

            cat_name = esc(tx.category.name if tx.category else "Общее")

            amount_str = f"<b>{format_amount(tx.amount, currency)}</b>"
            if tx.asset_amount:
                amount_str += f" (<b>{tx.asset_amount:g} у.е.</b>)"
            discount_line = ""
            if tx.discount_amount and tx.discount_amount > 0 and tx.original_amount:
                amount_str += f" <s>{format_amount(tx.original_amount, currency)}</s>"
                discount_line = f"\n🏷️ <b>Скидка</b>: -{format_amount(tx.discount_amount, currency)}"

            return (
                f"✅ <b>Записано!</b>\n\n"
                f"{icon} <b>{type_label}</b>: {amount_str}{discount_line}\n"
                f"📌 Позиция: <b>{esc(tx.item_name)}</b>\n"
                f"📁 Категория: <b>{cat_name}</b>"
                f"{balance_suffix}"
            )

        # Case 2: Multi-item batch formatting
        lines = [f"✅ <b>Записано ({len(tx_list)} поз.)!</b>\n"]
        total_expense = 0.0
        total_income = 0.0
        total_discount = 0.0

        for i, tx in enumerate(tx_list, start=1):
            icon = "💸" if tx.type == CategoryType.expense else "💰"
            cat_name = esc(tx.category.name if tx.category else "Общее")
            if tx.discount_amount and tx.discount_amount > 0 and tx.original_amount:
                lines.append(
                    f"{i}. {icon} <b>{esc(tx.item_name)}</b> — {format_amount(tx.amount, currency)} "
                    f"<s>{format_amount(tx.original_amount, currency)}</s> (<i>{cat_name}</i>)"
                )
                total_discount += float(tx.discount_amount)
            else:
                lines.append(f"{i}. {icon} <b>{esc(tx.item_name)}</b> — {format_amount(tx.amount, currency)} (<i>{cat_name}</i>)")

            if tx.type == CategoryType.expense:
                total_expense += float(tx.amount)
            else:
                total_income += float(tx.amount)

        lines.append("")
        if total_discount > 0:
            lines.append(f"🏷️ Общая скидка: <b>-{format_amount(total_discount, currency)}</b>")

        if total_expense > 0 and total_income > 0:
            lines.append(f"💸 Итого расходов: <b>{format_amount(total_expense, currency)}</b>")
            lines.append(f"💰 Итого доходов: <b>{format_amount(total_income, currency)}</b>")
        elif total_expense > 0:
            lines.append(f"💰 <b>К оплате: {format_amount(total_expense, currency)}</b>")
        else:
            lines.append(f"💰 <b>Итого: {format_amount(total_income, currency)}</b>")

        if current_balance is not None:
            lines.append(f"\n💳 <b>Остаток на счёте: {format_amount(current_balance, currency)}</b>")

        return "\n".join(lines)

    @staticmethod
    def receipt_batch_success(
        receipts: list[dict[str, Any]],
        total_operations: int,
        total_amount: float,
        currency: str = "RUB",
        current_balance: float | None = None
    ) -> str:
        lines = [f"🧾 <b>Обработано чеков: {len(receipts)}</b>\n"]
        for i, r in enumerate(receipts, start=1):
            title = esc(r.get("title", f"Чек {i}"))
            amt = format_amount(r.get("total_amount", 0.0), currency)
            if title and title.lower() != "чек" and not title.lower().startswith(f"чек {i}"):
                lines.append(f"• Чек {i}: <b>{title}</b> ({amt})")
            else:
                lines.append(f"• Чек {i} ({amt})")

        lines.append("")
        lines.append(f"💰 <b>Всего добавлено операций: {total_operations} на сумму: {format_amount(total_amount, currency)}</b>")
        if current_balance is not None:
            lines.append(f"💳 <b>Текущий баланс: {format_amount(current_balance, currency)}</b>")

        return "\n".join(lines)

    @staticmethod
    def voice_clarification(recognized_text: str | None = None) -> str:
        if recognized_text:
            return (
                f"🎙️ Я распознал: «<i>{esc(recognized_text)}</i>», но не понял точную сумму.\n\n"
                f"<b>Повтори, пожалуйста!</b> Назови сумму и покупку, например:\n"
                f"• <i>«Кофе 250 рублей»</i>\n"
                f"• <i>«Такси 450»</i>\n"
                f"• <i>«Обед 600»</i>"
            )
        return (
            "🎙️ Не удалось разобрать аудиозапись или определить сумму.\n\n"
            "<b>Повтори, пожалуйста!</b> Скажи чётче, например:\n"
            "• <i>«Продукты 1500»</i>\n"
            "• <i>«Заправка 2000 рублей»</i>"
        )

    @staticmethod
    def text_clarification() -> str:
        return (
            "❓ Не удалось определить сумму.\n\n"
            "<b>Повтори, пожалуйста!</b> Укажи сумму и категорию, например:\n"
            "• <i>«Кофе 300»</i>\n"
            "• <i>«450 обед»</i>\n"
            "• <i>«Продукты 1200 руб»</i>"
        )

    @staticmethod
    def photo_clarification() -> str:
        return (
            "🧾 Не удалось распознать сумму в чеке.\n\n"
            "<b>Повтори, пожалуйста!</b> Сделай фото чека при хорошем освещении или введи трату текстом, например:\n"
            "• <i>«Пятёрочка 1240»</i>"
        )

    @staticmethod
    def off_topic_warning(content_type: str = "text") -> str:
        if content_type == "photo":
            return (
                "🛡️ <b>На фотографии не обнаружен чек или квитанция.</b>\n\n"
                "Я — финансовый ассистент Smart Bujet и обрабатываю только кассовые чеки и платежные документы.\n"
                "Пожалуйста, отправьте фотографию чека или введите трату текстом (например: <i>«Кофе 300»</i>)."
            )
        elif content_type == "voice":
            return (
                "🛡️ <b>В голосовом сообщении не найдено финансовых операций.</b>\n\n"
                "Я узкоспециализированный финансовый ассистент и умею учитывать только расходы, доходы и переводы.\n"
                "Назовите сумму и операцию, например: <i>«Такси 450»</i> или <i>«Зарплата 500000»</i>."
            )
        return (
            "🛡️ <b>Я узкоспециализированный финансовый ассистент Smart Bujet.</b>\n\n"
            "Я не отвечаю на общие и сторонние вопросы, а помогаю вести финансовый учёт:\n"
            "• Траты: <i>«Кофе 250»</i>, <i>«Обед 1200»</i>\n"
            "• Доходы: <i>«Зарплата 850000»</i>\n"
            "• Переводы: <i>«Перевел жене 50000»</i>\n"
            "• Депозиты: <i>«Положил на депозит 100000»</i>\n"
            "• Фото чеков и голосовые записи трат"
        )

    @staticmethod
    def service_unavailable() -> str:
        return "⚠️ Временная ошибка распознавания. Пожалуйста, попробуй ещё раз или отправь текстом."

    @staticmethod
    def welcome_new() -> str:
        return (
            "👋 <b>Добро пожаловать в Smart Bujet!</b>\n\n"
            "Я помогу вам легко вести учёт расходов и доходов.\n"
            "Пожалуйста, выберите вашу основную валюту:"
        )

    @staticmethod
    def welcome_back(first_name: str | None, currency: str, current_balance: float | None = None) -> str:
        name_greeting = f", {esc(first_name)}" if first_name else ""
        symbol = get_currency_symbol(currency)
        balance_part = ""
        if current_balance is not None:
            balance_part = f"💳 Текущий баланс: <b>{format_amount(current_balance, currency)}</b>\n\n"
        return (
            f"👋 <b>С возвращением{name_greeting}!</b>\n\n"
            f"💰 Ваша текущая валюта: <b>{currency} ({symbol})</b>\n"
            f"{balance_part}"
            f"💡 <b>Как записать операцию:</b>\n"
            f"• Текстом: <i>«Кофе 250»</i>, <i>«Зарплата 860000»</i>, <i>«Перевел жене 50000»</i>\n"
            f"• Запишите голосовое сообщение\n"
            f"• Отправьте фото чека"
        )

    @staticmethod
    def ask_initial_balance() -> str:
        return (
            "💳 <b>Сколько у тебя сейчас на счету?</b>\n\n"
            "Напиши сумму (например: <code>500000</code> или <code>0</code>) или назови её голосом, чтобы я начал точный учёт баланса:"
        )

    @staticmethod
    def initial_balance_set(amount: float, currency: str) -> str:
        return (
            f"✅ <b>Начальный баланс установлен: {format_amount(amount, currency)}</b>!\n\n"
            f"Теперь ты можешь вести учёт:\n"
            f"• Расходы: <i>«Кофе 250»</i>, <i>«Я перевел жене 50000»</i>\n"
            f"• Доходы: <i>«Пришла зарплата 860000»</i>, <i>«Подарок 20000»</i>\n"
            f"• Голосом или фото чеков"
        )

    @staticmethod
    def guard_set_balance_first() -> str:
        return (
            "⚠️ <b>Прежде чем записывать траты, укажи: Сколько у тебя сейчас на счету?</b>\n\n"
            "Напиши сумму (например: <code>500000</code> или <code>0</code>) или назови её голосом."
        )

    @staticmethod
    def currency_updated(currency: str) -> str:
        symbol = get_currency_symbol(currency)
        return f"✅ Валюта успешно установлена: <b>{currency} ({symbol})</b>"


def format_summary_card(
    summary: Any,
    advice: dict[str, str] | None = None
) -> str:
    curr = getattr(summary, "currency", "KZT")
    scope_title = "👨‍👩‍👧‍👦 Семейная" if getattr(summary, "is_family", False) else "👤 Личная"
    net_savings = getattr(summary, "net_savings", 0.0)
    sign = "+" if net_savings >= 0 else ""
    saving_rate = getattr(summary, "saving_rate", 0.0)

    lines = [
        f"📊 <b>Финансовая сводка ({scope_title})</b>",
        f"📅 Период: <b>{esc(getattr(summary, 'period_label', ''))}</b>",
        "━━━━━━━━━━━━━━━━━━━━━",
        f"💸 <b>Расходы:</b> {format_amount(getattr(summary, 'total_expense', 0.0), curr)}",
        f"💰 <b>Доходы:</b> {format_amount(getattr(summary, 'total_income', 0.0), curr)}",
        f"📈 <b>Чистый результат:</b> {sign}{format_amount(net_savings, curr)} (сбережения {saving_rate}%)",
        ""
    ]

    top_cat_name = getattr(summary, "top_category_name", None)
    if top_cat_name:
        top_cat_amount = getattr(summary, "top_category_amount", 0.0)
        top_cat_share = getattr(summary, "top_category_share", 0.0)
        lines.extend([
            "🏆 <b>Главная категория трат:</b>",
            f"• <b>{esc(top_cat_name)}</b>: {format_amount(top_cat_amount, curr)} (<b>{top_cat_share}%</b> от всех трат)",
            ""
        ])

    liquid = getattr(summary, "current_liquid_balance", 0.0)
    deposits = getattr(summary, "total_deposit_balance", 0.0)
    credits = getattr(summary, "total_credit_debt", 0.0)
    runway = getattr(summary, "runway_months", 0.0)

    lines.extend([
        "💼 <b>Активы и обязательства:</b>",
        f"• 💳 На карте / текущий баланс: <b>{format_amount(liquid, curr)}</b>",
        f"• 🏦 Депозиты и сбережения: <b>{format_amount(deposits, curr)}</b>",
        f"• 💳 Остаток долга по кредитам: <b>{format_amount(credits, curr)}</b>",
        f"• 🛡️ Подушка безопасности: <b>{runway:.1f} мес.</b>",
    ])

    if advice:
        lines.extend([
            "━━━━━━━━━━━━━━━━━━━━━",
            "🤖 <b>Рекомендации Smart Bujet:</b>",
            f"✂️ <b>Где ужаться:</b> {esc(advice.get('where_to_cut', ''))}",
            f"📥 <b>Куда отложить:</b> {esc(advice.get('where_to_save', ''))}",
            f"⚠️ <b>Обратить внимание:</b> {esc(advice.get('what_to_watch', ''))}"
        ])

    return "\n".join(lines)

